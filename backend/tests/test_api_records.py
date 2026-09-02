"""日次記録APIのテスト（データ構造編6.2、仕様書6.4〜6.7・7.2章、
実装フェーズ分割計画書Phase4・Phase5）。

logical_date（1日の境界時刻を考慮した論理的な本日）は calendar.day_boundary_hour=0（初期値）
のため常にシステム日付と一致する。この前提のもと dt.date.today() を基準に相対日付でテストする。

POST /records/{date}/chat（Phase5）は実際のAI基盤へ接続せず、app.ai.client.send_message等を
モックして検証する。
"""

import datetime as dt

import pytest

from app.ai import client as ai_client
from app.ai import rate_limiter


def _create_goal_with_subject(client, exam_date_from="2026-06-01", exam_date_to="2026-06-10"):
    goal = client.post("/api/v1/goals", json={"name": "目標A", "start_date": "2026-01-01"}).json()
    client.post(
        f"/api/v1/goals/{goal['id']}/subjects",
        json={
            "name": "科目A",
            "exam_date_type": "RANGE",
            "exam_date_from": exam_date_from,
            "exam_date_to": exam_date_to,
        },
    )
    subject_id = client.get(f"/api/v1/goals/{goal['id']}").json()["exam_subjects"][0]["id"]
    return goal, subject_id


def _create_material(client, goal_id, subject_ids, **overrides):
    payload = {
        "name": "教材A",
        "unit_label": "ページ",
        "total_amount": 100,
        "planned_cycles": 1,
        "subject_ids": subject_ids,
        "start_date": "2026-01-01",
        "due_date_is_manual": True,
        "due_date": "2027-12-31",
    }
    payload.update(overrides)
    response = client.post(f"/api/v1/goals/{goal_id}/materials", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _make_active_goal_with_material(client, **material_overrides):
    goal, subject_id = _create_goal_with_subject(client)
    material = _create_material(client, goal["id"], [subject_id], **material_overrides)
    activated = client.post(f"/api/v1/goals/{goal['id']}/activate")
    assert activated.status_code == 200, activated.text
    return goal, material


# --- GET /records/today, GET /records/{date} ---


def test_get_today_returns_logical_date_and_null_state_when_not_entered(client):
    response = client.get("/api/v1/records/today")
    assert response.status_code == 200
    body = response.json()
    assert body["logical_date"] == dt.date.today().isoformat()
    assert body["record_state"] is None


def test_get_record_for_unentered_date_returns_empty_structure(client):
    target = dt.date.today().isoformat()
    response = client.get(f"/api/v1/records/{target}")
    assert response.status_code == 200
    body = response.json()
    assert body["record_state"] is None
    assert body["study_logs"] == []
    assert body["comments"] == []
    assert body["diary_body"] is None


# --- POST /records/{date}/progress ---


def test_register_progress_endpoint_creates_progress_only_record(client):
    _goal, material = _make_active_goal_with_material(client)
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/progress",
        json={
            "study_logs": [
                {"material_id": material["id"], "minutes_spent": 30, "amount_completed": 10}
            ]
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["record_state"] == "PROGRESS_ONLY"
    assert len(body["study_logs"]) == 1
    assert body["study_logs"][0]["cycle_number"] == 1


def test_register_progress_endpoint_rejects_future_date(client):
    _goal, material = _make_active_goal_with_material(client)
    future = (dt.date.today() + dt.timedelta(days=1)).isoformat()

    response = client.post(
        f"/api/v1/records/{future}/progress",
        json={
            "study_logs": [
                {"material_id": material["id"], "minutes_spent": 30, "amount_completed": 10}
            ]
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_register_progress_endpoint_rejects_unknown_material(client):
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/progress",
        json={"study_logs": [{"material_id": 9999, "minutes_spent": 30, "amount_completed": 10}]},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# --- POST /records/{date}/finalize ---


def test_finalize_endpoint_marks_reported_and_reflects_in_today(client):
    _goal, material = _make_active_goal_with_material(client)
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/finalize",
        json={
            "study_logs": [
                {"material_id": material["id"], "minutes_spent": 30, "amount_completed": 10}
            ],
            "diary_body": "今日はよく頑張った",
            "diary_learned": "過去問を解いた",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["record_state"] == "REPORTED"
    assert body["diary_body"] == "今日はよく頑張った"

    today_response = client.get("/api/v1/records/today")
    assert today_response.json()["record_state"] == "REPORTED"


def test_finalize_endpoint_rejects_backdate_beyond_yesterday(client):
    two_days_ago = (dt.date.today() - dt.timedelta(days=2)).isoformat()

    response = client.post(
        f"/api/v1/records/{two_days_ago}/finalize",
        json={"study_logs": [], "diary_body": "所感", "diary_learned": "学び"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BACKDATE_LIMIT_EXCEEDED"


def test_finalize_endpoint_rejects_update_after_reported(client):
    target = dt.date.today().isoformat()
    client.post(
        f"/api/v1/records/{target}/finalize",
        json={"study_logs": [], "diary_body": "所感", "diary_learned": "学び"},
    )

    response = client.post(
        f"/api/v1/records/{target}/finalize",
        json={"study_logs": [], "diary_body": "上書き", "diary_learned": "上書き"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IMMUTABLE_RECORD"


def test_progress_endpoint_rejects_update_after_reported(client):
    _goal, material = _make_active_goal_with_material(client)
    target = dt.date.today().isoformat()
    client.post(
        f"/api/v1/records/{target}/finalize",
        json={"study_logs": [], "diary_body": "所感", "diary_learned": "学び"},
    )

    response = client.post(
        f"/api/v1/records/{target}/progress",
        json={
            "study_logs": [
                {"material_id": material["id"], "minutes_spent": 30, "amount_completed": 10}
            ]
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IMMUTABLE_RECORD"


# --- 読書記録（reading_logs。実装フェーズ分割計画書Phase15） ---


def _make_active_reading_goal_with_book(client):
    goal = client.post(
        "/api/v1/goals",
        json={"category": "READING", "name": "読書目標A", "start_date": "2026-01-01"},
    ).json()
    book = client.post(
        f"/api/v1/goals/{goal['id']}/book",
        json={"title": "書籍A", "start_date": "2026-01-01", "due_date": "2026-12-31"},
    ).json()
    activated = client.post(f"/api/v1/goals/{goal['id']}/activate")
    assert activated.status_code == 200, activated.text
    return goal, book


def test_register_progress_endpoint_accepts_reading_only(client):
    """study_logsが空でもreading_logsのみで進捗のみ登録ができる（要件定義書R-65）。"""
    _goal, book = _make_active_reading_goal_with_book(client)
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/progress",
        json={
            "reading_logs": [
                {"book_id": book["id"], "recall_body": "今日読んだ内容の想起", "pages_read": 10}
            ]
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["record_state"] == "PROGRESS_ONLY"
    assert body["study_logs"] == []
    assert len(body["reading_logs"]) == 1
    assert body["reading_logs"][0]["recall_body"] == "今日読んだ内容の想起"


def test_register_progress_endpoint_rejects_both_lists_empty(client):
    target = dt.date.today().isoformat()

    response = client.post(f"/api/v1/records/{target}/progress", json={})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_finalize_endpoint_persists_reading_log(client):
    _goal, book = _make_active_reading_goal_with_book(client)
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/finalize",
        json={
            "reading_logs": [{"book_id": book["id"], "recall_body": "読了に向けた想起"}],
            "diary_body": "所感",
            "diary_learned": "学び",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["record_state"] == "REPORTED"
    assert len(body["reading_logs"]) == 1

    fetched = client.get(f"/api/v1/records/{target}").json()
    assert fetched["reading_logs"][0]["recall_body"] == "読了に向けた想起"


def test_register_progress_endpoint_rejects_unknown_book(client):
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/progress",
        json={"reading_logs": [{"book_id": 9999, "recall_body": "想起"}]},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_reading_log_recall_body_is_required(client):
    _goal, book = _make_active_reading_goal_with_book(client)
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/progress",
        json={"reading_logs": [{"book_id": book["id"], "recall_body": ""}]},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --- GET /records/{date}/quota ---


def test_quota_endpoint_returns_items_for_active_goal_material(client):
    _goal, material = _make_active_goal_with_material(
        client, total_amount=100, planned_cycles=1, quality_metric_type="OBJECTIVE"
    )
    target = dt.date.today().isoformat()

    response = client.get(f"/api/v1/records/{target}/quota")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["material_id"] == material["id"]
    assert body[0]["current_cycle"] == 1
    # unit_label・quality_metric_type はSC-06/SC-07の実績入力欄（単位表示・品質指標の
    # 入力形式切替）に必要なため、レスポンスに含まれることを確認する（仕様書6.5）。
    assert body[0]["unit_label"] == "ページ"
    assert body[0]["quality_metric_type"] == "OBJECTIVE"


# --- コメント ---


def test_comment_create_update_delete_flow(client):
    target = dt.date.today().isoformat()
    client.post(
        f"/api/v1/records/{target}/finalize",
        json={"study_logs": [], "diary_body": "所感", "diary_learned": "学び"},
    )

    created = client.post(f"/api/v1/records/{target}/comments", json={"body": "初回コメント"})
    assert created.status_code == 201, created.text
    comment_id = created.json()["id"]

    updated = client.patch(f"/api/v1/comments/{comment_id}", json={"body": "修正後コメント"})
    assert updated.status_code == 200
    assert updated.json()["body"] == "修正後コメント"

    record = client.get(f"/api/v1/records/{target}").json()
    assert record["comments"][0]["body"] == "修正後コメント"

    deleted = client.delete(f"/api/v1/comments/{comment_id}")
    assert deleted.status_code == 204

    record_after_delete = client.get(f"/api/v1/records/{target}").json()
    assert record_after_delete["comments"] == []


def test_comment_create_for_unentered_date_returns_404(client):
    target = dt.date.today().isoformat()
    response = client.post(f"/api/v1/records/{target}/comments", json={"body": "コメント"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_update_missing_comment_returns_404(client):
    response = client.patch("/api/v1/comments/9999", json={"body": "x"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# --- POST /records/{date}/chat（Phase5） ---


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
        ai_client, "create_chat", lambda session, *, assistant_uid, title: "chat-uid-api"
    )
    monkeypatch.setattr(
        ai_client,
        "create_chat_in_folder_by_name",
        lambda session, *, assistant_uid, folder_name, title: "chat-uid-api",
    )


def test_chat_endpoint_returns_assistant_message(client, monkeypatch):
    _make_active_goal_with_material(client)
    _stub_ai_client(monkeypatch, response="今日もよく頑張りましたね")
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/chat",
        json={"diary_body": "今日は頑張った", "diary_learned": "過去問を解いた"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assistant_message"]["content"] == "今日もよく頑張りましたね"
    assert body["assistant_message"]["role"] == "ASSISTANT"
    assert body["was_truncated"] is False
    # 実績・日記は下書きのままDBへ確定されない（16.7、Phase5完了条件）。
    assert body["record"]["study_logs"] == []
    assert body["record"]["diary_body"] is None


def test_chat_endpoint_persists_conversation_history_across_turns(client, monkeypatch):
    _make_active_goal_with_material(client)
    _stub_ai_client(monkeypatch, response="1回目の応答")
    target = dt.date.today().isoformat()

    client.post(f"/api/v1/records/{target}/chat", json={})

    _stub_ai_client(monkeypatch, response="2回目の応答")
    response = client.post(
        f"/api/v1/records/{target}/chat", json={"message": "続きを教えてください"}
    )

    assert response.status_code == 200, response.text
    record = client.get(f"/api/v1/records/{target}").json()
    roles = [m["role"] for m in record["chat_messages"]]
    assert roles == ["ASSISTANT", "USER", "ASSISTANT"]


def test_chat_endpoint_rejects_future_date(client, monkeypatch):
    _make_active_goal_with_material(client)
    _stub_ai_client(monkeypatch)
    future = (dt.date.today() + dt.timedelta(days=1)).isoformat()

    response = client.post(f"/api/v1/records/{future}/chat", json={})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_chat_endpoint_maps_ai_error_and_keeps_input_recoverable(client, monkeypatch):
    """AI呼び出しが失敗しても実績入力が失われない（16.7、Phase5完了条件）。
    サーバ側で下書きを保持しないため、失敗時にDBへ何も確定されないことを確認する。
    """
    from app.ai.exceptions import AiError

    _make_active_goal_with_material(client)
    _stub_ai_client(monkeypatch, raise_exc=AiError("通信に失敗しました"))
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/chat",
        json={"diary_body": "失われてはいけない", "diary_learned": "失われてはいけない"},
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AI_ERROR"

    record = client.get(f"/api/v1/records/{target}").json()
    assert record["study_logs"] == []
    assert record["diary_body"] is None


def test_chat_endpoint_maps_ai_auth_required_error(client, monkeypatch):
    from app.ai.exceptions import AiAuthRequiredError

    _make_active_goal_with_material(client)
    _stub_ai_client(monkeypatch, raise_exc=AiAuthRequiredError("認証が必要です"))
    target = dt.date.today().isoformat()

    response = client.post(f"/api/v1/records/{target}/chat", json={})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AI_AUTH_REQUIRED"


# --- POST /records/{date}/reading-chat（実装フェーズ分割計画書Phase16） ---


def test_reading_chat_endpoint_returns_assistant_message(client, monkeypatch):
    _goal, book = _make_active_reading_goal_with_book(client)
    _stub_ai_client(monkeypatch, response="想起を深める応答")
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/reading-chat",
        json={"reading_logs": [{"book_id": book["id"], "recall_body": "今日の想起"}]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assistant_message"]["content"] == "想起を深める応答"
    assert body["assistant_message"]["purpose"] == "DAILY_FEEDBACK_READING"
    # 想起は下書きのままDBへ確定されない（16.7と同じ保証）。
    assert body["record"]["reading_logs"] == []


def test_reading_chat_endpoint_persists_conversation_history_across_turns(client, monkeypatch):
    _goal, book = _make_active_reading_goal_with_book(client)
    _stub_ai_client(monkeypatch, response="1回目の応答")
    target = dt.date.today().isoformat()

    client.post(f"/api/v1/records/{target}/reading-chat", json={})

    _stub_ai_client(monkeypatch, response="2回目の応答")
    response = client.post(
        f"/api/v1/records/{target}/reading-chat", json={"message": "続きを教えてください"}
    )

    assert response.status_code == 200, response.text
    record = client.get(f"/api/v1/records/{target}").json()
    reading_messages = [
        m for m in record["chat_messages"] if m["purpose"] == "DAILY_FEEDBACK_READING"
    ]
    assert [m["role"] for m in reading_messages] == ["ASSISTANT", "USER", "ASSISTANT"]


def test_reading_chat_endpoint_rejects_future_date(client, monkeypatch):
    _make_active_reading_goal_with_book(client)
    _stub_ai_client(monkeypatch)
    future = (dt.date.today() + dt.timedelta(days=1)).isoformat()

    response = client.post(f"/api/v1/records/{future}/reading-chat", json={})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_reading_chat_endpoint_maps_ai_error_and_keeps_input_recoverable(client, monkeypatch):
    from app.ai.exceptions import AiError

    _goal, book = _make_active_reading_goal_with_book(client)
    _stub_ai_client(monkeypatch, raise_exc=AiError("通信に失敗しました"))
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/reading-chat",
        json={"reading_logs": [{"book_id": book["id"], "recall_body": "失われてはいけない想起"}]},
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AI_ERROR"

    record = client.get(f"/api/v1/records/{target}").json()
    assert record["reading_logs"] == []
