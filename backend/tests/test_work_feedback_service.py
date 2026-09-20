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
from app.constants.app_setting_keys import AI_MAX_PROMPT_CHARS
from app.constants.enums import (
    AiPurpose,
    ChatRole,
    ConversationScope,
    GoalCategory,
    GoalStatus,
    RecordState,
)
from app.models.ai import AiConversation
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import ChatMessage, DailyRecord, WeeklySummary, WorkLog
from app.models.setting import AppSetting
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


def _make_work_goal(
    session, name="仕事目標A", status=GoalStatus.ACTIVE, start_date=dt.date(2026, 1, 1)
):
    goal = Goal(
        category=GoalCategory.WORK,
        name=name,
        start_date=start_date,
        status=status,
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


def _add_past_work_log(session, work_assignment_id, record_date, body):
    """{{recent_work_logs}}に注入される過去日の業務記録（保存済み）を追加する
    （ai_context_service.build_recent_work_logs_entriesが参照するWorkLog行、17.8）。"""
    record = DailyRecord(record_date=record_date, work_record_state=RecordState.PROGRESS_ONLY)
    session.add(record)
    session.flush()
    session.add(
        WorkLog(daily_record_id=record.id, work_assignment_id=work_assignment_id, body=body)
    )
    session.flush()


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
                slot_minutes={1: 30},
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


def test_send_work_feedback_degrades_oldest_recent_logs_before_instructions(
    seeded_session, monkeypatch
):
    """段階的縮退の回帰テスト（2026-09-14の実運用で発生した事象、CLAUDE.md該当なし・
    ユーザー報告に基づく修正）。旧実装（prompt_builder.build_simple）は上限超過時に
    末尾（テンプレートの指示文＝「フィードバックの構成」「重要な原則」「出力形式」）を
    問答無用で切り詰めていたため、AIが指示を受け取れず直近の会話内容へ引きずられて
    無関係な応答を返す不具合があった。build_recent_log_feedbackは直近記録を古い日
    （{{recent_work_logs}}の先頭）から先に削るため、指示文は必ず残ることを確認する。
    """
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _add_past_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 8), "OLD_MARKER" * 300)
    _add_past_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 9), "NEW_MARKER" * 300)

    setting = seeded_session.get(AppSetting, AI_MAX_PROMPT_CHARS)
    setting.value = "1500"  # 直近記録2件分は到底収まらないが、固定変数＋指示文は収まる閾値
    seeded_session.flush()

    calls = _stub_send_message(monkeypatch)
    outcome = work_feedback_service.send_work_feedback(
        seeded_session,
        goal_id=goal.id,
        target_date=dt.date(2026, 1, 10),
        today=dt.date(2026, 1, 10),
        message=None,
        work_log_items=[_work_log(work_assignment.id, body="本日の業務内容")],
    )

    sent_message = calls[0]["message"]
    assert outcome.was_truncated is True
    # テンプレート末尾（指示文）が必ず残る（旧実装での回帰確認）。
    assert "自然な文章で記述してください" in sent_message
    assert "重要な原則" in sent_message
    # 固定変数（today_work）は縮退対象外のため常に残る。
    assert "本日の業務内容" in sent_message
    # 直近記録は閾値に収まらず、古い日・新しい日の別なく段階1で除外される。
    assert "OLD_MARKER" not in sent_message
    assert "NEW_MARKER" not in sent_message
    assert "直近の業務記録はありません" in sent_message


def test_send_work_feedback_compresses_weekly_summaries_inside_and_outside_recent_window(
    seeded_session, monkeypatch
):
    """L-11（2026-09-16是正）: 週次要約はperiod_start=goal.start_dateまで遡って探索する
    （summary.inject_weeksを上限に、直近recent_days日分〈既定14日〉の窓より前の週も
    {{weekly_summaries}}へ注入される＝過去の経緯を要約で反映し続ける）。加えて、窓と
    重なる週についても、既に週次要約が生成済みなら圧縮表現へ回し{{recent_work_logs}}側の
    生ログからは除外する（reading_feedback_serviceの同名テストと対になる仕事版）。
    """
    goal = _make_work_goal(seeded_session, start_date=dt.date(2025, 11, 1))
    work_assignment = _make_work_assignment(seeded_session, goal)
    seeded_session.add(
        WeeklySummary(
            goal_id=goal.id,
            week_start_date=dt.date(2025, 11, 24),
            week_end_date=dt.date(2025, 11, 30),  # target_date(2026-1-10)の14日窓より前
            summary_body="OLDER_WEEK_SUMMARY",
        )
    )
    seeded_session.add(
        WeeklySummary(
            goal_id=goal.id,
            week_start_date=dt.date(2025, 12, 29),
            week_end_date=dt.date(2026, 1, 4),  # 直近14日窓と重なる週
            summary_body="OVERLAPPING_WEEK_SUMMARY",
        )
    )
    seeded_session.flush()
    calls = _stub_send_message(monkeypatch)

    work_feedback_service.send_work_feedback(
        seeded_session,
        goal_id=goal.id,
        target_date=dt.date(2026, 1, 10),
        today=dt.date(2026, 1, 10),
        message=None,
        work_log_items=[_work_log(work_assignment.id)],
    )

    sent_message = calls[0]["message"]
    assert "OLDER_WEEK_SUMMARY" in sent_message
    # 是正後: 窓と重なる週も既に要約済みなら圧縮対象となり、weekly_summariesへ注入される。
    assert "OVERLAPPING_WEEK_SUMMARY" in sent_message


# --- 観点提案の追加指示（S-4 4-3） ---


def test_send_work_feedback_includes_perspective_suggestion_when_records_are_few(
    seeded_session, monkeypatch
):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    calls = _stub_send_message(monkeypatch)

    work_feedback_service.send_work_feedback(
        seeded_session,
        goal_id=goal.id,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message=None,
        work_log_items=[_work_log(work_assignment.id)],
    )

    assert "断定" in calls[0]["message"]


def test_send_work_feedback_omits_perspective_suggestion_once_enough_records_exist(
    seeded_session, monkeypatch
):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    for day in (21, 22, 23):
        record = DailyRecord(
            record_date=dt.date(2026, 8, day), work_record_state=RecordState.REPORTED
        )
        seeded_session.add(record)
    seeded_session.flush()
    calls = _stub_send_message(monkeypatch)

    work_feedback_service.send_work_feedback(
        seeded_session,
        goal_id=goal.id,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message=None,
        work_log_items=[_work_log(work_assignment.id)],
    )

    assert "断定" not in calls[0]["message"]
