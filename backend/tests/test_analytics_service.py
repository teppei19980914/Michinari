"""analytics_service のテスト（仕様書6.8 SC-09、実装フェーズ分割計画書Phase9）。

analytics_serviceには、既存章（6・8・13・14章）のどれにも属さない分析画面固有の算出
（計画線・成長記述の抽出）のみを置いている。それぞれの算出根拠はcompute_plan_line・
list_growth_descriptionsのdocstringを参照。
"""

import datetime as dt

import pytest

from app.constants.enums import (
    AiPurpose,
    BaselineReason,
    ChatRole,
    DayType,
    GoalCategory,
    GoalStatus,
    RecordState,
)
from app.models.goal import Goal
from app.models.material import Material, PlanBaseline
from app.models.record import ChatMessage, DailyRecord
from app.models.setting import CalendarDayOverride
from app.services import analytics_service
from app.services.exceptions import NotFoundError, ValidationError


def _make_goal(db_session, category=GoalCategory.EXAM, name="分析検証") -> Goal:
    goal = Goal(
        name=name, category=category, start_date=dt.date(2026, 1, 1), status=GoalStatus.ACTIVE
    )
    db_session.add(goal)
    db_session.flush()
    return goal


def _make_material(
    db_session,
    goal_id: int,
    start_date: dt.date = dt.date(2026, 1, 1),
    due_date: dt.date = dt.date(2026, 1, 5),
) -> Material:
    material = Material(
        goal_id=goal_id,
        name="教材",
        unit_label="問",
        total_amount=100,
        planned_cycles=1,
        start_date=start_date,
        due_date=due_date,
        display_order=1,
    )
    db_session.add(material)
    db_session.flush()
    return material


def _add_baseline(
    db_session,
    material_id: int,
    effective_from: dt.date,
    quota: float,
    reason: BaselineReason = BaselineReason.INITIAL,
) -> None:
    db_session.add(
        PlanBaseline(
            material_id=material_id,
            effective_from=effective_from,
            baseline_daily_quota=quota,
            remaining_at_baseline=100,
            plan_days_at_baseline=10,
            planned_cycles_at_baseline=1,
            reason=reason,
        )
    )
    db_session.flush()


def test_plan_line_accumulates_baseline_quota_over_plan_days(db_session):
    """計画線は基準ノルマをPLAN日に沿って積算すること（Phase9実装判断、docstring参照）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    _add_baseline(db_session, material.id, dt.date(2026, 1, 1), quota=10)

    points = analytics_service.compute_plan_line(db_session, material, treat_holiday_as_buffer=True)

    assert [p.record_date for p in points] == [
        dt.date(2026, 1, 1),
        dt.date(2026, 1, 2),
        dt.date(2026, 1, 3),
        dt.date(2026, 1, 4),
        dt.date(2026, 1, 5),
    ]
    assert [p.cumulative_completed for p in points] == [10, 20, 30, 40, 50]


def test_plan_line_switches_quota_at_replan_effective_date(db_session):
    """リプラン後は新しいbaseline_daily_quotaへ切り替わって積算されること。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    _add_baseline(db_session, material.id, dt.date(2026, 1, 1), quota=10)
    _add_baseline(
        db_session, material.id, dt.date(2026, 1, 3), quota=20, reason=BaselineReason.REPLAN
    )

    points = analytics_service.compute_plan_line(db_session, material, treat_holiday_as_buffer=True)

    assert [p.cumulative_completed for p in points] == [10, 20, 40, 60, 80]


def test_plan_line_excludes_buffer_and_off_days_from_accumulation(db_session):
    """PLAN日以外（BUFFER/OFF）はノルマを積算しないこと。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    _add_baseline(db_session, material.id, dt.date(2026, 1, 1), quota=10)
    db_session.add(CalendarDayOverride(target_date=dt.date(2026, 1, 3), day_type=DayType.BUFFER))
    db_session.flush()

    points = analytics_service.compute_plan_line(db_session, material, treat_holiday_as_buffer=True)

    # 1/3はBUFFER日のため据え置き（10, 20, 20, 30, 40）
    assert [p.cumulative_completed for p in points] == [10, 20, 20, 30, 40]


def test_plan_line_empty_when_no_baselines(db_session):
    """境界値: 計画基準値が1件も記録されていない場合に例外が発生しないこと。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)

    points = analytics_service.compute_plan_line(db_session, material, treat_holiday_as_buffer=True)
    assert points == []


def _make_record(db_session, record_date: dt.date, state: RecordState = RecordState.REPORTED):
    record = DailyRecord(record_date=record_date, exam_record_state=state)
    db_session.add(record)
    db_session.flush()
    return record


def _add_chat_message(
    db_session,
    record_id: int,
    role: ChatRole,
    sequence: int,
    content: str,
    goal_id: int | None = None,
    purpose: AiPurpose = AiPurpose.DAILY_FEEDBACK,
) -> ChatMessage:
    message = ChatMessage(
        daily_record_id=record_id,
        goal_id=goal_id,
        purpose=purpose,
        role=role,
        content=content,
        sequence=sequence,
    )
    db_session.add(message)
    db_session.flush()
    return message


def test_growth_descriptions_returns_assistant_messages_ordered_by_date_desc(db_session):
    """成長記述タブ（ANL-07）: 対象目標宛てのAI応答が新しい日付順に列挙されること
    （Phase26で目標単位に分離）。"""
    goal = _make_goal(db_session)
    record1 = _make_record(db_session, dt.date(2026, 1, 5))
    _add_chat_message(db_session, record1.id, ChatRole.USER, 1, "今日は疲れました", goal_id=goal.id)
    _add_chat_message(db_session, record1.id, ChatRole.ASSISTANT, 2, "1/5の応答", goal_id=goal.id)
    record2 = _make_record(db_session, dt.date(2026, 1, 10))
    _add_chat_message(db_session, record2.id, ChatRole.ASSISTANT, 1, "1/10の応答", goal_id=goal.id)

    entries = analytics_service.list_growth_descriptions(db_session, goal)

    assert [e.record_date for e in entries] == [dt.date(2026, 1, 10), dt.date(2026, 1, 5)]
    assert entries[0].content == "1/10の応答"
    assert entries[0].goal_id == goal.id
    assert entries[1].content == "1/5の応答"


def test_growth_descriptions_excludes_user_role_messages(db_session):
    """USER発言（自由入力メッセージ）は成長記述の対象に含めないこと。"""
    goal = _make_goal(db_session)
    record = _make_record(db_session, dt.date(2026, 1, 5))
    _add_chat_message(db_session, record.id, ChatRole.USER, 1, "質問です", goal_id=goal.id)

    assert analytics_service.list_growth_descriptions(db_session, goal) == []


def test_growth_descriptions_empty_when_no_chat_messages(db_session):
    """境界値: AI対話が1件も記録されていない場合に例外が発生しないこと。"""
    goal = _make_goal(db_session)
    assert analytics_service.list_growth_descriptions(db_session, goal) == []


def test_growth_descriptions_excludes_messages_assigned_to_other_goal(db_session):
    """同カテゴリの別目標に割り当て済みのメッセージは対象に含めないこと（Phase26）。"""
    goal_a = _make_goal(db_session, name="目標A")
    goal_b = _make_goal(db_session, name="目標B")
    record = _make_record(db_session, dt.date(2026, 1, 5))
    _add_chat_message(db_session, record.id, ChatRole.ASSISTANT, 1, "目標A宛て", goal_id=goal_a.id)

    assert analytics_service.list_growth_descriptions(db_session, goal_b) == []


def test_growth_descriptions_includes_unassigned_legacy_messages_of_same_category(db_session):
    """移行前のレガシーメッセージ（goal_id=NULL）は、purposeが一致するカテゴリの目標に
    対しては「未割り当て」として表示対象に含めること（Phase26、未決事項L-07）。"""
    goal = _make_goal(db_session)
    record = _make_record(db_session, dt.date(2026, 1, 5))
    _add_chat_message(db_session, record.id, ChatRole.ASSISTANT, 1, "移行前の応答", goal_id=None)

    entries = analytics_service.list_growth_descriptions(db_session, goal)

    assert len(entries) == 1
    assert entries[0].goal_id is None
    assert entries[0].content == "移行前の応答"


def test_growth_descriptions_excludes_unassigned_messages_of_other_category(db_session):
    """未割り当てメッセージでも、purposeのカテゴリが異なれば対象に含めないこと（Phase26）。"""
    exam_goal = _make_goal(db_session)
    record = _make_record(db_session, dt.date(2026, 1, 5))
    _add_chat_message(
        db_session,
        record.id,
        ChatRole.ASSISTANT,
        1,
        "読書の応答",
        goal_id=None,
        purpose=AiPurpose.DAILY_FEEDBACK_READING,
    )

    assert analytics_service.list_growth_descriptions(db_session, exam_goal) == []


def test_assign_growth_description_goal_updates_goal_id(db_session):
    """未割り当ての成長記述に目標を手動で割り当てられること（Phase26）。"""
    goal = _make_goal(db_session)
    record = _make_record(db_session, dt.date(2026, 1, 5))
    message = _add_chat_message(
        db_session, record.id, ChatRole.ASSISTANT, 1, "移行前の応答", goal_id=None
    )

    analytics_service.assign_growth_description_goal(db_session, message, goal)

    assert message.goal_id == goal.id


def test_assign_growth_description_goal_rejects_category_mismatch(db_session):
    """メッセージのpurposeに対応しないカテゴリの目標は割り当てられないこと（Phase26）。"""
    reading_goal = _make_goal(db_session, category=GoalCategory.READING, name="読書目標")
    record = _make_record(db_session, dt.date(2026, 1, 5))
    message = _add_chat_message(
        db_session,
        record.id,
        ChatRole.ASSISTANT,
        1,
        "資格試験の応答",
        goal_id=None,
        purpose=AiPurpose.DAILY_FEEDBACK,
    )

    with pytest.raises(ValidationError):
        analytics_service.assign_growth_description_goal(db_session, message, reading_goal)

    assert message.goal_id is None


def test_get_chat_message_raises_not_found_for_unknown_id(db_session):
    with pytest.raises(NotFoundError):
        analytics_service.get_chat_message(db_session, 999999)
