"""テスト用DB設定。

app.database はモジュールインポート時にエンジンを生成するため、他の app.* を
インポートする前に環境変数でテスト用DBパスを確定させる（本ファイルはpytestが
テストモジュールより先に読み込むconftestであることを利用する）。
"""

import os
import tempfile
from pathlib import Path

from tests.db_retry import unlink_retrying

TESTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TESTS_DIR.parent
# 2026-09-16、release.bat経由の実行でOneDriveロック（PermissionError: WinError 32）により
# db_retry.pyの再試行（3秒×5回＝最大15秒）を使い切ってもテストDBを削除できずリリースが
# 失敗する事象が発生した。本リポジトリ配下（tests/直下）はOneDrive同期フォルダのため、
# 直前のuv sync・別のpytest実行によるファイル書き換えが多いとロックが長引きうる。
# scripts/release_smoke.py のスモークDB（tempfile.TemporaryDirectory）と同じ方針で、
# OneDrive同期の対象外である一時ディレクトリへ置き、問題の根本原因を避ける
# （db_retry.pyの再試行はアンチウイルス等の別要因への保険として維持する）。
TEST_DB_PATH = Path(tempfile.gettempdir()) / "michinari-backend-tests" / "_test.db"
TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

if TEST_DB_PATH.exists():
    unlink_retrying(TEST_DB_PATH)

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
        unlink_retrying(TEST_DB_PATH)


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
