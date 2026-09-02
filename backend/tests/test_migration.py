"""完了条件: alembic upgrade head でデータベースが構築されること。"""

from alembic.config import Config
from sqlalchemy import inspect

from alembic import command
from app.database import engine

EXPECTED_TABLES = {
    "app_setting",
    "prompt_template",
    "holiday",
    "day_type_default",
    "calendar_day_override",
    "resource_slot",
    "resource_slot_weekday",
    "goal",
    "exam_subject",
    "material",
    "material_subject",
    "load_profile",
    "plan_baseline",
    "book",
    "daily_record",
    "study_log",
    "reading_log",
    "chat_message",
    "record_comment",
    "weekly_summary",
    "daily_message",
    "exam_result",
    "goal_retrospective",
    "ai_conversation",
    "ai_log",
    "alembic_version",
}


def test_upgrade_head_creates_all_tables():
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert EXPECTED_TABLES <= tables


def test_upgrade_head_is_idempotent(alembic_config: Config):
    # 既にheadまで適用済みの状態で再実行してもエラーにならないこと
    command.upgrade(alembic_config, "head")
    inspector = inspect(engine)
    assert "goal" in inspector.get_table_names()


def test_material_has_planned_cycles_not_current_cycle():
    """完了条件: material に planned_cycles が存在し、current_cycle が存在しないこと。"""
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("material")}
    assert "planned_cycles" in columns
    assert "current_cycle" not in columns


def test_goal_has_category_column_and_existing_rows_backfilled_to_exam(db_session):
    """完了条件: goal.categoryが存在し、既存goalレコードがEXAMとして引き継がれること。"""
    import datetime as dt

    from app.constants.enums import GoalCategory, GoalStatus
    from app.models.goal import Goal

    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("goal")}
    assert "category" in columns

    goal = Goal(
        name="マイグレーション検証用", start_date=dt.date(2026, 1, 1), status=GoalStatus.ACTIVE
    )
    db_session.add(goal)
    db_session.commit()
    assert goal.category == GoalCategory.EXAM


def test_chat_message_has_purpose_column_defaulting_to_daily_feedback(db_session):
    """完了条件: chat_message.purposeが存在し、既存の用途（資格試験）ではDAILY_FEEDBACKとして
    引き継がれること（実装フェーズ分割計画書Phase16）。"""
    import datetime as dt

    from app.constants.enums import AiPurpose, ChatRole, RecordState
    from app.models.record import ChatMessage, DailyRecord

    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("chat_message")}
    assert "purpose" in columns

    record = DailyRecord(record_date=dt.date(2026, 1, 1), record_state=RecordState.PROGRESS_ONLY)
    db_session.add(record)
    db_session.flush()
    message = ChatMessage(
        daily_record_id=record.id, role=ChatRole.ASSISTANT, content="応答", sequence=1
    )
    db_session.add(message)
    db_session.commit()
    assert message.purpose == AiPurpose.DAILY_FEEDBACK
