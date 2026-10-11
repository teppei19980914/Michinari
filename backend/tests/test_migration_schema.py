"""完了条件: alembic upgrade head でデータベースが構築されること（スキーマ変更系）。

本ファイルは最終スキーマの構造（テーブル・列の存在/削除・NULL許容等）を検証する。
既存データに対する安全性（移行時のデータ保持・バックフィル）を検証するテストは
test_migration_data.py、prompt_templateの初期文面移行を検証するテストは
test_migration_prompt.py を参照（実装フェーズ分割計画書S02、test_migration.pyからの分割）。
"""

from alembic.config import Config
from sqlalchemy import inspect

from alembic import command
from app.database import engine
from app.desktop.logging_setup import preserve_logging_state

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
    "daily_goal_diary",
    "weekly_summary",
    "daily_message",
    "exam_result",
    "goal_retrospective",
    "ai_conversation",
    "ai_log",
    "work_assignment",
    "work_log",
    "alembic_version",
}


def test_upgrade_head_creates_all_tables():
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert EXPECTED_TABLES <= tables


def test_upgrade_head_is_idempotent(alembic_config: Config):
    # 既にheadまで適用済みの状態で再実行してもエラーにならないこと。
    # alembic/env.pyのfileConfig()の副作用（既存の非alembicロガーの無効化）から
    # 他テストを守るためpreserve_logging_state()で包む（migration_helpers.upgrade_to参照）。
    with preserve_logging_state():
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

    record = DailyRecord(
        record_date=dt.date(2026, 1, 1), exam_record_state=RecordState.PROGRESS_ONLY
    )
    db_session.add(record)
    db_session.flush()
    message = ChatMessage(
        daily_record_id=record.id, role=ChatRole.ASSISTANT, content="応答", sequence=1
    )
    db_session.add(message)
    db_session.commit()
    assert message.purpose == AiPurpose.DAILY_FEEDBACK


def test_daily_record_no_longer_has_diary_columns():
    """完了条件: diary_body/diary_learnedはdaily_goal_diaryへ分離され、
    daily_recordには残らないこと（設計書ロジック・プロンプト編 未決事項L-04）。
    """
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("daily_record")}
    assert "diary_body" not in columns
    assert "diary_learned" not in columns
    diary_columns = {col["name"] for col in inspector.get_columns("daily_goal_diary")}
    assert diary_columns >= {"id", "daily_record_id", "goal_id", "diary_body", "diary_learned"}


def test_daily_record_has_category_state_columns_and_no_longer_has_record_state():
    """完了条件: daily_recordがカテゴリ別の確定状態6列を持ち、旧record_state/reported_at
    列は残っていないこと（仕様変更2026-09-05、7c2e5a1d9f4b）。"""
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("daily_record")}
    assert columns >= {
        "exam_record_state",
        "exam_reported_at",
        "reading_record_state",
        "reading_reported_at",
        "work_record_state",
        "work_reported_at",
    }
    assert "record_state" not in columns
    assert "reported_at" not in columns


def test_daily_message_has_nullable_goal_id_and_composite_unique():
    """完了条件: daily_messageがgoal_id列を持ち、(target_date, goal_id)の複合ユニーク
    制約により同一日に複数目標分のメッセージを保持できること（未決事項L-04関連）。
    """
    inspector = inspect(engine)
    columns = {col["name"]: col for col in inspector.get_columns("daily_message")}
    assert "goal_id" in columns
    assert columns["goal_id"]["nullable"] is True
    unique_constraints = inspector.get_unique_constraints("daily_message")
    assert any(set(uc["column_names"]) == {"target_date", "goal_id"} for uc in unique_constraints)


def test_work_goal_category_migration_creates_work_tables_and_retrospective_columns():
    """完了条件: work_assignment・work_logテーブルが作成され、goal_retrospectiveに
    period_type以下9列が追加されること（実装フェーズ分割計画書Phase20、e1f4a9c3b6d8）。"""
    inspector = inspect(engine)

    work_assignment_columns = {col["name"] for col in inspector.get_columns("work_assignment")}
    assert work_assignment_columns >= {
        "id",
        "goal_id",
        "client_name",
        "expected_content",
        "start_date",
        "created_at",
        "updated_at",
    }
    work_assignment_unique = inspector.get_unique_constraints("work_assignment")
    assert any(uc["column_names"] == ["goal_id"] for uc in work_assignment_unique)

    work_log_columns = {col["name"] for col in inspector.get_columns("work_log")}
    assert work_log_columns >= {
        "id",
        "daily_record_id",
        "work_assignment_id",
        "body",
        "created_at",
    }
    work_log_unique = inspector.get_unique_constraints("work_log")
    assert any(
        set(uc["column_names"]) == {"work_assignment_id", "daily_record_id"}
        for uc in work_log_unique
    )

    retrospective_columns = {col["name"] for col in inspector.get_columns("goal_retrospective")}
    assert retrospective_columns >= {
        "period_type",
        "period_key",
        "target_goal_text",
        "business_summary",
        "achievement_score",
        "achievement_reflection",
        "next_goal_text",
        "report_notes",
        "edited_at",
    }
    retrospective_unique = inspector.get_unique_constraints("goal_retrospective")
    assert any(
        set(uc["column_names"]) == {"goal_id", "period_type", "period_key", "is_anonymized"}
        for uc in retrospective_unique
    )


def test_chat_message_has_nullable_goal_id_column(db_session):
    """完了条件: chat_message.goal_idが存在し、NULL許容であること
    （Phase26、d8f21a6c4b3e、未決事項L-07の解消方針転換）。"""
    import datetime as dt

    from app.constants.enums import ChatRole, RecordState
    from app.models.record import ChatMessage, DailyRecord

    inspector = inspect(engine)
    columns = {col["name"]: col for col in inspector.get_columns("chat_message")}
    assert "goal_id" in columns
    assert columns["goal_id"]["nullable"] is True

    record = DailyRecord(
        record_date=dt.date(2026, 1, 1), exam_record_state=RecordState.PROGRESS_ONLY
    )
    db_session.add(record)
    db_session.flush()
    message = ChatMessage(
        daily_record_id=record.id, role=ChatRole.ASSISTANT, content="応答", sequence=1
    )
    db_session.add(message)
    db_session.commit()
    assert message.goal_id is None


def test_slot_allocation_migration_creates_tables_and_drops_resource_ratio():
    """リソース配分のスロット単位化（f2b7c4a91d3e）で、配分・時間枠別内訳の3テーブルが
    構築され、goal.resource_ratio が削除されていること（実装フェーズ分割計画書Phase28）。"""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    assert {"goal_slot_allocation", "study_log_slot_time", "reading_log_slot_time"} <= tables

    goal_columns = {c["name"] for c in inspector.get_columns("goal")}
    assert "resource_ratio" not in goal_columns

    reading_log_columns = {c["name"] for c in inspector.get_columns("reading_log")}
    assert "minutes_spent" in reading_log_columns


def test_slot_allocation_migration_slot_time_slot_id_is_nullable():
    """時間枠別内訳の slot_id は NULL 許容であること（スロット削除時に ON DELETE SET NULL
    で実績を残すため。データ構造編5.4、仕様書NT-09）。"""
    inspector = inspect(engine)

    for table, log_column in (
        ("study_log_slot_time", "study_log_id"),
        ("reading_log_slot_time", "reading_log_id"),
    ):
        columns = {c["name"]: c for c in inspector.get_columns(table)}
        assert columns["slot_id"]["nullable"] is True
        assert columns[log_column]["nullable"] is False
        assert columns["minutes"]["nullable"] is False


