"""データ管理APIのテスト（仕様書6.12 SC-12、実装フェーズ分割計画書Phase10）。

backup_service と同じ理由（Windows環境での共有DBファイルロック回避、かつ
export_all_data/import_all_data はBase.metadataの全テーブルを対象とするため）で、
database_path・BACKUP_DIR・engine を実スキーマのスタブDBへ差し替える。
"""

import json
import sqlite3

import pytest
from sqlalchemy import create_engine

from app.models.base import Base
from app.services import backup_service


def _insert_minimal_goal(db_path, *, id_=1, name="マーカー"):
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "INSERT INTO goal (id, name, start_date, status, category, "
            "created_at, updated_at) VALUES (?, ?, '2026-01-01', 'DRAFT', 'EXAM', "
            "'2026-01-01T00:00:00', '2026-01-01T00:00:00')",
            (id_, name),
        )
        connection.commit()
    finally:
        connection.close()


class _NoopEngine:
    def dispose(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _stub_db(tmp_path, monkeypatch):
    db_path = tmp_path / "michinari.db"
    temp_engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=temp_engine)
    temp_engine.dispose()

    monkeypatch.setattr(backup_service, "database_path", lambda: db_path)
    monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(backup_service, "engine", _NoopEngine())
    return db_path


def test_export_data_returns_json_with_table_rows(client, _stub_db):
    _insert_minimal_goal(_stub_db)

    response = client.get("/api/v1/data/export")

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == backup_service.DATA_SCHEMA_VERSION
    assert body["tables"]["goal"][0]["name"] == "マーカー"
    assert "attachment" in response.headers["content-disposition"]


def test_backup_then_list_returns_created_backup(client):
    created = client.post("/api/v1/data/backup")
    assert created.status_code == 201

    listed = client.get("/api/v1/data/backups")
    assert listed.status_code == 200
    ids = [b["id"] for b in listed.json()]
    assert created.json()["id"] in ids


def test_restore_missing_backup_returns_404(client):
    response = client.post("/api/v1/data/backups/backup_20000101_000000/restore")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_restore_existing_backup_succeeds(client, _stub_db):
    created = client.post("/api/v1/data/backup").json()

    response = client.post(f"/api/v1/data/backups/{created['id']}/restore")

    assert response.status_code == 204


def test_import_rejects_non_json_file(client):
    response = client.post(
        "/api/v1/data/import",
        files={"file": ("not_json.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_import_rejects_unrelated_json(client):
    payload = json.dumps({"schema_version": "1.0", "tables": {"unrelated": []}}).encode("utf-8")

    response = client.post(
        "/api/v1/data/import",
        files={"file": ("data.json", payload, "application/json")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_import_replaces_database(client, _stub_db):
    _insert_minimal_goal(_stub_db, name="インポート前")
    exported = client.get("/api/v1/data/export").json()
    exported["tables"]["goal"][0]["name"] = "インポート済み"
    payload = json.dumps(exported).encode("utf-8")

    response = client.post(
        "/api/v1/data/import",
        files={"file": ("michinari_export.json", payload, "application/json")},
    )

    assert response.status_code == 204
    connection = sqlite3.connect(_stub_db)
    name = connection.execute("SELECT name FROM goal WHERE id = 1").fetchone()[0]
    connection.close()
    assert name == "インポート済み"
