"""日次記録APIのテストのうち読書（READING）固有のエンドポイント（データ構造編6.2、
仕様書6.4〜6.7・7.2章、実装フェーズ分割計画書Phase15・Phase16・S02）。共通処理・カテゴリ横断の
相互独立性のテストはtest_api_records_common.pyを参照（実装フェーズ分割計画書S02、
test_api_records.pyからの分割）。
"""

import datetime as dt

import pytest

from app.ai import client as ai_client
from app.ai import rate_limiter


def _make_active_reading_goal_with_book(client):
    goal = client.post(
        "/api/v1/goals",
        json={"category": "READING", "name": "読書目標A", "start_date": "2026-01-01"},
    ).json()
    book = client.post(
        f"/api/v1/goals/{goal['id']}/book",
        json={
            "title": "書籍A",
            "total_pages": 300,
            "start_date": "2026-01-01",
            "due_date": "2026-12-31",
        },
    ).json()
    activated = client.post(f"/api/v1/goals/{goal['id']}/activate")
    assert activated.status_code == 200, activated.text
    return goal, book


# --- 読書記録（reading_logs。実装フェーズ分割計画書Phase15） ---


def test_register_progress_endpoint_accepts_reading_only(client):
    """study_logsが空でもreading_logsのみで進捗のみ登録ができる（要件定義書R-65）。"""
    _goal, book = _make_active_reading_goal_with_book(client)
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/progress",
        json={
            "reading_logs": [
                {"book_id": book["id"], "recall_body": "今日読んだ内容の想起", "current_page": 10}
            ]
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["reading_record_state"] == "PROGRESS_ONLY"
    assert body["exam_record_state"] is None
    assert body["study_logs"] == []
    assert len(body["reading_logs"]) == 1
    assert body["reading_logs"][0]["recall_body"] == "今日読んだ内容の想起"


def test_register_progress_endpoint_rejects_current_page_over_total_pages(client):
    """現在ページが総ページ数を超える場合、画面で理由が分かる専用エラーコードを返す
    （日次報告の送信はボタンのクリックであり、入力欄のmax属性では止まらないため）。"""
    _goal, book = _make_active_reading_goal_with_book(client)
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/progress",
        json={
            "reading_logs": [
                {"book_id": book["id"], "recall_body": "今日読んだ内容の想起", "current_page": 301}
            ]
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "CURRENT_PAGE_EXCEEDS_TOTAL_PAGES"


def test_finalize_reading_endpoint_persists_reading_log(client):
    """読書の確定は/reading-finalize（EXAMの/finalizeとは独立、仕様変更2026-09-05）。"""
    _goal, book = _make_active_reading_goal_with_book(client)
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/reading-finalize",
        json={"reading_logs": [{"book_id": book["id"], "recall_body": "読了に向けた想起"}]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["reading_record_state"] == "REPORTED"
    assert body["exam_record_state"] is None
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


# --- POST /records/{date}/reading-chat（実装フェーズ分割計画書Phase16） ---


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


def test_reading_chat_endpoint_returns_assistant_message(client, monkeypatch):
    goal, book = _make_active_reading_goal_with_book(client)
    _stub_ai_client(monkeypatch, response="想起を深める応答")
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/reading-chat",
        json={
            "goal_id": goal["id"],
            "reading_logs": [{"book_id": book["id"], "recall_body": "今日の想起"}],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assistant_message"]["content"] == "想起を深める応答"
    assert body["assistant_message"]["purpose"] == "DAILY_FEEDBACK_READING"
    # 「AIが参照した情報」表示用（2026-09-19）。読書は教材を持たないためMATERIAL_PROGRESSは
    # 含まない（CONTEXT_CATEGORIES_BY_PURPOSE参照）。
    assert body["context_categories"] == ["GOAL_INFO", "TODAY_RECORD", "WEEKLY_SUMMARY"]
    # 想起は下書きのままDBへ確定されない（16.7と同じ保証）。
    assert body["record"]["reading_logs"] == []


def test_reading_chat_endpoint_persists_conversation_history_across_turns(client, monkeypatch):
    goal, _book = _make_active_reading_goal_with_book(client)
    _stub_ai_client(monkeypatch, response="1回目の応答")
    target = dt.date.today().isoformat()

    client.post(f"/api/v1/records/{target}/reading-chat", json={"goal_id": goal["id"]})

    _stub_ai_client(monkeypatch, response="2回目の応答")
    response = client.post(
        f"/api/v1/records/{target}/reading-chat",
        json={"goal_id": goal["id"], "message": "続きを教えてください"},
    )

    assert response.status_code == 200, response.text
    record = client.get(f"/api/v1/records/{target}").json()
    reading_messages = [
        m for m in record["chat_messages"] if m["purpose"] == "DAILY_FEEDBACK_READING"
    ]
    assert [m["role"] for m in reading_messages] == ["ASSISTANT", "USER", "ASSISTANT"]


def test_reading_chat_endpoint_rejects_future_date(client, monkeypatch):
    goal, _book = _make_active_reading_goal_with_book(client)
    _stub_ai_client(monkeypatch)
    future = (dt.date.today() + dt.timedelta(days=1)).isoformat()

    response = client.post(f"/api/v1/records/{future}/reading-chat", json={"goal_id": goal["id"]})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_reading_chat_endpoint_maps_ai_error_and_keeps_input_recoverable(client, monkeypatch):
    from app.ai.exceptions import AiError

    goal, book = _make_active_reading_goal_with_book(client)
    _stub_ai_client(monkeypatch, raise_exc=AiError("通信に失敗しました"))
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/reading-chat",
        json={
            "goal_id": goal["id"],
            "reading_logs": [{"book_id": book["id"], "recall_body": "失われてはいけない想起"}],
        },
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AI_ERROR"

    record = client.get(f"/api/v1/records/{target}").json()
    assert record["reading_logs"] == []


# --- 前回の記録ヒント（記録画面改善タスク2026-09-17） ---


def test_get_previous_reading_log_endpoint_returns_previous_entry(client):
    _goal, book = _make_active_reading_goal_with_book(client)
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    target = dt.date.today().isoformat()
    client.post(
        f"/api/v1/records/{yesterday}/reading-finalize",
        json={"reading_logs": [{"book_id": book["id"], "recall_body": "昨日の想起"}]},
    )

    response = client.get(f"/api/v1/records/{target}/previous-reading-log?book_id={book['id']}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["record_date"] == yesterday
    assert body["body"] == "昨日の想起"
