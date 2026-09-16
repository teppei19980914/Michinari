"""テスト用DB設定。

app.database はモジュールインポート時にエンジンを生成するため、他の app.* を
インポートする前に環境変数でテスト用DBパスを確定させる（本ファイルはpytestが
テストモジュールより先に読み込むconftestであることを利用する）。
"""

import os
import tempfile
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TESTS_DIR.parent
# 2026-09-16、release.bat経由の実行で、固定パスのテストDB（当初はリポジトリ配下の
# tests/_test.db、その後 tempfile.gettempdir() 配下の固定ファイル名）の削除が
# `PermissionError: [WinError 32]` で2回連続失敗した（3秒×5回＝最大15秒の再試行を
# 使い切っても解消せず）。tempfile配下へ移した後も再発したことから、原因はOneDrive
# ロックに限らない（アンチウイルスの一時スキャン等、他プロセスが一時的にロックする
# 要因は他にも起こりうる）と判断した。「削除してから使う」設計そのものが、前回実行の
# 残骸ファイルに新しい実行がロックで阻まれるという構造的な弱点を持つため、
# 固定パスではなく`tempfile.TemporaryDirectory`でテスト実行のたびに専用の一意な
# ディレクトリを割り当てる方式へ改めた。これにより「削除対象が存在しない＝削除に
# 失敗しようがない」という形で起動時の失敗経路自体を無くした。終了時の後片付けも
# `ignore_cleanup_errors=True`（scripts/release_smoke.py のスモークDBと同じ）とし、
# 万一ロックが残っていても後片付けの失敗でテスト結果自体を失敗させない
# （一時ディレクトリはOSが定期的に掃除する領域のため、まれに残っても実害はない）。
_test_db_dir = tempfile.TemporaryDirectory(
    prefix="michinari-backend-tests-", ignore_cleanup_errors=True
)
TEST_DB_PATH = Path(_test_db_dir.name) / "_test.db"

os.environ["MICHINARI_DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402

from alembic import command  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


@pytest.fixture(scope="session", autouse=True)
def _migrated_database(alembic_config: Config):
    """完了条件『alembic upgrade head でデータベースが構築される』を実際に検証する。"""
    command.upgrade(alembic_config, "head")
    yield
    engine.dispose()
    _test_db_dir.cleanup()


def _wipe_all_tables(session) -> None:
    """全テーブルを空にする（PRAGMA foreign_keys=ON のため子テーブルから順に削除する）。

    session.rollback() は commit() 済みの変更を取り消せないため、テスト内で明示的に
    commit() するケース（例: test_seed_data.py の冪等性検証）があっても、次のテストへ
    状態が漏れないようにするための後始末（client フィクスチャと共通の後始末処理）。
    """
    from app.models.base import Base

    session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        _wipe_all_tables(session)
        session.close()


@pytest.fixture
def seeded_session(db_session):
    """app_setting・day_type_default 等を投入済みのセッション（サービス層テストで使用）。

    run_all は冪等なため、他テストの実行順に依存せず必要な初期データを保証できる。
    """
    from app.init.seed_data import run_all

    run_all(db_session)
    return db_session


@pytest.fixture
def client(seeded_session):
    """API層テスト用のTestClient。get_dbをテスト用セッション(seeded_session)へ差し替える。

    API層の各エンドポイントはリクエスト完了時に session.commit() を呼ぶため
    （通常のREST実装）、db_session フィクスチャのロールバックだけでは後始末できない。
    そのためテスト終了時に全テーブルを明示的に空にする（PRAGMA foreign_keys=ON のため
    子テーブルから順に削除する）。
    """
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    def _override_get_db():
        yield seeded_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        _wipe_all_tables(seeded_session)
