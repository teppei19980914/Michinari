"""ナレッジエクスポートAPIのテスト（仕様書6.10 SC-13、実装フェーズ分割計画書Phase10）。"""

import pytest

from app.ai import client as ai_client
from app.ai import rate_limiter
from app.services import export_progress, export_service
from tests import api_allocation_helpers


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


@pytest.fixture(autouse=True)
def _export_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(export_service, "EXPORT_DIR", tmp_path)
    return tmp_path


def _create_goal(client, name="目標A"):
    goal = client.post("/api/v1/goals", json={"name": name, "start_date": "2026-01-01"}).json()
    api_allocation_helpers.allocate(client, goal["id"])
    return goal


def test_preview_returns_data_and_markdown(client):
    goal = _create_goal(client)

    response = client.get(f"/api/v1/goals/{goal['id']}/knowledge-export/preview")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["schema_version"] == export_service.SCHEMA_VERSION
    assert "# 目標A" in body["markdown"]


def test_preview_respects_selection_query_params(client):
    goal = _create_goal(client)

    response = client.get(
        f"/api/v1/goals/{goal['id']}/knowledge-export/preview",
        params={"materials": False, "summary": False},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert "materials" not in data
    assert "summary" not in data
    assert "goal" in data


def test_execute_export_writes_files_and_returns_paths(client):
    goal = _create_goal(client)

    response = client.post(f"/api/v1/goals/{goal['id']}/knowledge-export", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["markdown_path"].endswith(".md")
    assert body["json_path"].endswith(".json")


def test_execute_export_with_anonymize_calls_ai(client, monkeypatch):
    goal = _create_goal(client)

    def _fake(session, *, chat_uid, message):
        return ai_client.SendResult(response_text="匿名化レポート", latency_ms=1)

    monkeypatch.setattr(ai_client, "send_message", _fake)
    monkeypatch.setattr(
        ai_client,
        "create_chat_in_folder_by_name",
        lambda session, *, assistant_uid, folder_name, title: "chat-1",
    )

    response = client.post(f"/api/v1/goals/{goal['id']}/knowledge-export", json={"anonymize": True})

    assert response.status_code == 200
    assert response.json()["data"]["retrospective"] == "匿名化レポート"


# --- GET /goals/{goal_id}/knowledge-export/progress（Phase10注意点「進捗を表示すること」） ---


def test_get_progress_returns_not_in_progress_when_no_export_running(client):
    goal = _create_goal(client)

    response = client.get(f"/api/v1/goals/{goal['id']}/knowledge-export/progress")

    assert response.status_code == 200
    assert response.json() == {"in_progress": False, "completed": 0, "total": 0}


def test_get_progress_reflects_in_memory_state(client):
    goal = _create_goal(client)
    export_progress.start(goal["id"], total=3)
    try:
        export_progress.advance(goal["id"])

        response = client.get(f"/api/v1/goals/{goal['id']}/knowledge-export/progress")

        assert response.status_code == 200
        assert response.json() == {"in_progress": True, "completed": 1, "total": 3}
    finally:
        export_progress.finish(goal["id"])
