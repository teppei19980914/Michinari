"""analytics_service のテスト（仕様書6.8 SC-09、実装フェーズ分割計画書Phase9）。

analytics_serviceには、既存章（6・8・13・14章）のどれにも属さない分析画面固有の算出
（計画線・成長記述の抽出）のみを置いている。それぞれの算出根拠はcompute_plan_line・
list_growth_descriptionsのdocstringを参照。
"""

import datetime as dt

from app.constants.enums import (
    BaselineReason,
    ChatRole,
    DayType,
    GoalStatus,
    RecordState,
)
from app.models.goal import Goal
from app.models.material import Material, PlanBaseline
from app.models.record import ChatMessage, DailyRecord
from app.models.setting import CalendarDayOverride
from app.services import analytics_service


def _make_goal(db_session) -> Goal:
    goal = Goal(name="分析検証", start_date=dt.date(2026, 1, 1), status=GoalStatus.ACTIVE)
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
    db_session, record_id: int, role: ChatRole, sequence: int, content: str
) -> None:
    db_session.add(
        ChatMessage(daily_record_id=record_id, role=role, content=content, sequence=sequence)
    )
    db_session.flush()


def test_growth_descriptions_returns_assistant_messages_ordered_by_date_desc(db_session):
    """成長記述タブ（ANL-07）: AI応答が新しい日付順に列挙されること。"""
    record1 = _make_record(db_session, dt.date(2026, 1, 5))
    _add_chat_message(db_session, record1.id, ChatRole.USER, 1, "今日は疲れました")
    _add_chat_message(db_session, record1.id, ChatRole.ASSISTANT, 2, "1/5の応答")
    record2 = _make_record(db_session, dt.date(2026, 1, 10))
    _add_chat_message(db_session, record2.id, ChatRole.ASSISTANT, 1, "1/10の応答")

    entries = analytics_service.list_growth_descriptions(db_session)

    assert [e.record_date for e in entries] == [dt.date(2026, 1, 10), dt.date(2026, 1, 5)]
    assert entries[0].content == "1/10の応答"
    assert entries[1].content == "1/5の応答"


def test_growth_descriptions_excludes_user_role_messages(db_session):
    """USER発言（自由入力メッセージ）は成長記述の対象に含めないこと。"""
    record = _make_record(db_session, dt.date(2026, 1, 5))
    _add_chat_message(db_session, record.id, ChatRole.USER, 1, "質問です")

    assert analytics_service.list_growth_descriptions(db_session) == []


def test_growth_descriptions_empty_when_no_chat_messages(db_session):
    """境界値: AI対話が1件も記録されていない場合に例外が発生しないこと。"""
    assert analytics_service.list_growth_descriptions(db_session) == []
