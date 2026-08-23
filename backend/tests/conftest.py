"""テスト用DB設定。

app.database はモジュールインポート時にエンジンを生成するため、他の app.* を
インポートする前に環境変数でテスト用DBパスを確定させる（本ファイルはpytestが
テストモジュールより先に読み込むconftestであることを利用する）。
"""

import os
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TESTS_DIR.parent
TEST_DB_PATH = TESTS_DIR / "_test.db"

if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

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
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
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
    from app.models.base import Base

    def _override_get_db():
        yield seeded_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        seeded_session.rollback()
        for table in reversed(Base.metadata.sorted_tables):
            seeded_session.execute(table.delete())
        seeded_session.commit()
