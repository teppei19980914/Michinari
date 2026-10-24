"""目標相談チャットのAPIのテスト（S09で導入・S10で読書・仕事へ展開＋履歴API追加、
S11で会話継続の会話系APIを追加、要件定義書R-104、開発Todo v1.1 B-06・v1.2 B-07）。

AI基盤へは接続せず、app.ai.client の通信関数を差し替える。API層の責務（リクエストの受け付け、
ステータスと応答形式、ドメイン例外のHTTP変換、相談履歴の一覧/削除、会話の作成/一覧/削除）を
確かめる（test_api_help_assistant.pyと同じ方針）。カテゴリ別の変数組み立ての中身は
test_goal_consultation_service_exam/_reading/_work.pyで検証済みのため、ここではAPIが
EXAM・READING・WORKのいずれでも受理されることだけを確認する（CODING_RULES.md DRYの原則）。
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
def work_goal(seeded_session):
    goal = Goal(
        name="仕事目標",
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
        category=GoalCategory.WORK,
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


def _create_conversation(client, goal_id, title=""):
    """会話を1件作り、idを返す（S11、開発Todo v1.2 W7）。"""
    response = client.post(
        f"/api/v1/goals/{goal_id}/consultation/conversations", json={"title": title}
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_post_question_returns_answer(client, exam_goal, fake_ai):
    conversation_id = _create_conversation(client, exam_goal.id)

    response = client.post(
        f"/api/v1/goals/{exam_goal.id}/consultation/questions",
        json={
            "conversation_id": conversation_id,
            "question": "この後どのような分野の勉強が必要ですか？",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ANSWERED"
    assert "記録からはまだ判断できません" in body["answer"]
    assert body["cited_dates"] == []
    assert body["cited_weeks"] == []


def test_post_question_on_reading_goal_is_accepted(client, reading_goal, fake_ai):
    """S10でEXAM専用ガードを撤廃し、READINGでも使える（開発Todo v1.1 V1）。"""
    conversation_id = _create_conversation(client, reading_goal.id)

    response = client.post(
        f"/api/v1/goals/{reading_goal.id}/consultation/questions",
        json={"conversation_id": conversation_id, "question": "この後何を読むべきですか？"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ANSWERED"


def test_post_question_on_missing_goal_returns_not_found(client, fake_ai):
    response = client.post(
        "/api/v1/goals/999999/consultation/questions",
        json={"conversation_id": 1, "question": "質問です"},
    )

    assert response.status_code == 404


def test_post_question_with_conversation_from_another_goal_returns_not_found(
    client, exam_goal, reading_goal, fake_ai
):
    """他目標の会話は、goal_idが一致しないため使えない（認可境界、開発Todo v1.2 §5）。"""
    conversation_id = _create_conversation(client, reading_goal.id)

    response = client.post(
        f"/api/v1/goals/{exam_goal.id}/consultation/questions",
        json={"conversation_id": conversation_id, "question": "質問です"},
    )

    assert response.status_code == 404


def test_post_empty_question_is_rejected(client, exam_goal, fake_ai):
    conversation_id = _create_conversation(client, exam_goal.id)

    response = client.post(
        f"/api/v1/goals/{exam_goal.id}/consultation/questions",
        json={"conversation_id": conversation_id, "question": "   "},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_post_over_long_question_is_rejected(client, exam_goal, fake_ai):
    conversation_id = _create_conversation(client, exam_goal.id)

    response = client.post(
        f"/api/v1/goals/{exam_goal.id}/consultation/questions",
        json={"conversation_id": conversation_id, "question": "あ" * 301},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_post_question_without_ai_connection_returns_auth_error(client, exam_goal, monkeypatch):
    conversation_id = _create_conversation(client, exam_goal.id)
    monkeypatch.setattr(ai_client, "is_authenticated", lambda session: False)

    response = client.post(
        f"/api/v1/goals/{exam_goal.id}/consultation/questions",
        json={"conversation_id": conversation_id, "question": "質問です"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AI_AUTH_REQUIRED"


def test_post_question_when_ai_call_fails_returns_error_code(client, exam_goal, monkeypatch):
    from app.ai.exceptions import AiError

    conversation_id = _create_conversation(client, exam_goal.id)
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
        f"/api/v1/goals/{exam_goal.id}/consultation/questions",
        json={"conversation_id": conversation_id, "question": "質問です"},
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


def test_post_question_on_work_goal_is_accepted(client, work_goal, fake_ai):
    """S10でEXAM専用ガードを撤廃し、WORKでも使える（開発Todo v1.1 V1）。"""
    conversation_id = _create_conversation(client, work_goal.id)

    response = client.post(
        f"/api/v1/goals/{work_goal.id}/consultation/questions",
        json={"conversation_id": conversation_id, "question": "最近の課題の傾向は？"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ANSWERED"


# --- 会話（S11、開発Todo v1.2 W7） ---


def test_post_conversation_creates_with_title(client, exam_goal):
    response = client.post(
        f"/api/v1/goals/{exam_goal.id}/consultation/conversations", json={"title": "科目Aの相談"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "科目Aの相談"
    assert "created_at" in body


def test_post_conversation_defaults_title_to_empty(client, exam_goal):
    response = client.post(f"/api/v1/goals/{exam_goal.id}/consultation/conversations", json={})

    assert response.status_code == 201
    assert response.json()["title"] == ""


def test_post_conversation_on_missing_goal_returns_not_found(client):
    response = client.post("/api/v1/goals/999999/consultation/conversations", json={})

    assert response.status_code == 404


def test_get_conversations_returns_created_entries_in_order(client, exam_goal):
    _create_conversation(client, exam_goal.id, title="最初の相談")
    _create_conversation(client, exam_goal.id, title="2回目の相談")

    response = client.get(f"/api/v1/goals/{exam_goal.id}/consultation/conversations")

    assert response.status_code == 200
    titles = [item["title"] for item in response.json()]
    assert titles == ["最初の相談", "2回目の相談"]


def test_get_conversations_excludes_other_goals(client, exam_goal, reading_goal):
    _create_conversation(client, exam_goal.id, title="資格の相談")
    _create_conversation(client, reading_goal.id, title="読書の相談")

    response = client.get(f"/api/v1/goals/{exam_goal.id}/consultation/conversations")

    assert [item["title"] for item in response.json()] == ["資格の相談"]


def test_delete_conversation_removes_it(client, exam_goal):
    conversation_id = _create_conversation(client, exam_goal.id)

    response = client.delete(
        f"/api/v1/goals/{exam_goal.id}/consultation/conversations/{conversation_id}"
    )

    assert response.status_code == 204
    assert client.get(f"/api/v1/goals/{exam_goal.id}/consultation/conversations").json() == []


def test_delete_conversation_cascades_removes_history(client, exam_goal, fake_ai):
    conversation_id = _create_conversation(client, exam_goal.id)
    client.post(
        f"/api/v1/goals/{exam_goal.id}/consultation/questions",
        json={"conversation_id": conversation_id, "question": "質問"},
    )

    response = client.delete(
        f"/api/v1/goals/{exam_goal.id}/consultation/conversations/{conversation_id}"
    )

    assert response.status_code == 204
    assert client.get(f"/api/v1/goals/{exam_goal.id}/consultation/history").json() == []


def test_delete_conversation_on_another_goal_returns_not_found(client, exam_goal, reading_goal):
    """他目標の会話は削除できない（認可境界、開発Todo v1.2 §5）。"""
    conversation_id = _create_conversation(client, exam_goal.id)

    response = client.delete(
        f"/api/v1/goals/{reading_goal.id}/consultation/conversations/{conversation_id}"
    )

    assert response.status_code == 404


def test_delete_conversation_on_missing_id_returns_not_found(client, exam_goal):
    response = client.delete(
        f"/api/v1/goals/{exam_goal.id}/consultation/conversations/999999"
    )

    assert response.status_code == 404


# --- 相談履歴（S10、開発Todo v1.1 V7） ---


def test_get_history_returns_saved_entries_in_order(client, exam_goal, fake_ai):
    conversation_id = _create_conversation(client, exam_goal.id)
    client.post(
        f"/api/v1/goals/{exam_goal.id}/consultation/questions",
        json={"conversation_id": conversation_id, "question": "質問1"},
    )
    client.post(
        f"/api/v1/goals/{exam_goal.id}/consultation/questions",
        json={"conversation_id": conversation_id, "question": "質問2"},
    )

    response = client.get(f"/api/v1/goals/{exam_goal.id}/consultation/history")

    assert response.status_code == 200
    body = response.json()
    assert [item["question"] for item in body] == ["質問1", "質問2"]
    assert body[0]["conversation_id"] == conversation_id
    assert body[0]["status"] == "ANSWERED"
    assert body[0]["cited_dates"] == []
    assert body[0]["cited_weeks"] == []
    assert "created_at" in body[0]


def test_get_history_excludes_other_goals(client, exam_goal, reading_goal, fake_ai):
    exam_conversation_id = _create_conversation(client, exam_goal.id)
    reading_conversation_id = _create_conversation(client, reading_goal.id)
    client.post(
        f"/api/v1/goals/{exam_goal.id}/consultation/questions",
        json={"conversation_id": exam_conversation_id, "question": "資格の質問"},
    )
    client.post(
        f"/api/v1/goals/{reading_goal.id}/consultation/questions",
        json={"conversation_id": reading_conversation_id, "question": "読書の質問"},
    )

    response = client.get(f"/api/v1/goals/{exam_goal.id}/consultation/history")

    assert [item["question"] for item in response.json()] == ["資格の質問"]


def test_get_history_on_missing_goal_returns_not_found(client):
    response = client.get("/api/v1/goals/999999/consultation/history")

    assert response.status_code == 404


def test_delete_history_item_removes_it(client, exam_goal, fake_ai):
    conversation_id = _create_conversation(client, exam_goal.id)
    client.post(
        f"/api/v1/goals/{exam_goal.id}/consultation/questions",
        json={"conversation_id": conversation_id, "question": "質問"},
    )
    [entry] = client.get(f"/api/v1/goals/{exam_goal.id}/consultation/history").json()

    response = client.delete(
        f"/api/v1/goals/{exam_goal.id}/consultation/history/{entry['id']}"
    )

    assert response.status_code == 204
    assert client.get(f"/api/v1/goals/{exam_goal.id}/consultation/history").json() == []


def test_delete_history_item_on_another_goal_returns_not_found(
    client, exam_goal, reading_goal, fake_ai
):
    """他目標の履歴は削除できない（認可境界、開発Todo v1.1 §5）。"""
    conversation_id = _create_conversation(client, exam_goal.id)
    client.post(
        f"/api/v1/goals/{exam_goal.id}/consultation/questions",
        json={"conversation_id": conversation_id, "question": "資格の質問"},
    )
    [entry] = client.get(f"/api/v1/goals/{exam_goal.id}/consultation/history").json()

    response = client.delete(
        f"/api/v1/goals/{reading_goal.id}/consultation/history/{entry['id']}"
    )

    assert response.status_code == 404


def test_delete_history_item_on_missing_log_id_returns_not_found(client, exam_goal):
    response = client.delete(f"/api/v1/goals/{exam_goal.id}/consultation/history/999999")

    assert response.status_code == 404
