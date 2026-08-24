"""AI連携APIのテスト（データ構造編6.2、実装フェーズ分割計画書Phase5）。

実際のAI基盤へは接続せず、app.ai.client / app.ai.auth をモックして検証する。
"""

import pytest

from app.ai import auth as ai_auth
from app.ai import client as ai_client
from app.ai import rate_limiter


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


# --- GET /ai/status ---


def test_get_ai_status_returns_authenticated_state(client, monkeypatch):
    monkeypatch.setattr(ai_client, "is_authenticated", lambda session: True)
    monkeypatch.setattr(ai_client, "get_model_status", lambda session: {"gpt-5": True})

    response = client.get("/api/v1/ai/status")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "authenticated": True,
        "model_status": {"gpt-5": True},
        "login_in_progress": False,
    }


def test_get_ai_status_when_unauthenticated(client, monkeypatch):
    monkeypatch.setattr(ai_client, "is_authenticated", lambda session: False)

    response = client.get("/api/v1/ai/status")

    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is False
    assert body["model_status"] == {}


# --- POST /ai/login ---


def test_login_with_pat_registers_and_returns_authenticated(client, monkeypatch):
    monkeypatch.setattr(
        ai_auth, "register_pat", lambda session, *, host, personal_access_token: True
    )

    response = client.post(
        "/api/v1/ai/login",
        json={"host": "example.newton-x.net", "personal_access_token": "1|abcdef"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "AUTHENTICATED", "authenticated": True}


def test_login_without_pat_starts_fallback_login(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        ai_auth, "start_fallback_login", lambda session: calls.append(session) or True
    )

    response = client.post("/api/v1/ai/login", json={})

    assert response.status_code == 200
    assert response.json() == {"status": "PENDING", "authenticated": False}
    assert len(calls) == 1


# --- POST /ai/logout ---


def test_logout_calls_ai_auth_logout(client, monkeypatch):
    calls = []
    monkeypatch.setattr(ai_auth, "logout", lambda session: calls.append(session))

    response = client.post("/api/v1/ai/logout")

    assert response.status_code == 204
    assert len(calls) == 1


# --- GET /ai/assistants ---


def test_get_assistants_returns_extracted_fields(client, monkeypatch):
    monkeypatch.setattr(
        ai_client,
        "get_assistants",
        lambda session: [
            {"uid": "a1", "name": "アシスタントA", "description": "説明A", "extra": "無視される"},
            {"uid": "a2", "name": "アシスタントB"},
        ],
    )

    response = client.get("/api/v1/ai/assistants")

    assert response.status_code == 200
    body = response.json()
    assert body == [
        {"uid": "a1", "name": "アシスタントA", "description": "説明A"},
        {"uid": "a2", "name": "アシスタントB", "description": None},
    ]


# --- GET /daily-message ---


def test_get_daily_message_generates_on_first_call(client, monkeypatch):
    calls = []

    def _fake_send_message(session, *, chat_uid, message):
        calls.append(message)
        return ai_client.SendResult(response_text="今日も一歩前進しましょう", latency_ms=10)

    monkeypatch.setattr(ai_client, "send_message", _fake_send_message)
    monkeypatch.setattr(
        ai_client, "create_chat", lambda session, *, assistant_uid, title: "chat-uid-msg"
    )

    response = client.get("/api/v1/daily-message")

    assert response.status_code == 200
    assert response.json()["body"] == "今日も一歩前進しましょう"
    assert len(calls) == 1


def test_get_daily_message_does_not_regenerate_same_day(client, monkeypatch):
    call_count = {"n": 0}

    def _fake_send_message(session, *, chat_uid, message):
        call_count["n"] += 1
        return ai_client.SendResult(response_text="一言", latency_ms=10)

    monkeypatch.setattr(ai_client, "send_message", _fake_send_message)
    monkeypatch.setattr(
        ai_client, "create_chat", lambda session, *, assistant_uid, title: "chat-uid-msg"
    )

    first = client.get("/api/v1/daily-message")
    second = client.get("/api/v1/daily-message")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["generated_at"] == second.json()["generated_at"]
    assert call_count["n"] == 1
