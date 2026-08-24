"""baseline_service のテスト（ロジック・プロンプト編 12章）。"""

import datetime as dt

from app.constants.enums import BaselineReason, GoalStatus
from app.models.goal import Goal
from app.models.material import Material
from app.services import baseline_service


def _make_goal_and_material(db_session) -> Material:
    goal = Goal(name="基準値検証", start_date=dt.date(2026, 1, 1), status=GoalStatus.ACTIVE)
    db_session.add(goal)
    db_session.flush()
    material = Material(
        goal_id=goal.id,
        name="教材",
        unit_label="問",
        total_amount=100,
        planned_cycles=2,
        start_date=dt.date(2026, 1, 1),
        due_date=dt.date(2026, 12, 31),
        display_order=1,
    )
    db_session.add(material)
    db_session.flush()
    return material


def test_record_baseline_persists_all_fields(db_session):
    material = _make_goal_and_material(db_session)

    baseline = baseline_service.record_baseline(
        db_session,
        material,
        reason=BaselineReason.INITIAL,
        effective_from=dt.date(2026, 1, 1),
        baseline_daily_quota=5.0,
        remaining_at_baseline=200.0,
        plan_days_at_baseline=300,
    )

    assert baseline.id is not None
    assert baseline.planned_cycles_at_baseline == material.planned_cycles
    assert baseline.reason == BaselineReason.INITIAL


def test_get_current_baseline_returns_latest_effective_record(db_session):
    """リプラン後に新しい基準で警告判定が行われること（12.3、20章）の前提となる取得挙動。"""
    material = _make_goal_and_material(db_session)
    baseline_service.record_baseline(
        db_session,
        material,
        reason=BaselineReason.INITIAL,
        effective_from=dt.date(2026, 1, 1),
        baseline_daily_quota=5.0,
        remaining_at_baseline=200.0,
        plan_days_at_baseline=300,
    )
    replanned = baseline_service.record_baseline(
        db_session,
        material,
        reason=BaselineReason.REPLAN,
        effective_from=dt.date(2026, 3, 1),
        baseline_daily_quota=8.0,
        remaining_at_baseline=150.0,
        plan_days_at_baseline=200,
    )

    current = baseline_service.get_current_baseline(db_session, material.id, dt.date(2026, 6, 1))

    assert current.id == replanned.id
    assert current.reason == BaselineReason.REPLAN


def test_get_current_baseline_ignores_future_records(db_session):
    material = _make_goal_and_material(db_session)
    initial = baseline_service.record_baseline(
        db_session,
        material,
        reason=BaselineReason.INITIAL,
        effective_from=dt.date(2026, 1, 1),
        baseline_daily_quota=5.0,
        remaining_at_baseline=200.0,
        plan_days_at_baseline=300,
    )
    baseline_service.record_baseline(
        db_session,
        material,
        reason=BaselineReason.REPLAN,
        effective_from=dt.date(2026, 6, 1),
        baseline_daily_quota=8.0,
        remaining_at_baseline=150.0,
        plan_days_at_baseline=200,
    )

    current = baseline_service.get_current_baseline(db_session, material.id, dt.date(2026, 3, 1))

    assert current.id == initial.id


def test_get_current_baseline_none_when_no_record(db_session):
    """境界値: 基準値が1件も無い場合に例外が発生しないこと。"""
    material = _make_goal_and_material(db_session)

    assert (
        baseline_service.get_current_baseline(db_session, material.id, dt.date(2026, 6, 1)) is None
    )
