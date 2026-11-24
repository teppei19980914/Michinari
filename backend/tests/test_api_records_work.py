"""日次記録APIのテストのうち仕事（WORK）固有のエンドポイント（データ構造編6.2、
仕様書6.4〜6.7・7.2章、実装フェーズ分割計画書Phase21・Phase22・S02）。共通処理・カテゴリ横断の
相互独立性のテストはtest_api_records_common.pyを参照（実装フェーズ分割計画書S02、
test_api_records.pyからの分割）。
"""

import datetime as dt

import pytest

from app.ai import client as ai_client
from app.ai import rate_limiter


def _make_active_work_goal_with_assignment(client):
    goal = client.post(
        "/api/v1/goals",
        json={"category": "WORK", "name": "仕事目標A", "start_date": "2026-01-01"},
    ).json()
    work_assignment = client.post(
        f"/api/v1/goals/{goal['id']}/work-assignment",
        json={"expected_content": "想定業務内容", "start_date": "2026-01-01"},
    ).json()
    activated = client.post(f"/api/v1/goals/{goal['id']}/activate")
    assert activated.status_code == 200, activated.text
    return goal, work_assignment


# --- POST /records/{date}/work-chat（実装フェーズ分割計画書Phase22） ---


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


def _stub_ai_client(monkeypatch, *, response="AIからの応答", raise_exc=None):
    def _fake_send_message(session, *, chat_uid, message):
        if raise_exc is not None:
            raise raise_exc
        return ai_client.SendResult(response_text=response, latency_ms=42)

    monkeypatch.setattr(ai_client, "send_message", _fake_send_message)
    monkeypatch.setattr(
        ai_client,
        "create_chat_in_folder_by_name",
        lambda session, *, assistant_uid, folder_name, title: "chat-uid-api",
    )


def test_work_chat_endpoint_returns_assistant_message(client, monkeypatch):
    goal, work_assignment = _make_active_work_goal_with_assignment(client)
    _stub_ai_client(monkeypatch, response="今日の業務、お疲れさまでした")
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/work-chat",
        json={
            "goal_id": goal["id"],
            "work_logs": [{"work_assignment_id": work_assignment["id"], "body": "今日の業務内容"}],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assistant_message"]["content"] == "今日の業務、お疲れさまでした"
    assert body["assistant_message"]["purpose"] == "DAILY_FEEDBACK_WORK"
    # 「AIが参照した情報」表示用（2026-09-19）。仕事は教材を持たないためMATERIAL_PROGRESSは
    # 含まない（CONTEXT_CATEGORIES_BY_PURPOSE参照）。
    assert body["context_categories"] == ["GOAL_INFO", "TODAY_RECORD", "WEEKLY_SUMMARY"]
    # 業務記録は下書きのままDBへ確定されない（16.7と同じ保証）。
    assert body["record"]["work_logs"] == []


def test_work_chat_endpoint_persists_conversation_history_across_turns(client, monkeypatch):
    goal, _work_assignment = _make_active_work_goal_with_assignment(client)
    _stub_ai_client(monkeypatch, response="1回目の応答")
    target = dt.date.today().isoformat()

    client.post(f"/api/v1/records/{target}/work-chat", json={"goal_id": goal["id"]})

    _stub_ai_client(monkeypatch, response="2回目の応答")
    response = client.post(
        f"/api/v1/records/{target}/work-chat",
        json={"goal_id": goal["id"], "message": "続きを教えてください"},
    )

    assert response.status_code == 200, response.text
    record = client.get(f"/api/v1/records/{target}").json()
    work_messages = [m for m in record["chat_messages"] if m["purpose"] == "DAILY_FEEDBACK_WORK"]
    assert [m["role"] for m in work_messages] == ["ASSISTANT", "USER", "ASSISTANT"]


def test_work_chat_endpoint_rejects_future_date(client, monkeypatch):
    goal, _work_assignment = _make_active_work_goal_with_assignment(client)
    _stub_ai_client(monkeypatch)
    future = (dt.date.today() + dt.timedelta(days=1)).isoformat()

    response = client.post(f"/api/v1/records/{future}/work-chat", json={"goal_id": goal["id"]})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_work_chat_endpoint_maps_ai_error_and_keeps_input_recoverable(client, monkeypatch):
    from app.ai.exceptions import AiError

    goal, work_assignment = _make_active_work_goal_with_assignment(client)
    _stub_ai_client(monkeypatch, raise_exc=AiError("通信に失敗しました"))
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/work-chat",
        json={
            "goal_id": goal["id"],
            "work_logs": [
                {"work_assignment_id": work_assignment["id"], "body": "失われてはいけない業務内容"}
            ],
        },
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AI_ERROR"

    record = client.get(f"/api/v1/records/{target}").json()
    assert record["work_logs"] == []


# --- 前回の記録ヒント（記録画面改善タスク2026-09-17） ---


def test_get_previous_work_log_endpoint_returns_previous_entry(client):
    _goal, work_assignment = _make_active_work_goal_with_assignment(client)
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    target = dt.date.today().isoformat()
    client.post(
        f"/api/v1/records/{yesterday}/work-finalize",
        json={
            "work_logs": [{"work_assignment_id": work_assignment["id"], "body": "昨日の業務内容"}]
        },
    )

    response = client.get(
        f"/api/v1/records/{target}/previous-work-log?work_assignment_id={work_assignment['id']}"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["record_date"] == yesterday
    assert body["body"] == "昨日の業務内容"


# --- schedule_item_updates（開発Todo_スケジュール・ガントチャート_v1.1 D-32・D-35、単位4） ---


def _create_schedule_item(client, goal_id, **overrides):
    payload = {
        "title": "作業A",
        "planned_start_date": "2026-01-01",
        "planned_end_date": "2026-01-10",
        "status": "NOT_STARTED",
    }
    payload.update(overrides)
    response = client.put(
        f"/api/v1/goals/{goal_id}/schedule", json={"revision": 0, "items": [payload]}
    )
    assert response.status_code == 200, response.text
    return response.json()["items"][0]["id"]


def test_work_finalize_endpoint_applies_schedule_item_updates(client):
    """EXAM版（test_api_records_exam.py）・READING版（test_api_records_reading.py）に加えて
    WORKでも確認する（3種別すべてへの反映、重点確認事項）。"""
    goal, _work_assignment = _make_active_work_goal_with_assignment(client)
    item_id = _create_schedule_item(client, goal["id"])
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/work-finalize",
        json={
            "work_logs": [],
            "schedule_item_updates": [
                {
                    "schedule_item_id": item_id,
                    "status": "IN_PROGRESS",
                    "actual_start_date": target,
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    schedule = client.get(f"/api/v1/goals/{goal['id']}/schedule").json()
    assert schedule["items"][0]["status"] == "IN_PROGRESS"


def test_work_finalize_endpoint_rejects_schedule_item_from_different_category(client):
    goal, _work_assignment = _make_active_work_goal_with_assignment(client)
    reading_goal = client.post(
        "/api/v1/goals",
        json={"category": "READING", "name": "読書目標A", "start_date": "2026-01-01"},
    ).json()
    other_item_id = _create_schedule_item(client, reading_goal["id"])
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/work-finalize",
        json={
            "work_logs": [],
            "schedule_item_updates": [{"schedule_item_id": other_item_id, "status": "NOT_STARTED"}],
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
