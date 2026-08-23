"""threshold_service のテスト（ロジック・プロンプト編 11章、20章の検証観点）。

閾値は app_setting から読むため、初期データ投入済みの seeded_session を使う。
"""

import datetime as dt

from app.constants.enums import BaselineReason, DayType, GoalStatus
from app.models.goal import Goal
from app.models.material import Material
from app.services import baseline_service, threshold_service


def _make_material(seeded_session, due_date: dt.date = dt.date(2026, 12, 31)) -> Material:
    goal = Goal(name="判定検証", start_date=dt.date(2026, 1, 1), status=GoalStatus.ACTIVE)
    seeded_session.add(goal)
    seeded_session.flush()
    material = Material(
        goal_id=goal.id,
        name="教材",
        unit_label="問",
        total_amount=100,
        planned_cycles=1,
        start_date=dt.date(2026, 1, 1),
        due_date=due_date,
        display_order=1,
    )
    seeded_session.add(material)
    seeded_session.flush()
    return material


def test_warning_not_judged_when_today_is_not_plan_day(seeded_session):
    """バッファ日に警告判定が行われないこと（Phase2完了条件・20章）。"""
    material = _make_material(seeded_session)

    result = threshold_service.check_warning(
        seeded_session, material.id, dt.date(2026, 1, 1), DayType.BUFFER, quota_today=100.0
    )

    assert result is False


def test_warning_false_when_no_baseline_exists(seeded_session):
    """境界値: 基準値が存在しない場合に例外が発生せずFalseとなること。"""
    material = _make_material(seeded_session)

    result = threshold_service.check_warning(
        seeded_session, material.id, dt.date(2026, 1, 1), DayType.PLAN, quota_today=100.0
    )

    assert result is False


def test_warning_true_when_ratio_meets_threshold(seeded_session):
    """警告倍率の閾値が設定値から読まれること（20章）。初期値1.20を用いる。"""
    material = _make_material(seeded_session)
    baseline_service.record_baseline(
        seeded_session,
        material,
        reason=BaselineReason.INITIAL,
        effective_from=dt.date(2026, 1, 1),
        baseline_daily_quota=10.0,
        remaining_at_baseline=100.0,
        plan_days_at_baseline=10,
    )

    # 10 × 1.20 = 12（閾値ちょうど）
    assert threshold_service.check_warning(
        seeded_session, material.id, dt.date(2026, 1, 1), DayType.PLAN, quota_today=12.0
    )
    # 閾値未満は警告なし
    assert not threshold_service.check_warning(
        seeded_session, material.id, dt.date(2026, 1, 1), DayType.PLAN, quota_today=11.9
    )


def test_forced_replan_not_judged_when_speed_unavailable(seeded_session):
    """speed_eff算出不能（overrun_days=None）の場合は強制リプラン判定を行わないこと（Phase2完了条件）。"""
    assert threshold_service.check_forced_replan(seeded_session, overrun_days=None) is False


def test_forced_replan_uses_threshold_from_setting(seeded_session):
    """超過日数の閾値が設定値から読まれること（20章）。初期値3日を用いる。"""
    assert threshold_service.check_forced_replan(seeded_session, overrun_days=3) is False
    assert threshold_service.check_forced_replan(seeded_session, overrun_days=4) is True


def test_deadline_overrun_true_when_past_due_with_remaining(seeded_session):
    material = _make_material(seeded_session, due_date=dt.date(2026, 1, 5))

    assert threshold_service.check_deadline_overrun(dt.date(2026, 1, 10), material, remaining=10.0)
    assert not threshold_service.check_deadline_overrun(
        dt.date(2026, 1, 10), material, remaining=0.0
    )
    assert not threshold_service.check_deadline_overrun(
        dt.date(2026, 1, 1), material, remaining=10.0
    )
