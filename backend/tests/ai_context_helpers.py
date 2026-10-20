"""ai_context_common／ai_context_exam／ai_context_reading／ai_context_workの各テストで
共通して使う生成処理（CLAUDE.md DRYの原則。reading_helpers.pyと同じ位置づけ）。
"""

import datetime as dt

from app.constants.enums import AiPurpose, ChatRole, GoalStatus, RecordState
from app.models.goal import Goal
from app.models.record import ChatMessage, DailyRecord


def make_goal(session, name="目標A", status=GoalStatus.ACTIVE):
    goal = Goal(name=name, start_date=dt.date(2026, 1, 1), status=status)
    session.add(goal)
    session.flush()
    return goal


def make_daily_record(
    session, record_date: dt.date, state: RecordState = RecordState.REPORTED
) -> DailyRecord:
    """build_week_user_chat_text等、chat_messageを扱うテストで使う日次記録の生成
    （test_analytics_service.pyの同名パターンと同じ最小構成。CLAUDE.md DRYの原則）。
    record_dateはテーブル全体で一意のため、呼び出し側は日付を重複させない。
    """
    record = DailyRecord(record_date=record_date, exam_record_state=state)
    session.add(record)
    session.flush()
    return record


def add_chat_message(
    session,
    daily_record_id: int,
    role: ChatRole,
    sequence: int,
    content: str,
    goal_id: int | None = None,
    purpose: AiPurpose = AiPurpose.DAILY_FEEDBACK,
) -> ChatMessage:
    message = ChatMessage(
        daily_record_id=daily_record_id,
        goal_id=goal_id,
        purpose=purpose,
        role=role,
        content=content,
        sequence=sequence,
    )
    session.add(message)
    session.flush()
    return message
