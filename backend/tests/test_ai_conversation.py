"""ai/conversation のテスト（ロジック・プロンプト編16.3、データ構造編5.5 ai_conversation）。"""

import datetime as dt

import pytest

from app.ai import client as ai_client
from app.ai import conversation as ai_conversation
from app.ai.exceptions import AiError
from app.constants.enums import ConversationScope, GoalStatus
from app.models.ai import AiConversation
from app.models.goal import Goal


def _make_goal(session, name="目標A"):
    goal = Goal(name=name, start_date=dt.date(2026, 1, 1), status=GoalStatus.ACTIVE)
    session.add(goal)
    session.flush()
    return goal


def test_ensure_conversation_creates_new_when_absent_with_folder(seeded_session, monkeypatch):
    goal = _make_goal(seeded_session)
    calls = []
    monkeypatch.setattr(
        ai_client,
        "create_chat_in_folder_by_name",
        lambda session, *, assistant_uid, folder_name, title: (
            calls.append((assistant_uid, folder_name, title)) or "chat-uid-1"
        ),
    )

    conversation = ai_conversation.ensure_conversation(
        seeded_session,
        goal=goal,
        scope=ConversationScope.WEEKLY_SUMMARY,
        scope_key="2026-08-17",
        assistant_uid="asst-1",
        title="2026-08-17週 週次要約",
    )

    assert conversation.conversation_uid == "chat-uid-1"
    assert conversation.goal_id == goal.id
    assert calls == [("asst-1", f"ミチナリ_{goal.name}", "2026-08-17週 週次要約")]
    assert seeded_session.query(AiConversation).count() == 1


def test_ensure_conversation_creates_without_folder_when_goal_is_none(
    seeded_session, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        ai_client,
        "create_chat",
        lambda session, *, assistant_uid, title: (
            calls.append((assistant_uid, title)) or "chat-uid-2"
        ),
    )

    conversation = ai_conversation.ensure_conversation(
        seeded_session,
        goal=None,
        scope=ConversationScope.DAILY_MESSAGE,
        scope_key="2026-08-24",
        assistant_uid="asst-2",
        title="2026-08-24 今日の一言",
    )

    assert conversation.goal_id is None
    assert conversation.conversation_uid == "chat-uid-2"
    assert calls == [("asst-2", "2026-08-24 今日の一言")]


def test_ensure_conversation_reuses_existing_without_calling_ai(seeded_session, monkeypatch):
    goal = _make_goal(seeded_session)
    existing = AiConversation(
        goal_id=goal.id,
        scope=ConversationScope.DAILY_FEEDBACK,
        scope_key="2026-08-24",
        conversation_uid="existing-chat-uid",
        last_parent_order=0,
    )
    seeded_session.add(existing)
    seeded_session.flush()

    def _fail(*args, **kwargs):
        raise AssertionError("既存の会話がある場合はAI基盤へ問い合わせないはず")

    monkeypatch.setattr(ai_client, "create_chat", _fail)
    monkeypatch.setattr(ai_client, "create_chat_in_folder_by_name", _fail)

    conversation = ai_conversation.ensure_conversation(
        seeded_session,
        goal=goal,
        scope=ConversationScope.DAILY_FEEDBACK,
        scope_key="2026-08-24",
        assistant_uid="asst-1",
        title="2026-08-24 日次報告",
    )

    assert conversation.id == existing.id
    assert seeded_session.query(AiConversation).count() == 1


def test_ensure_conversation_raises_ai_error_when_chat_uid_is_empty(seeded_session, monkeypatch):
    monkeypatch.setattr(ai_client, "create_chat", lambda session, *, assistant_uid, title: None)

    with pytest.raises(AiError):
        ai_conversation.ensure_conversation(
            seeded_session,
            goal=None,
            scope=ConversationScope.DAILY_MESSAGE,
            scope_key="2026-08-24",
            assistant_uid="asst-1",
            title="2026-08-24 今日の一言",
        )


def test_ensure_conversation_distinguishes_by_scope_key(seeded_session, monkeypatch):
    goal = _make_goal(seeded_session)
    uid_counter = iter(["chat-a", "chat-b"])
    monkeypatch.setattr(
        ai_client,
        "create_chat_in_folder_by_name",
        lambda session, **kwargs: next(uid_counter),
    )

    first = ai_conversation.ensure_conversation(
        seeded_session,
        goal=goal,
        scope=ConversationScope.WEEKLY_SUMMARY,
        scope_key="2026-08-10",
        assistant_uid="asst-1",
        title="第1週",
    )
    second = ai_conversation.ensure_conversation(
        seeded_session,
        goal=goal,
        scope=ConversationScope.WEEKLY_SUMMARY,
        scope_key="2026-08-17",
        assistant_uid="asst-1",
        title="第2週",
    )

    assert first.conversation_uid == "chat-a"
    assert second.conversation_uid == "chat-b"
    assert seeded_session.query(AiConversation).count() == 2
