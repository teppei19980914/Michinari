"""テスト用DB設定（backend/tests/conftest.pyと同じ方針。別実装）。

本番はPostgreSQL（Supabase）だが、テストは実行のたびに専用の一意なSQLiteファイルを使う
（backend/tests/conftest.pyと同じ理由：固定パスの前回実行の残骸ファイルを新しい実行が
削除しようとして他プロセスのロックに阻まれる事故を構造的に避けるため）。
`app.database`はモジュールimport時にengineを生成するため、他のapp.*をimportする前に
環境変数でテスト用DBパスを確定させる。
"""

import contextlib
import logging
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PUBLISH_SERVER_DIR = TESTS_DIR.parent

_test_db_dir = tempfile.TemporaryDirectory(
    prefix="michinari-publish-server-tests-", ignore_cleanup_errors=True
)
TEST_DB_PATH = Path(_test_db_dir.name) / "_test.db"

os.environ["PUBLISH_DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
# セッションCookieのSecure属性（D-18）をテストでも検証するため、TestClientはHTTPS相当の
# base_urlで動かす（tests/test_auth_api.pyのclientフィクスチャ参照）。
os.environ.setdefault("PUBLISH_LOGIN_MAX_ATTEMPTS", "5")
os.environ.setdefault("PUBLISH_LOGIN_LOCKOUT_MINUTES", "15")

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from alembic import command  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.base import Base  # noqa: E402


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    config = Config(str(PUBLISH_SERVER_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(PUBLISH_SERVER_DIR / "alembic"))
    return config


@contextlib.contextmanager
def _preserve_logging_state() -> Iterator[None]:
    """alembicの`fileConfig()`（`disable_existing_loggers`既定True）から既存ロガーを守る。

    `fileConfig()`は呼び出し時点で存在する非alembicロガー（`app.api.errors`等、テスト
    モジュールのimport時点で生成済み）を標準ライブラリの仕様で全て`disabled = True`にする。
    これを退避しないと、このフィクスチャ（セッション単位で最初に1回だけ実行）以降、
    テスト全体で`caplog`が何も捕捉できなくなる（backend/app/desktop/logging_setup.py
    の`preserve_logging_state`と同じ問題・同じ対策。publish_serverはbackendとは別実装の
    ため、テスト専用としてここに複製する）。
    """
    root_logger = logging.getLogger()
    disabled_snapshot = {
        name: logger_obj.disabled
        for name, logger_obj in root_logger.manager.loggerDict.items()
        if isinstance(logger_obj, logging.Logger)
    }
    try:
        yield
    finally:
        for name, was_disabled in disabled_snapshot.items():
            logger_obj = root_logger.manager.loggerDict.get(name)
            if isinstance(logger_obj, logging.Logger):
                logger_obj.disabled = was_disabled


@pytest.fixture(scope="session", autouse=True)
def _migrated_database(alembic_config: Config):
    """完了条件『alembic upgrade headでデータベースが構築される』を実際に検証する。"""
    with _preserve_logging_state():
        command.upgrade(alembic_config, "head")
    yield
    engine.dispose()
    _test_db_dir.cleanup()


def _wipe_all_tables(session) -> None:
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
def client(db_session):
    """Secure Cookie（D-18）の送受信を検証できるよう、base_urlをhttps扱いにする。"""
    app = create_app()
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client
