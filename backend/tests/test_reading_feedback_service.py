"""reading_feedback_service のテスト（データ構造編6.2 POST /records/{date}/reading-chat、
ロジック・プロンプト編17.6、実装フェーズ分割計画書Phase16・Phase26完了条件）。

daily_feedback_service（資格試験用）のテストと対になる読書版。実際のAI基盤へは接続せず、
app.ai.client.send_message をモックして検証する。Phase26で日次フィードバックを目標単位の
会話へ分離したため、goal_idが必須になった（未決事項L-07の解消方針転換）。
"""

import datetime as dt

import pytest

from app.ai import client as ai_client
from app.ai import rate_limiter
from app.ai.exceptions import AiError
from app.constants.enums import AiPurpose, ChatRole, ConversationScope, GoalCategory, GoalStatus
from app.models.ai import AiConversation
from app.models.book import Book
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import ChatMessage
from app.services import daily_feedback_service, reading_feedback_service, record_service
from app.services.exceptions import InvalidStateTransitionError, NotFoundError, ValidationError
from app.services.record_service import DiaryEntryItem, ReadingLogItem, StudyLogItem


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


@pytest.fixture(autouse=True)
def _cleanup_committed_rows(seeded_session):
    """AI呼び出し失敗時にcommitされる行が他テストへ漏れないよう明示的に空にする
    （test_daily_feedback_service.pyと同じ後始末パターン）。"""
    yield
    from app.models.base import Base

    seeded_session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        seeded_session.execute(table.delete())
    seeded_session.commit()


def _make_reading_goal(session, name="読書目標A", status=GoalStatus.ACTIVE):
    goal = Goal(
        category=GoalCategory.READING,
        name=name,
        start_date=dt.date(2026, 1, 1),
        status=status,
    )
    session.add(goal)
    session.flush()
    return goal


def _make_book(session, goal, **overrides):
    defaults = dict(
        goal_id=goal.id,
        title="書籍A",
        start_date=dt.date(2026, 1, 1),
        due_date=dt.date(2026, 12, 31),
    )
    defaults.update(overrides)
    book = Book(**defaults)
    session.add(book)
    session.flush()
    return book


def _make_exam_goal_with_material(session, name="資格目標A"):
    goal = Goal(name=name, start_date=dt.date(2026, 1, 1), status=GoalStatus.ACTIVE)
    session.add(goal)
    session.flush()
    material = Material(
        goal_id=goal.id,
        name="教材A",
        unit_label="ページ",
        total_amount=100.0,
        planned_cycles=1,
        start_date=dt.date(2026, 1, 1),
        due_date=dt.date(2026, 12, 31),
        display_order=1,
    )
    session.add(material)
    session.flush()
    return goal, material


def _reading_log(book_id, **overrides):
    defaults = dict(
        book_id=book_id, recall_body="今日読んだ内容の想起", pages_read=10, current_page=10
    )
    defaults.update(overrides)
    return ReadingLogItem(**defaults)


def _stub_send_message(monkeypatch, *, response="AIからの応答", raise_exc=None):
    calls = []

    def _fake(session, *, chat_uid, message):
        calls.append({"chat_uid": chat_uid, "message": message})
        if raise_exc is not None:
            raise raise_exc
        return ai_client.SendResult(response_text=response, latency_ms=123)

    monkeypatch.setattr(ai_client, "send_message", _fake)
    monkeypatch.setattr(
        ai_client,
        "create_chat_in_folder_by_name",
        lambda session, *, assistant_uid, folder_name, title: "chat-uid-reading",
    )
    return calls


def test_send_reading_feedback_raises_when_prompt_template_missing(seeded_session):
    from app.models.setting import PromptTemplate

    goal = _make_reading_goal(seeded_session)
    seeded_session.query(PromptTemplate).filter_by(
        purpose=AiPurpose.DAILY_FEEDBACK_READING.value
    ).delete()
    seeded_session.flush()

    with pytest.raises(ValidationError):
        reading_feedback_service.send_reading_feedback(
            seeded_session,
            goal_id=goal.id,
            target_date=dt.date(2026, 8, 24),
            today=dt.date(2026, 8, 24),
            message=None,
            reading_log_items=[],
        )


def test_send_reading_feedback_rejects_future_date(seeded_session):
    goal = _make_reading_goal(seeded_session)

    with pytest.raises(ValidationError):
        reading_feedback_service.send_reading_feedback(
            seeded_session,
            goal_id=goal.id,
            target_date=dt.date(2026, 8, 25),
            today=dt.date(2026, 8, 24),
            message=None,
            reading_log_items=[],
        )


def test_send_reading_feedback_rejects_unknown_goal(seeded_session):
    with pytest.raises(NotFoundError):
        reading_feedback_service.send_reading_feedback(
            seeded_session,
            goal_id=999999,
            target_date=dt.date(2026, 8, 24),
            today=dt.date(2026, 8, 24),
            message=None,
            reading_log_items=[],
        )


def test_send_reading_feedback_rejects_non_reading_goal(seeded_session):
    exam_goal, _material = _make_exam_goal_with_material(seeded_session)

    with pytest.raises(ValidationError):
        reading_feedback_service.send_reading_feedback(
            seeded_session,
            goal_id=exam_goal.id,
            target_date=dt.date(2026, 8, 24),
            today=dt.date(2026, 8, 24),
            message=None,
            reading_log_items=[],
        )


def test_send_reading_feedback_rejects_inactive_goal(seeded_session):
    goal = _make_reading_goal(seeded_session, status=GoalStatus.DRAFT)

    with pytest.raises(InvalidStateTransitionError):
        reading_feedback_service.send_reading_feedback(
            seeded_session,
            goal_id=goal.id,
            target_date=dt.date(2026, 8, 24),
            today=dt.date(2026, 8, 24),
            message=None,
            reading_log_items=[],
        )


def test_send_reading_feedback_first_turn_has_no_user_message_row(seeded_session, monkeypatch):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    _stub_send_message(monkeypatch)

    outcome = reading_feedback_service.send_reading_feedback(
        seeded_session,
        goal_id=goal.id,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message=None,
        reading_log_items=[_reading_log(book.id)],
    )

    messages = (
        seeded_session.query(ChatMessage)
        .filter_by(daily_record_id=outcome.daily_record.id)
        .order_by(ChatMessage.sequence)
        .all()
    )
    assert len(messages) == 1
    assert messages[0].role == ChatRole.ASSISTANT
    assert messages[0].purpose == AiPurpose.DAILY_FEEDBACK_READING
    assert messages[0].goal_id == goal.id
    assert messages[0].content == "AIからの応答"
    assert outcome.was_truncated is False


def test_send_reading_feedback_followup_turn_adds_user_and_assistant_messages(
    seeded_session, monkeypatch
):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    _stub_send_message(monkeypatch, response="1回目の応答")

    reading_feedback_service.send_reading_feedback(
        seeded_session,
        goal_id=goal.id,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message=None,
        reading_log_items=[_reading_log(book.id)],
    )

    calls = _stub_send_message(monkeypatch, response="2回目の応答")
    outcome = reading_feedback_service.send_reading_feedback(
        seeded_session,
        goal_id=goal.id,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message="もう少し詳しく教えて",
        reading_log_items=[],
    )

    messages = (
        seeded_session.query(ChatMessage)
        .filter_by(daily_record_id=outcome.daily_record.id)
        .order_by(ChatMessage.sequence)
        .all()
    )
    assert [m.role for m in messages] == [ChatRole.ASSISTANT, ChatRole.USER, ChatRole.ASSISTANT]
    assert "1回目の応答" in calls[0]["message"]
    assert "もう少し詳しく教えて" in calls[0]["message"]


def test_send_reading_feedback_does_not_persist_reading_logs(seeded_session, monkeypatch):
    """AI呼び出しが失敗しても想起入力が失われない（16.7と同じ保証、Phase16完了条件）。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    _stub_send_message(monkeypatch, raise_exc=AiError("通信に失敗しました"))

    with pytest.raises(AiError):
        reading_feedback_service.send_reading_feedback(
            seeded_session,
            goal_id=goal.id,
            target_date=dt.date(2026, 8, 24),
            today=dt.date(2026, 8, 24),
            message=None,
            reading_log_items=[_reading_log(book.id, recall_body="失われてはいけない想起")],
        )

    record = record_service.get_daily_record(seeded_session, dt.date(2026, 8, 24))
    assert record is not None
    assert record.reading_logs == []


def test_reading_feedback_conversation_history_does_not_leak_exam_messages(
    seeded_session, monkeypatch
):
    """資格試験の日次報告フィードバックと読書の日次報告フィードバックが同日に両方
    実行されても、互いの対話履歴が相手のプロンプトに注入されないこと
    （chat_message.purposeによる分離、Phase16でのai_context_service.list_active_exam_goals
    導入に続く回帰防止確認）。
    """
    exam_goal, material = _make_exam_goal_with_material(seeded_session)
    reading_goal = _make_reading_goal(seeded_session, name="読書目標B")
    book = _make_book(seeded_session, reading_goal)

    _stub_send_message(monkeypatch, response="資格試験フィードバック1回目")
    daily_feedback_service.send_daily_feedback(
        seeded_session,
        goal_id=exam_goal.id,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message=None,
        study_log_items=[
            StudyLogItem(
                material_id=material.id,
                slot_minutes={1: 30},
                amount_completed=10.0,
                cycle_number=1,
                quality_value=None,
            )
        ],
        diary_entries=[
            DiaryEntryItem(
                goal_id=exam_goal.id, diary_body="今日は頑張った", diary_learned="過去問を解いた"
            )
        ],
    )

    _stub_send_message(monkeypatch, response="読書フィードバック1回目")
    reading_feedback_service.send_reading_feedback(
        seeded_session,
        goal_id=reading_goal.id,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message=None,
        reading_log_items=[_reading_log(book.id)],
    )

    exam_calls = _stub_send_message(monkeypatch, response="資格試験フィードバック2回目")
    daily_feedback_service.send_daily_feedback(
        seeded_session,
        goal_id=exam_goal.id,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message="続きです（資格試験）",
        study_log_items=[],
        diary_entries=[],
    )
    # 資格試験2回目の送信内容に、読書フィードバックの応答が混入していないこと。
    assert "資格試験フィードバック1回目" in exam_calls[0]["message"]
    assert "読書フィードバック1回目" not in exam_calls[0]["message"]

    reading_calls = _stub_send_message(monkeypatch, response="読書フィードバック2回目")
    reading_feedback_service.send_reading_feedback(
        seeded_session,
        goal_id=reading_goal.id,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message="続きです（読書）",
        reading_log_items=[],
    )
    # 読書2回目の送信内容に、資格試験フィードバックの応答が混入していないこと。
    assert "読書フィードバック1回目" in reading_calls[0]["message"]
    assert "資格試験フィードバック1回目" not in reading_calls[0]["message"]


def test_reading_feedback_uses_separate_ai_conversation_from_exam(seeded_session, monkeypatch):
    """DAILY_FEEDBACKとDAILY_FEEDBACK_READINGは別scope・別goal_idのため、
    ai_conversationの一意制約(goal_id, scope, scope_key)により別会話として保存されること
    （Phase26で目標単位化した後も、カテゴリをまたいだ会話分離は従来通り機能する）。
    """
    exam_goal, material = _make_exam_goal_with_material(seeded_session)
    reading_goal = _make_reading_goal(seeded_session, name="読書目標B")
    book = _make_book(seeded_session, reading_goal)

    _stub_send_message(monkeypatch)
    daily_feedback_service.send_daily_feedback(
        seeded_session,
        goal_id=exam_goal.id,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message=None,
        study_log_items=[],
        diary_entries=[],
    )
    reading_feedback_service.send_reading_feedback(
        seeded_session,
        goal_id=reading_goal.id,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message=None,
        reading_log_items=[_reading_log(book.id)],
    )

    conversations = seeded_session.query(AiConversation).all()
    assert len(conversations) == 2
    scopes = {c.scope for c in conversations}
    assert scopes == {ConversationScope.DAILY_FEEDBACK, ConversationScope.DAILY_FEEDBACK_READING}
    goal_ids = {c.goal_id for c in conversations}
    assert goal_ids == {exam_goal.id, reading_goal.id}
