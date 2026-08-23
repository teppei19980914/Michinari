"""起動補助関数のテスト（DBテーブル作成、起動ポートの解決）。"""

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants.app_setting_keys import SERVER_PORT
from app.database import create_all_tables, engine, get_db
from app.main import port_from_app_setting, resolve_startup_port
from app.models.setting import AppSetting


def test_create_all_tables_is_idempotent():
    create_all_tables()
    create_all_tables()
    inspector = inspect(engine)
    assert "goal" in inspector.get_table_names()


def test_get_db_yields_and_closes_session():
    generator = get_db()
    session = next(generator)
    assert isinstance(session, Session)
    generator.close()


def test_resolve_startup_port_reads_app_setting(db_session):
    port = resolve_startup_port()
    assert port == int(db_session.get(AppSetting, SERVER_PORT).value)


def test_port_from_app_setting_falls_back_when_row_missing(db_session):
    setting = db_session.get(AppSetting, SERVER_PORT)
    if setting is not None:
        db_session.delete(setting)
        db_session.flush()

    port = port_from_app_setting(db_session)

    assert port == get_settings().fallback_server_port
    db_session.rollback()
