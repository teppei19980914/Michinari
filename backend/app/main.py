"""アプリケーション起動（設計書 データ構造編 8章）。"""

import sys
import webbrowser
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Timer

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.types import Scope

from alembic import command
from app.ai import logger as ai_logger
from app.api.ai import router as ai_router
from app.api.analytics import router as analytics_router
from app.api.calendar import router as calendar_router
from app.api.closure import router as closure_router
from app.api.dashboard import router as dashboard_router
from app.api.data import router as data_router
from app.api.errors import register_exception_handlers
from app.api.export import router as export_router
from app.api.goals import router as goals_router
from app.api.materials import router as materials_router
from app.api.records import router as records_router
from app.api.resources import router as resources_router
from app.api.settings import router as settings_router
from app.api.system_info import router as system_info_router
from app.config import BACKEND_DIR, REPO_ROOT, get_settings
from app.constants.app_setting_keys import SERVER_PORT
from app.database import SessionLocal, engine
from app.init.seed_data import run_all
from app.models.setting import AppSetting
from app.services import backup_service, goal_service, weekly_summary_service

#: データ構造編6.1「ベースパス /api/v1」。
API_V1_PREFIX = "/api/v1"


def resolve_frontend_dist_dir() -> Path:
    """フロントエンドのビルド済み静的ファイルの配置先を解決する（配布パッケージ対応）。

    PyInstallerでパッケージ化された実行ファイル（`sys.frozen`）として起動している場合は、
    同梱した静的ファイル（ビルドスクリプトが `frontend_dist` として配置する）を参照する。
    ソースから起動する開発環境では `frontend/dist`（`npm run build` の既定出力先）を参照する。
    いずれの場合も存在しなければ create_app 側でマウントをスキップし、これまで通り
    Vite開発サーバー（`npm run dev`）経由でのアクセスを前提とする。
    """
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "frontend_dist"
    return REPO_ROOT / "frontend" / "dist"


def resolve_alembic_ini_path() -> Path:
    """alembic.iniの配置先を解決する（配布パッケージ対応）。resolve_frontend_dist_dirと同じ
    理由で、PyInstallerでパッケージ化された実行ファイル（`sys.frozen`）として起動している
    場合は同梱した`alembic.ini`（ビルドスクリプトbuild_backendが `.`＝バンドル直下へ配置、
    `alembic/`本体もあわせて同梱）を、ソースから起動する開発環境では`backend/alembic.ini`
    を参照する。
    """
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "alembic.ini"
    return BACKEND_DIR / "alembic.ini"


class _SpaStaticFiles(StaticFiles):
    """未一致パスを index.html へフォールバックする静的ファイル配信。

    React Routerはクライアント側でルーティングするため、`/goals/3` のような
    ビルド後の実ファイルが存在しないパスへの直接アクセスでも index.html を返し、
    フロント側のルーティングに委ねる必要がある（配布パッケージで単一プロセス配信する
    場合のみ関係する。開発時はVite開発サーバー側がこれを処理する）。
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


#: upgrade_database_schemaが同一プロセス内での再チェックを省略するためのフラグ
#: （DBのスキーマ状態はプロセス起動後に外部から変化しない前提。テスト実行時、
#: TestClientのlifespan経由で毎回呼ばれても2回目以降を軽量にするため）。
_schema_confirmed_current = False

#: 本関数導入前の配布パッケージは`create_all_tables()`のみでスキーマを構築しており、
#: alembic_versionテーブル自体を持たない。それらのDBのテーブルは、導入前の最終
#: マイグレーション（＝このリビジョンの1つ前）までと同じ実質スキーマを持つ
#: （create_all_tables()は既存テーブルへの列追加は行わないが、テーブル自体は
#: 作成された時点のモデル定義通りに作られるため、本プロジェクトで配布された全ビルドは
#: 導入時点のモデル定義を反映済み）。そのためstamp先として固定するのは安全である
#: （2026-08 exam_subject.passing_score_type欠落インシデントの根本修正時に判明）。
_PRE_ALEMBIC_BASELINE_REVISION = "a3f9c1d7e2b4"


def upgrade_database_schema() -> None:
    """DBスキーマをAlembicの最新リビジョンへ更新する（データ構造編8章、本番相当の構築）。

    以前は`create_all_tables()`（`Base.metadata.create_all()`）のみを実行していたが、
    これは未作成のテーブルを新規作成するだけで、既存テーブルへのカラム追加等の
    スキーマ変更は反映しない。配布パッケージを新バージョンに差し替えた際、既存
    インストール先のDBに新規カラムが追加されないまま起動し、`no such column`エラーで
    アプリ自体が起動不能になる不具合があったため、Alembicのマイグレーションチェーン
    適用に一本化する（`alembic upgrade head`と同等の処理をAPI経由で実行）。

    新規DB（テーブル未作成）はチェーンの先頭から適用されるため、`create_all_tables()`と
    同じ最終スキーマになる（新規インストールへの挙動は変わらない）。

    `create_all_tables()`のみで構築されてきた既存DB（alembic_versionテーブルが無い）は、
    テーブルは既に存在するため、そのままchainの先頭から`upgrade`すると`create_table`が
    「テーブルが既に存在する」エラーになる。この場合は`_PRE_ALEMBIC_BASELINE_REVISION`へ
    `stamp`（実際にはSQLを実行せず、適用済みとして記録するだけ）してから`upgrade`する
    ことで、未適用分（このリビジョン以降の変更）のみを反映する。

    現在のリビジョンが既にhead（最新）の場合は何もしない（テスト実行時、TestClientの
    lifespan経由で毎起動ごとに呼ばれても安全・軽量にするため）。適用が必要な場合のみ、
    実行前にDBファイルの安全退避コピーを作成する（万一の不具合時の復旧手段を残すため、
    backup_service.create_safety_copyを再利用。CLAUDE.md DRYの原則）。
    """
    global _schema_confirmed_current
    if _schema_confirmed_current:
        return

    alembic_cfg = Config(str(resolve_alembic_ini_path()))
    script = ScriptDirectory.from_config(alembic_cfg)
    head_revision = script.get_current_head()

    with engine.connect() as connection:
        current_revision = MigrationContext.configure(connection).get_current_revision()
        is_legacy_unversioned_database = current_revision is None and inspect(
            connection
        ).has_table("goal")

    if current_revision == head_revision:
        _schema_confirmed_current = True
        return

    db_path = backup_service.database_path()
    if db_path.exists():
        engine.dispose()  # SQLiteファイルのコピー前に接続を解放する（Windowsのファイルロック対策）
        backup_service.create_safety_copy(db_path, "pre_migration")

    if is_legacy_unversioned_database:
        command.stamp(alembic_cfg, _PRE_ALEMBIC_BASELINE_REVISION)
    command.upgrade(alembic_cfg, "head")
    _schema_confirmed_current = True


def bootstrap_database() -> None:
    """スキーマ更新（Alembic）と初期データ投入をまとめて行う。

    ai_logの保持期間超過分の削除（データ構造編5.5「起動時に削除する」）もここで行う。
    AI基盤への通信を伴わないローカルなDB操作のみのため、テスト実行時（TestClientの
    lifespan経由での毎回起動）に含めても安全（実ネットワーク呼び出しを伴う週次要約の
    遡及生成はここに含めない。run_ai_startup_tasks・__main__ブロックを参照）。
    """
    upgrade_database_schema()
    session = SessionLocal()
    try:
        run_all(session)
        today = goal_service.resolve_today(session)
        ai_logger.purge_expired(session, today)
        session.commit()
    finally:
        session.close()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    bootstrap_database()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="ミチナリ API", lifespan=lifespan)
    register_exception_handlers(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(goals_router, prefix=API_V1_PREFIX)
    app.include_router(materials_router, prefix=API_V1_PREFIX)
    app.include_router(resources_router, prefix=API_V1_PREFIX)
    app.include_router(records_router, prefix=API_V1_PREFIX)
    app.include_router(calendar_router, prefix=API_V1_PREFIX)
    app.include_router(ai_router, prefix=API_V1_PREFIX)
    app.include_router(dashboard_router, prefix=API_V1_PREFIX)
    app.include_router(settings_router, prefix=API_V1_PREFIX)
    app.include_router(analytics_router, prefix=API_V1_PREFIX)
    app.include_router(closure_router, prefix=API_V1_PREFIX)
    app.include_router(export_router, prefix=API_V1_PREFIX)
    app.include_router(data_router, prefix=API_V1_PREFIX)
    app.include_router(system_info_router, prefix=API_V1_PREFIX)

    # フロントエンドの静的配信（配布パッケージ対応）。API/healthルートを登録した後に
    # マウントすることで、それらのパスが静的配信より優先して解決される。開発時は
    # frontend/distが存在しないため、これまで通りVite開発サーバー経由のプロキシとなる。
    frontend_dist_dir = resolve_frontend_dist_dir()
    if frontend_dist_dir.is_dir():
        app.mount(
            "/", _SpaStaticFiles(directory=str(frontend_dist_dir), html=True), name="frontend"
        )

    return app


app = create_app()


def port_from_app_setting(session: Session) -> int:
    """server.port（app_setting）を返す。行が存在しない場合のみ設定ファイルの
    フォールバック値を使う（DB未構築直後などのブートストラップ用）。"""
    setting = session.query(AppSetting).filter_by(key=SERVER_PORT).first()
    return int(setting.value) if setting else get_settings().fallback_server_port


def resolve_startup_port() -> int:
    bootstrap_database()
    session = SessionLocal()
    try:
        return port_from_app_setting(session)
    finally:
        session.close()


def run_ai_startup_tasks() -> None:
    """起動時のAI連携タスク（週次要約の遡及生成、ロジック・プロンプト編15.2）。

    実際にAI基盤へ通信するため、実サーバ起動時のみ呼び出す（TestClientのlifespan経由では
    呼ばない。bootstrap_databaseとは意図的に分離している）。1件の生成失敗が起動を止めない
    ことはweekly_summary_service.run_retroactive_generation側で保証する（16.7）。
    """
    session = SessionLocal()
    try:
        today = goal_service.resolve_today(session)
        weekly_summary_service.run_retroactive_generation(session, today)
    finally:
        session.close()


def _open_browser(port: int) -> None:  # pragma: no cover (実ブラウザ起動のためユニットテスト対象外)
    webbrowser.open(f"http://127.0.0.1:{port}")


if __name__ == "__main__":  # pragma: no cover (実サーバ起動のためユニットテスト対象外)
    import uvicorn

    port = resolve_startup_port()
    run_ai_startup_tasks()
    # 配布パッケージ（フロントエンドを同一プロセスで静的配信する構成）でのみ、
    # サーバー起動直後にブラウザを自動的に開く。フロントエンド未ビルドの開発環境
    # （Vite開発サーバーを別途起動する運用）では、開いても404になるだけのため行わない。
    if resolve_frontend_dist_dir().is_dir():
        Timer(1.5, _open_browser, args=(port,)).start()
    uvicorn.run(app, host="0.0.0.0", port=port)
