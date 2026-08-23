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
