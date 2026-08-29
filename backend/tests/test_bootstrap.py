"""起動補助関数のテスト（DBテーブル作成、起動ポートの解決、AI連携の起動時タスク）。"""

import sqlite3
import sys

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app import main as app_main
from app.config import BACKEND_DIR, get_settings
from app.constants.app_setting_keys import SERVER_PORT
from app.database import create_all_tables, engine, get_db
from app.main import port_from_app_setting, resolve_startup_port
from app.models.setting import AppSetting
from app.services import backup_service, weekly_summary_service
from tests import migration_helpers


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


def test_resolve_alembic_ini_path_uses_backend_dir_when_not_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)

    result = app_main.resolve_alembic_ini_path()

    assert result == BACKEND_DIR / "alembic.ini"


def test_resolve_alembic_ini_path_uses_meipass_when_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    result = app_main.resolve_alembic_ini_path()

    assert result == tmp_path / "alembic.ini"


def test_upgrade_database_schema_is_a_no_op_when_already_current(tmp_path, monkeypatch):
    """既にhead（最新）の場合は何もしない（バックアップも作成しない）。TestClientのlifespan
    経由で毎起動ごとに呼ばれても安全・軽量であることの退行防止。"""
    monkeypatch.setattr(app_main, "_schema_confirmed_current", False)
    monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path / "backups")

    app_main.upgrade_database_schema()

    assert not (tmp_path / "backups").exists()
    assert app_main._schema_confirmed_current is True


def test_upgrade_database_schema_migrates_legacy_unversioned_database_without_data_loss(
    tmp_path, monkeypatch
):
    """実際の不具合の再現・再発防止テスト。

    配布パッケージは本関数導入前、`create_all_tables()`のみでスキーマを構築しており、
    `alembic_version`テーブル自体が存在しない（一度もAlembicで管理されていない）。この
    状態のDBに新しいマイグレーション（passing_score_type/passing_score_max列追加）が
    未適用のまま起動すると`no such column`でアプリ自体が起動不能になっていた。

    `alembic_version`が無い状態でいきなり`upgrade head`すると、初期マイグレーションの
    `create_table`が「テーブルは既に存在する」エラーになるため、
    `_PRE_ALEMBIC_BASELINE_REVISION`へのstampを経由する必要がある（本テストはこの
    stamp経由の分岐を検証する）。

    a3f9c1d7e2b4までのスキーマをAlembicで構築した後、`alembic_version`テーブルを
    削除することで、この「一度もAlembic管理されていない既存DB」を再現する。
    """
    db_path = tmp_path / "legacy.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("a3f9c1d7e2b4")  # passing_score_type列追加（head）の1つ前
    migration_helpers.drop_alembic_version_table(db_path)

    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "INSERT INTO goal (id, name, start_date, status, resource_ratio, "
            "created_at, updated_at) VALUES (1, '目標A', '2026-01-01', 'DRAFT', 0.0, "
            "'2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        )
        connection.execute(
            "INSERT INTO exam_subject (id, goal_id, name, exam_date_type, passing_score, "
            "display_order, created_at, updated_at) VALUES (1, 1, '科目A', 'FIXED', 60.0, "
            "1, '2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        )
        connection.commit()
    finally:
        connection.close()

    stub_engine = create_engine(f"sqlite:///{db_path}")
    monkeypatch.setattr(app_main, "engine", stub_engine)
    monkeypatch.setattr(app_main, "_schema_confirmed_current", False)
    monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path / "backups")

    app_main.upgrade_database_schema()

    stub_engine.dispose()
    connection = sqlite3.connect(db_path)
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(exam_subject)")}
        assert {"passing_score_type", "passing_score_max"} <= columns
        name, passing_score_type = connection.execute(
            "SELECT name, passing_score_type FROM exam_subject WHERE id = 1"
        ).fetchone()
        assert name == "科目A"
        assert passing_score_type == "PERCENTAGE"
    finally:
        connection.close()
    assert any("pre_migration" in p.name for p in (tmp_path / "backups").glob("*.db"))


def test_upgrade_database_schema_upgrades_normally_tracked_database_without_stamp(
    tmp_path, monkeypatch
):
    """今後の通常のアップデート経路（今回のインシデント対応より後、既に`alembic_version`
    テーブルで管理されているDBを1つ前のリビジョンからheadへ更新するケース）を検証する。

    `is_legacy_unversioned_database`がFalseとなり`stamp`を経由しない分岐と、DBファイルが
    まだ存在しない場合に安全退避コピーをスキップする分岐（`db_path.exists()`がFalse）を
    同時に検証する。
    """
    db_path = tmp_path / "tracked.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")
    migration_helpers.upgrade_to("a3f9c1d7e2b4")  # alembic_versionテーブルを持つ正規のDB

    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "INSERT INTO goal (id, name, start_date, status, resource_ratio, "
            "created_at, updated_at) VALUES (1, '目標A', '2026-01-01', 'DRAFT', 0.0, "
            "'2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        )
        connection.execute(
            "INSERT INTO exam_subject (id, goal_id, name, exam_date_type, passing_score, "
            "display_order, created_at, updated_at) VALUES (1, 1, '科目A', 'FIXED', 60.0, "
            "1, '2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        )
        connection.commit()
    finally:
        connection.close()

    stub_engine = create_engine(f"sqlite:///{db_path}")
    monkeypatch.setattr(app_main, "engine", stub_engine)
    monkeypatch.setattr(app_main, "_schema_confirmed_current", False)
    monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(backup_service, "database_path", lambda: tmp_path / "does_not_exist.db")

    app_main.upgrade_database_schema()

    stub_engine.dispose()
    assert not (tmp_path / "backups").exists()  # db_path.exists()がFalseのため安全退避コピー無し

    connection = sqlite3.connect(db_path)
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(exam_subject)")}
        assert {"passing_score_type", "passing_score_max"} <= columns
        name = connection.execute("SELECT name FROM exam_subject WHERE id = 1").fetchone()[0]
        assert name == "科目A"
    finally:
        connection.close()
