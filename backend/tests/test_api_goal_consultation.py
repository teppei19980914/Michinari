"""目標相談チャットのAPIのテスト（S09、要件定義書R-104、開発Todo B-06・B-08）。

AI基盤へは接続せず、app.ai.client の通信関数を差し替える。API層の責務（リクエストの受け付け、
ステータスと応答形式、ドメイン例外のHTTP変換、資格以外の目標での拒否）を確かめる
（test_api_help_assistant.pyと同じ方針）。
"""

import datetime as dt

import pytest

from app.ai import client as ai_client
from app.ai import rate_limiter
from app.constants.app_setting_keys import AI_GOAL_CONSULTATION_QUESTION_MAX_CHARS
from app.constants.enums import GoalCategory, GoalStatus
from app.models.goal import Goal
from app.models.setting import AppSetting

_DEFAULT_RESPONSE = (
    "## 記録から言えること\n記録からはまだ判断できません。\n"
    "## 一般的な助言\n基礎から復習しましょう。\n[根拠: なし]"
)


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


@pytest.fixture
def exam_goal(seeded_session):
    goal = Goal(name="資格目標", start_date=dt.date(2026, 1, 1), status=GoalStatus.ACTIVE)
    seeded_session.add(goal)
    seeded_session.commit()
    return goal


@pytest.fixture
def reading_goal(seeded_session):
    goal = Goal(
        name="読書目標",
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
        category=GoalCategory.READING,
    )
    seeded_session.add(goal)
    seeded_session.commit()
    return goal


@pytest.fixture
def fake_ai(monkeypatch):
    monkeypatch.setattr(ai_client, "is_authenticated", lambda session: True)
    monkeypatch.setattr(
        ai_client, "create_chat_in_folder_by_name", lambda *args, **kwargs: "chat-1"
    )
    monkeypatch.setattr(
        ai_client,
        "send_message",
        lambda session, *, chat_uid, message: ai_client.SendResult(
            response_text=_DEFAULT_RESPONSE, latency_ms=1
        ),
    )
    monkeypatch.setattr(ai_client, "delete_chat", lambda session, *, chat_uid: None)
    monkeypatch.setattr(ai_client, "chat_listed_in_folder", lambda session, **kwargs: False)


def test_post_question_returns_answer(client, exam_goal, fake_ai):
    response = client.post(
        f"/api/v1/goals/{exam_goal.id}/consultation/questions",
        json={"question": "この後どのような分野の勉強が必要ですか？"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ANSWERED"
    assert "記録からはまだ判断できません" in body["answer"]
    assert body["cited_dates"] == []
    assert body["cited_weeks"] == []


def test_post_question_on_reading_goal_is_rejected(client, reading_goal, fake_ai):
    """資格以外の目標では使えない（開発Todo U7、API直叩きの拒否）。"""
    response = client.post(
        f"/api/v1/goals/{reading_goal.id}/consultation/questions",
        json={"question": "この後何を読むべきですか？"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_post_question_on_missing_goal_returns_not_found(client, fake_ai):
    response = client.post(
        "/api/v1/goals/999999/consultation/questions", json={"question": "質問です"}
    )

    assert response.status_code == 404


def test_post_empty_question_is_rejected(client, exam_goal, fake_ai):
    response = client.post(
        f"/api/v1/goals/{exam_goal.id}/consultation/questions", json={"question": "   "}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_post_over_long_question_is_rejected(client, exam_goal, fake_ai):
    response = client.post(
        f"/api/v1/goals/{exam_goal.id}/consultation/questions", json={"question": "あ" * 301}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_post_question_without_ai_connection_returns_auth_error(client, exam_goal, monkeypatch):
    monkeypatch.setattr(ai_client, "is_authenticated", lambda session: False)

    response = client.post(
        f"/api/v1/goals/{exam_goal.id}/consultation/questions", json={"question": "質問です"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AI_AUTH_REQUIRED"


def test_post_question_when_ai_call_fails_returns_error_code(client, exam_goal, monkeypatch):
    from app.ai.exceptions import AiError

    monkeypatch.setattr(ai_client, "is_authenticated", lambda session: True)
    monkeypatch.setattr(
        ai_client, "create_chat_in_folder_by_name", lambda *args, **kwargs: "chat-1"
    )

    def failing_send(session, *, chat_uid, message):
        raise AiError("通信に失敗しました")

    monkeypatch.setattr(ai_client, "send_message", failing_send)
    monkeypatch.setattr(ai_client, "delete_chat", lambda session, *, chat_uid: None)
    monkeypatch.setattr(ai_client, "chat_listed_in_folder", lambda session, **kwargs: False)

    response = client.post(
        f"/api/v1/goals/{exam_goal.id}/consultation/questions", json={"question": "質問です"}
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AI_ERROR"


def test_get_limits_returns_question_limit(client, exam_goal, seeded_session):
    response = client.get(f"/api/v1/goals/{exam_goal.id}/consultation/limits")

    assert response.status_code == 200
    assert response.json() == {"max_question_chars": 300}


def test_get_limits_reflects_app_setting(client, exam_goal, seeded_session):
    row = (
        seeded_session.query(AppSetting)
        .filter(AppSetting.key == AI_GOAL_CONSULTATION_QUESTION_MAX_CHARS)
        .one()
    )
    row.value = "120"
    seeded_session.commit()

    response = client.get(f"/api/v1/goals/{exam_goal.id}/consultation/limits")

    assert response.json() == {"max_question_chars": 120}


def test_get_limits_on_missing_goal_returns_not_found(client):
    response = client.get("/api/v1/goals/999999/consultation/limits")

    assert response.status_code == 404
