"""起動補助関数のテスト（DBテーブル作成、起動ポートの解決、AI連携の起動時タスク）。"""

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app import main as app_main
from app.config import get_settings
from app.constants.app_setting_keys import SERVER_PORT
from app.database import create_all_tables, engine, get_db
from app.main import port_from_app_setting, resolve_startup_port
from app.models.setting import AppSetting
from app.services import weekly_summary_service


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


def test_run_ai_startup_tasks_calls_retroactive_generation(db_session, monkeypatch):
    """実サーバ起動時のみ呼ばれる週次要約の遡及生成（ロジック・プロンプト編15.2、
    実装フェーズ分割計画書Phase5完了条件「週次要約が起動時に遡及生成される」）。
    AI基盤への実通信はweekly_summary_service側の責務のためここではモックする。

    run_ai_startup_tasks は独自にSessionLocal()を開くため、goal_service.resolve_today が
    参照するapp_settingを本テストのdb_sessionとは別に用意する必要がある（run_allで投入）。
    """
    from app.init.seed_data import run_all

    run_all(db_session)

    calls = []
    monkeypatch.setattr(
        weekly_summary_service,
        "run_retroactive_generation",
        lambda session, today: calls.append(today) or 0,
    )

    app_main.run_ai_startup_tasks()

    assert len(calls) == 1
