"""アプリケーション起動（設計書 データ構造編 8章）。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.ai import logger as ai_logger
from app.api.ai import router as ai_router
from app.api.calendar import router as calendar_router
from app.api.dashboard import router as dashboard_router
from app.api.errors import register_exception_handlers
from app.api.goals import router as goals_router
from app.api.materials import router as materials_router
from app.api.records import router as records_router
from app.api.resources import router as resources_router
from app.config import get_settings
from app.constants.app_setting_keys import SERVER_PORT
from app.database import SessionLocal, create_all_tables
from app.init.seed_data import run_all
from app.models.setting import AppSetting
from app.services import goal_service, weekly_summary_service

#: データ構造編6.1「ベースパス /api/v1」。
API_V1_PREFIX = "/api/v1"


def bootstrap_database() -> None:
    """テーブル作成（本番相当は Alembic）と初期データ投入をまとめて行う。

    ai_logの保持期間超過分の削除（データ構造編5.5「起動時に削除する」）もここで行う。
    AI基盤への通信を伴わないローカルなDB操作のみのため、テスト実行時（TestClientの
    lifespan経由での毎回起動）に含めても安全（実ネットワーク呼び出しを伴う週次要約の
    遡及生成はここに含めない。run_ai_startup_tasks・__main__ブロックを参照）。
    """
    create_all_tables()
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


if __name__ == "__main__":  # pragma: no cover (実サーバ起動のためユニットテスト対象外)
    import uvicorn

    port = resolve_startup_port()
    run_ai_startup_tasks()
    uvicorn.run(app, host="0.0.0.0", port=port)
