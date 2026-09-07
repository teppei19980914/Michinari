"""work_feedback_service のテスト（データ構造編6.2 POST /records/{date}/work-chat、
ロジック・プロンプト編17.8、実装フェーズ分割計画書Phase22・Phase26完了条件）。

daily_feedback_service（資格試験用）・reading_feedback_service（読書用）のテストと
対になる仕事版。実際のAI基盤へは接続せず、app.ai.client.send_message をモックして検証する。
Phase26で日次フィードバックを目標単位の会話へ分離したため、goal_idが必須になった
（未決事項L-07の解消方針転換）。
"""

import datetime as dt

import pytest

from app.ai import client as ai_client
from app.ai import rate_limiter
from app.ai.exceptions import AiError
from app.constants.enums import AiPurpose, ChatRole, ConversationScope, GoalCategory, GoalStatus
from app.models.ai import AiConversation
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import ChatMessage
from app.models.work import WorkAssignment
from app.services import daily_feedback_service, record_service, work_feedback_service
from app.services.exceptions import InvalidStateTransitionError, NotFoundError, ValidationError
from app.services.record_service import StudyLogItem, WorkLogItem


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


def _make_work_goal(session, name="仕事目標A", status=GoalStatus.ACTIVE):
    goal = Goal(
        category=GoalCategory.WORK,
        name=name,
        start_date=dt.date(2026, 1, 1),
        status=status,
        resource_ratio=0,
    )
    session.add(goal)
    session.flush()
    return goal


def _make_work_assignment(session, goal, **overrides):
    defaults = dict(
        goal_id=goal.id,
        expected_content="想定業務内容",
        start_date=dt.date(2026, 1, 1),
    )
    defaults.update(overrides)
    work_assignment = WorkAssignment(**defaults)
    session.add(work_assignment)
    session.flush()
    return work_assignment


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


def _work_log(work_assignment_id, **overrides):
    defaults = dict(work_assignment_id=work_assignment_id, body="今日の業務内容")
    defaults.update(overrides)
    return WorkLogItem(**defaults)


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
        lambda session, *, assistant_uid, folder_name, title: "chat-uid-work",
    )
    return calls


def test_send_work_feedback_raises_when_prompt_template_missing(seeded_session):
    from app.models.setting import PromptTemplate

    goal = _make_work_goal(seeded_session)
    seeded_session.query(PromptTemplate).filter_by(
        purpose=AiPurpose.DAILY_FEEDBACK_WORK.value
    ).delete()
    seeded_session.flush()

    with pytest.raises(ValidationError):
        work_feedback_service.send_work_feedback(
            seeded_session,
            goal_id=goal.id,
            target_date=dt.date(2026, 8, 24),
            today=dt.date(2026, 8, 24),
            message=None,
            work_log_items=[],
        )


def test_send_work_feedback_rejects_future_date(seeded_session):
    goal = _make_work_goal(seeded_session)

    with pytest.raises(ValidationError):
        work_feedback_service.send_work_feedback(
            seeded_session,
            goal_id=goal.id,
            target_date=dt.date(2026, 8, 25),
            today=dt.date(2026, 8, 24),
            message=None,
            work_log_items=[],
        )


def test_send_work_feedback_rejects_unknown_goal(seeded_session):
    with pytest.raises(NotFoundError):
        work_feedback_service.send_work_feedback(
            seeded_session,
            goal_id=999999,
            target_date=dt.date(2026, 8, 24),
            today=dt.date(2026, 8, 24),
            message=None,
            work_log_items=[],
        )


def test_send_work_feedback_rejects_non_work_goal(seeded_session):
    exam_goal, _material = _make_exam_goal_with_material(seeded_session)

    with pytest.raises(ValidationError):
        work_feedback_service.send_work_feedback(
            seeded_session,
            goal_id=exam_goal.id,
            target_date=dt.date(2026, 8, 24),
            today=dt.date(2026, 8, 24),
            message=None,
            work_log_items=[],
        )


def test_send_work_feedback_rejects_inactive_goal(seeded_session):
    goal = _make_work_goal(seeded_session, status=GoalStatus.DRAFT)

    with pytest.raises(InvalidStateTransitionError):
        work_feedback_service.send_work_feedback(
            seeded_session,
            goal_id=goal.id,
            target_date=dt.date(2026, 8, 24),
            today=dt.date(2026, 8, 24),
            message=None,
            work_log_items=[],
        )


def test_send_work_feedback_first_turn_has_no_user_message_row(seeded_session, monkeypatch):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _stub_send_message(monkeypatch)

    outcome = work_feedback_service.send_work_feedback(
        seeded_session,
        goal_id=goal.id,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message=None,
        work_log_items=[_work_log(work_assignment.id)],
    )

    messages = (
        seeded_session.query(ChatMessage)
        .filter_by(daily_record_id=outcome.daily_record.id)
        .order_by(ChatMessage.sequence)
        .all()
    )
    assert len(messages) == 1
    assert messages[0].role == ChatRole.ASSISTANT
    assert messages[0].purpose == AiPurpose.DAILY_FEEDBACK_WORK
    assert messages[0].goal_id == goal.id
    assert messages[0].content == "AIからの応答"
    assert outcome.was_truncated is False


def test_send_work_feedback_followup_turn_adds_user_and_assistant_messages(
    seeded_session, monkeypatch
):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _stub_send_message(monkeypatch, response="1回目の応答")

    work_feedback_service.send_work_feedback(
        seeded_session,
        goal_id=goal.id,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message=None,
        work_log_items=[_work_log(work_assignment.id)],
    )

    calls = _stub_send_message(monkeypatch, response="2回目の応答")
    outcome = work_feedback_service.send_work_feedback(
        seeded_session,
        goal_id=goal.id,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message="もう少し詳しく教えて",
        work_log_items=[],
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


def test_send_work_feedback_does_not_persist_work_logs(seeded_session, monkeypatch):
    """AI呼び出しが失敗しても業務記録入力が失われない（16.7と同じ保証）。"""
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _stub_send_message(monkeypatch, raise_exc=AiError("通信に失敗しました"))

    with pytest.raises(AiError):
        work_feedback_service.send_work_feedback(
            seeded_session,
            goal_id=goal.id,
            target_date=dt.date(2026, 8, 24),
            today=dt.date(2026, 8, 24),
            message=None,
            work_log_items=[_work_log(work_assignment.id, body="失われてはいけない業務内容")],
        )

    record = record_service.get_daily_record(seeded_session, dt.date(2026, 8, 24))
    assert record is not None
    assert record.work_logs == []


def test_work_feedback_conversation_history_does_not_leak_exam_messages(
    seeded_session, monkeypatch
):
    """資格試験の日次報告フィードバックと仕事の日次報告フィードバックが同日に両方
    実行されても、互いの対話履歴が相手のプロンプトに注入されないこと
    （chat_message.purposeによる分離）。
    """
    exam_goal, material = _make_exam_goal_with_material(seeded_session)
    work_goal = _make_work_goal(seeded_session, name="仕事目標B")
    work_assignment = _make_work_assignment(seeded_session, work_goal)

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
                minutes_spent=30,
                amount_completed=10.0,
                cycle_number=1,
                quality_value=None,
            )
        ],
        diary_entries=[],
    )

    _stub_send_message(monkeypatch, response="仕事フィードバック1回目")
    work_feedback_service.send_work_feedback(
        seeded_session,
        goal_id=work_goal.id,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message=None,
        work_log_items=[_work_log(work_assignment.id)],
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
    assert "資格試験フィードバック1回目" in exam_calls[0]["message"]
    assert "仕事フィードバック1回目" not in exam_calls[0]["message"]

    work_calls = _stub_send_message(monkeypatch, response="仕事フィードバック2回目")
    work_feedback_service.send_work_feedback(
        seeded_session,
        goal_id=work_goal.id,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message="続きです（仕事）",
        work_log_items=[],
    )
    assert "仕事フィードバック1回目" in work_calls[0]["message"]
    assert "資格試験フィードバック1回目" not in work_calls[0]["message"]


def test_work_feedback_uses_separate_ai_conversation_from_exam(seeded_session, monkeypatch):
    """DAILY_FEEDBACKとDAILY_FEEDBACK_WORKは別scope・別goal_idのため、
    ai_conversationの一意制約(goal_id, scope, scope_key)により別会話として保存されること
    （Phase26で目標単位化した後も、カテゴリをまたいだ会話分離は従来通り機能する）。
    """
    exam_goal, material = _make_exam_goal_with_material(seeded_session)
    work_goal = _make_work_goal(seeded_session, name="仕事目標B")
    work_assignment = _make_work_assignment(seeded_session, work_goal)

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
    work_feedback_service.send_work_feedback(
        seeded_session,
        goal_id=work_goal.id,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message=None,
        work_log_items=[_work_log(work_assignment.id)],
    )

    conversations = seeded_session.query(AiConversation).all()
    assert len(conversations) == 2
    scopes = {c.scope for c in conversations}
    assert scopes == {ConversationScope.DAILY_FEEDBACK, ConversationScope.DAILY_FEEDBACK_WORK}
    goal_ids = {c.goal_id for c in conversations}
    assert goal_ids == {exam_goal.id, work_goal.id}
