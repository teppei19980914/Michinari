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
    "daily_record",
    "study_log",
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
