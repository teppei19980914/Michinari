"""backup_service のテスト（仕様書6.12 SC-12、実装フェーズ分割計画書Phase10）。

pytestが使う実際のDBファイル（tests/_test.db、conftest.py）を書き換えるとテスト全体が
壊れるため、database_path をtmp_path配下のスタブDBへ差し替えて検証する
（BACKUP_DIRも同様にtmp_path配下へ差し替える）。
"""

import sqlite3
from pathlib import Path

import pytest

from app.models.base import Base
from app.services import backup_service
from app.services.exceptions import ValidationError


def _make_sqlite_db(path, *, extra_tables=True):
    connection = sqlite3.connect(path)
    try:
        if extra_tables:
            connection.execute("CREATE TABLE goal (id INTEGER PRIMARY KEY, name TEXT)")
            connection.execute("CREATE TABLE material (id INTEGER PRIMARY KEY)")
            connection.execute("CREATE TABLE app_setting (id INTEGER PRIMARY KEY)")
            connection.execute("INSERT INTO goal (id, name) VALUES (1, 'マーカー')")
        else:
            connection.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")
        connection.commit()
    finally:
        connection.close()
    return path


class _NoopEngine:
    """テスト用スタブ。backup_service.engine.dispose() が本物のSQLAlchemyエンジン
    （pytestが使う共有DBに紐づく）へ波及しないようにする。dispose()呼び出し自体は
    仕様（SQLiteファイルコピー前に接続を解放する）の一部として検証したいが、
    対象を本物のengineにすると、テスト間で共有される接続プールへ影響し、
    Windows環境でテストDBファイルのロック解放に失敗することがあるため分離する。"""

    def __init__(self) -> None:
        self.disposed = False

    def dispose(self) -> None:
        self.disposed = True


@pytest.fixture
def stub_db(tmp_path, monkeypatch):
    db_path = tmp_path / "michinari.db"
    _make_sqlite_db(db_path)
    monkeypatch.setattr(backup_service, "database_path", lambda: db_path)
    monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(backup_service, "engine", _NoopEngine())
    return db_path


def test_create_backup_creates_a_copy(seeded_session, stub_db):
    info = backup_service.create_backup(seeded_session)

    backups = backup_service.list_backups()
    assert len(backups) == 1
    assert backups[0].id == info.id
    assert backups[0].size_bytes == stub_db.stat().st_size


def test_create_backup_prunes_beyond_retention_count(seeded_session, stub_db, monkeypatch):
    from app.services import setting_reader

    monkeypatch.setattr(setting_reader, "get_int", lambda session, key: 2)

    import time

    for _ in range(4):
        backup_service.create_backup(seeded_session)
        time.sleep(1.1)  # ファイル名のタイムスタンプ（秒精度）を確実にずらすため

    backups = backup_service.list_backups()
    assert len(backups) == 2


def test_list_backups_orders_newest_first(seeded_session, stub_db):
    import time

    first = backup_service.create_backup(seeded_session)
    time.sleep(1.1)
    second = backup_service.create_backup(seeded_session)

    backups = backup_service.list_backups()
    assert [b.id for b in backups] == [second.id, first.id]


def test_restore_backup_overwrites_current_database(seeded_session, stub_db, monkeypatch):
    original = backup_service.create_backup(seeded_session)

    # DBを書き換えてから復元し、バックアップ時点の内容へ戻ることを確認する。
    connection = sqlite3.connect(stub_db)
    connection.execute("UPDATE goal SET name = '書き換え後' WHERE id = 1")
    connection.commit()
    connection.close()

    backup_service.restore_backup(original.id)

    connection = sqlite3.connect(stub_db)
    name = connection.execute("SELECT name FROM goal WHERE id = 1").fetchone()[0]
    connection.close()
    assert name == "マーカー"
    # 復元前の安全退避コピーが残っている。
    assert any("pre_restore" in p.name for p in (backup_service.BACKUP_DIR).glob("*.db"))


def test_restore_missing_backup_raises_not_found(stub_db):
    from app.services.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        backup_service.restore_backup("backup_20000101_000000")


def test_list_backups_returns_empty_list_when_backup_dir_missing(stub_db):
    assert backup_service.list_backups() == []


def test_list_backups_ignores_files_not_matching_naming_pattern(seeded_session, stub_db):
    backup_service.create_backup(seeded_session)
    (backup_service.BACKUP_DIR / "backup_not_a_timestamp.db").write_bytes(b"junk")

    backups = backup_service.list_backups()

    assert len(backups) == 1


def test_restore_backup_with_malformed_id_raises_not_found(stub_db):
    from app.services.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        backup_service.restore_backup("not-a-valid-backup-id")


def test_database_path_resolves_from_configured_database_url(monkeypatch):
    """database_path自体（モックしていない実装）がsqlite:///URLを正しくパースすることを検証する
    （他のテストはdatabase_pathをスタブへ差し替えるため、実装そのものはここでのみ検証する）。"""
    from app.config import Settings

    monkeypatch.setattr(
        backup_service,
        "get_settings",
        lambda: Settings(database_url="sqlite:///C:/tmp/michinari_test.db"),
    )

    assert backup_service.database_path() == Path("C:/tmp/michinari_test.db")


def test_database_path_rejects_non_sqlite_url(monkeypatch):
    from app.config import Settings
    from app.services.exceptions import ValidationError

    monkeypatch.setattr(
        backup_service,
        "get_settings",
        lambda: Settings(database_url="postgresql://localhost/michinari"),
    )

    with pytest.raises(ValidationError):
        backup_service.database_path()


# --- export_all_data / import_all_data（全データのエクスポート/インポート、
# 実装フェーズ分割計画書Phase10完了条件「JSON出力をインポートして復元できる」） ---


@pytest.fixture
def full_schema_db(tmp_path, monkeypatch):
    """goal/material/app_setting 等の3表だけの stub_db では
    export_all_data/import_all_data が対象とする Base.metadata の全テーブルを
    網羅できない（存在しないテーブルへのSELECTでエラーになる）ため、
    実際のモデル定義から全テーブルを構築したDBを使う。"""
    from sqlalchemy import create_engine

    db_path = tmp_path / "michinari_full.db"
    temp_engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=temp_engine)
    temp_engine.dispose()

    monkeypatch.setattr(backup_service, "database_path", lambda: db_path)
    monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(backup_service, "engine", _NoopEngine())
    return db_path


def _insert_minimal_goal(db_path, *, id_=1, name="マーカー"):
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "INSERT INTO goal (id, name, start_date, status, resource_ratio, category, "
            "created_at, updated_at) VALUES (?, ?, '2026-01-01', 'DRAFT', 0.0, 'EXAM', "
            "'2026-01-01T00:00:00', '2026-01-01T00:00:00')",
            (id_, name),
        )
        connection.commit()
    finally:
        connection.close()


def test_export_all_data_includes_schema_version_and_table_rows(full_schema_db):
    _insert_minimal_goal(full_schema_db)

    data = backup_service.export_all_data()

    assert data["schema_version"] == backup_service.DATA_SCHEMA_VERSION
    assert "exported_at" in data
    assert data["tables"]["goal"] == [
        {
            "id": 1,
            "category": "EXAM",
            "name": "マーカー",
            "start_date": "2026-01-01",
            "status": "DRAFT",
            "resource_ratio": 0.0,
            "memo": None,
            "activated_at": None,
            "closed_at": None,
            "archived_at": None,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
    ]
    # 空テーブルも（0件のリストとして）キーが含まれる。
    assert data["tables"]["material"] == []


def test_import_all_data_round_trips_rows(full_schema_db):
    _insert_minimal_goal(full_schema_db, name="インポート前")
    data = backup_service.export_all_data()
    data["tables"]["goal"][0]["name"] = "インポート後"

    backup_service.import_all_data(data)

    connection = sqlite3.connect(full_schema_db)
    name = connection.execute("SELECT name FROM goal WHERE id = 1").fetchone()[0]
    connection.close()
    assert name == "インポート後"


def test_import_all_data_replaces_existing_rows_rather_than_appending(full_schema_db):
    _insert_minimal_goal(full_schema_db, id_=1, name="既存データ")
    data = backup_service.export_all_data()
    data["tables"]["goal"] = [
        {
            "id": 2,
            "category": "EXAM",
            "name": "新データ",
            "start_date": "2026-02-01",
            "status": "DRAFT",
            "resource_ratio": 0.0,
            "memo": None,
            "activated_at": None,
            "closed_at": None,
            "created_at": "2026-02-01T00:00:00",
            "updated_at": "2026-02-01T00:00:00",
        }
    ]

    backup_service.import_all_data(data)

    connection = sqlite3.connect(full_schema_db)
    rows = connection.execute("SELECT id, name FROM goal").fetchall()
    connection.close()
    assert rows == [(2, "新データ")]


def test_import_all_data_creates_safety_backup(full_schema_db):
    _insert_minimal_goal(full_schema_db)
    data = backup_service.export_all_data()

    backup_service.import_all_data(data)

    assert any("pre_import" in p.name for p in backup_service.BACKUP_DIR.glob("*.db"))


def test_import_all_data_rejects_missing_tables_key(full_schema_db):
    with pytest.raises(ValidationError):
        backup_service.import_all_data({"schema_version": "1.0"})


def test_import_all_data_rejects_schema_version_mismatch(full_schema_db):
    data = backup_service.export_all_data()
    data["schema_version"] = "9.9"

    with pytest.raises(ValidationError):
        backup_service.import_all_data(data)


def test_import_all_data_rejects_missing_required_tables(full_schema_db):
    with pytest.raises(ValidationError):
        backup_service.import_all_data(
            {"schema_version": backup_service.DATA_SCHEMA_VERSION, "tables": {"unrelated": []}}
        )


def test_import_all_data_rolls_back_on_failure_partway_through(full_schema_db):
    """挿入中に失敗した場合、ロールバックしてDBを触る前の状態に戻す
    （全削除→全再構築の途中で失敗しても中途半端な状態を残さないため）。"""
    _insert_minimal_goal(full_schema_db, name="ロールバック確認用")
    data = backup_service.export_all_data()
    # goalテーブルのNOT NULL列（status等）を欠いた不正な行を混入させ、INSERT時に失敗させる。
    data["tables"]["goal"] = [{"id": 1, "name": "不正データ"}]

    with pytest.raises(sqlite3.Error):
        backup_service.import_all_data(data)

    connection = sqlite3.connect(full_schema_db)
    name = connection.execute("SELECT name FROM goal WHERE id = 1").fetchone()[0]
    connection.close()
    assert name == "ロールバック確認用"
