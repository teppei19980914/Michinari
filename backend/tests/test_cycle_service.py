"""cycle_service のテスト（ロジック・プロンプト編 6章、20章の検証観点）。"""

import datetime as dt

import pytest

from app.constants.enums import GoalStatus, RecordState
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import DailyRecord, StudyLog
from app.services import cycle_service
from app.services.exceptions import PlannedCyclesBelowCompletedError


def _make_goal(db_session) -> Goal:
    goal = Goal(name="周回検証", start_date=dt.date(2026, 1, 1), status=GoalStatus.ACTIVE)
    db_session.add(goal)
    db_session.flush()
    return goal


def _make_material(db_session, goal_id: int, total_amount: float, planned_cycles: int) -> Material:
    material = Material(
        goal_id=goal_id,
        name="教材",
        unit_label="問",
        total_amount=total_amount,
        planned_cycles=planned_cycles,
        start_date=dt.date(2026, 1, 1),
        due_date=dt.date(2026, 12, 31),
        display_order=1,
    )
    db_session.add(material)
    db_session.flush()
    return material


def _add_study_log(
    db_session, material_id: int, record_date: dt.date, amount: float, cycle: int
) -> None:
    record = DailyRecord(record_date=record_date, record_state=RecordState.PROGRESS_ONLY)
    db_session.add(record)
    db_session.flush()
    db_session.add(
        StudyLog(
            daily_record_id=record.id,
            material_id=material_id,
            minutes_spent=60,
            amount_completed=amount,
            cycle_number=cycle,
        )
    )
    db_session.flush()


def test_remaining_does_not_reach_zero_after_first_cycle_completion(db_session):
    """1周目完了時に残量が0にならず、2周目のノルマが算出されること（Phase2必須観点）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=100, planned_cycles=3)
    _add_study_log(db_session, material.id, dt.date(2026, 1, 2), 100, cycle=1)

    progress = cycle_service.get_material_progress(db_session, material)

    assert progress.total_work == 300
    assert progress.completed == 100
    assert progress.remaining == 200
    assert progress.current_cycle == 2


def test_current_cycle_derived_from_cumulative_completed_amount(db_session):
    """現在周回が累積完了量から正しく導出されること（Phase2必須観点）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=100, planned_cycles=3)
    _add_study_log(db_session, material.id, dt.date(2026, 1, 2), 100, cycle=1)
    _add_study_log(db_session, material.id, dt.date(2026, 1, 3), 50, cycle=2)

    progress = cycle_service.get_material_progress(db_session, material)

    assert progress.current_cycle == 2


def test_current_cycle_capped_at_planned_cycles_when_fully_completed(db_session):
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=100, planned_cycles=2)
    _add_study_log(db_session, material.id, dt.date(2026, 1, 2), 100, cycle=1)
    _add_study_log(db_session, material.id, dt.date(2026, 1, 3), 100, cycle=2)

    progress = cycle_service.get_material_progress(db_session, material)

    assert progress.current_cycle == 2
    assert progress.remaining == 0


def test_progress_with_zero_study_logs_does_not_raise(db_session):
    """境界値: 実績0件のケースで例外が発生しないこと。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=100, planned_cycles=1)

    progress = cycle_service.get_material_progress(db_session, material)

    assert progress.completed == 0
    assert progress.remaining == 100
    assert progress.current_cycle == 1


def test_current_cycle_progress_within_cycle(db_session):
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=100, planned_cycles=2)
    _add_study_log(db_session, material.id, dt.date(2026, 1, 2), 100, cycle=1)
    _add_study_log(db_session, material.id, dt.date(2026, 1, 3), 30, cycle=2)

    progress = cycle_service.get_material_progress(db_session, material)
    cycle_progress = cycle_service.compute_current_cycle_progress(material, progress)

    assert cycle_progress.completed_in_cycle == 30
    assert cycle_progress.progress_rate_in_cycle == pytest.approx(0.3)


def test_validate_planned_cycles_change_rejects_below_current_cycle():
    """予定周回数を完了済み周回数未満に変更できないこと（Phase3完了条件・Phase2で検証する純粋検証ロジック）。"""
    with pytest.raises(PlannedCyclesBelowCompletedError):
        cycle_service.validate_planned_cycles_change(current_cycle=2, new_planned_cycles=1)


def test_validate_planned_cycles_change_allows_equal_or_above():
    cycle_service.validate_planned_cycles_change(current_cycle=2, new_planned_cycles=2)
    cycle_service.validate_planned_cycles_change(current_cycle=2, new_planned_cycles=3)


def test_cumulative_progress_accumulates_by_date_across_multiple_logs_per_day(db_session):
    """分析画面「進捗」タブ: 累積完了量が日付順に積み上がること（同日に複数実績があれば合算）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=100, planned_cycles=2)
    _add_study_log(db_session, material.id, dt.date(2026, 1, 2), 10, cycle=1)
    _add_study_log(db_session, material.id, dt.date(2026, 1, 5), 20, cycle=1)

    points = cycle_service.compute_cumulative_progress(db_session, material.id)

    assert [p.record_date for p in points] == [dt.date(2026, 1, 2), dt.date(2026, 1, 5)]
    assert [p.cumulative_completed for p in points] == [10, 30]


def test_cumulative_progress_empty_when_no_study_logs(db_session):
    """境界値: 実績0件のケースで例外が発生しないこと。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=100, planned_cycles=1)

    assert cycle_service.compute_cumulative_progress(db_session, material.id) == []


def test_cycle_boundaries_mark_dates_where_cumulative_crosses_total_amount(db_session):
    """周回の区切り（累積完了量がtotal_amountの倍数を越えた日付）が特定されること。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=100, planned_cycles=3)
    _add_study_log(db_session, material.id, dt.date(2026, 1, 2), 60, cycle=1)
    # 累積120 -> 1周目境界(100)を越える
    _add_study_log(db_session, material.id, dt.date(2026, 1, 3), 60, cycle=2)
    _add_study_log(db_session, material.id, dt.date(2026, 1, 4), 60, cycle=2)  # 累積180

    points = cycle_service.compute_cumulative_progress(db_session, material.id)
    boundaries = cycle_service.compute_cycle_boundaries(material, points)

    # 2周目(累積200)にはまだ到達していないため、境界は1件のみ
    assert len(boundaries) == 1
    assert boundaries[0].cycle_number == 1
    assert boundaries[0].record_date == dt.date(2026, 1, 3)


def test_cycle_boundaries_excludes_not_yet_reached_boundaries(db_session):
    """境界値: まだ到達していない周回境界は含まれないこと。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=100, planned_cycles=2)
    _add_study_log(db_session, material.id, dt.date(2026, 1, 2), 30, cycle=1)

    points = cycle_service.compute_cumulative_progress(db_session, material.id)
    boundaries = cycle_service.compute_cycle_boundaries(material, points)

    assert boundaries == []


# --- compute_completed_cycles（Phase10: 総括レポート・ナレッジエクスポート向け） ---


def test_compute_completed_cycles_counts_full_cycles_only(db_session):
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=100, planned_cycles=3)
    _add_study_log(db_session, material.id, dt.date(2026, 1, 1), amount=150.0, cycle=1)

    progress = cycle_service.get_material_progress(db_session, material)

    assert cycle_service.compute_completed_cycles(material, progress) == 1


def test_compute_completed_cycles_caps_at_planned_cycles(db_session):
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=100, planned_cycles=2)
    _add_study_log(db_session, material.id, dt.date(2026, 1, 1), amount=250.0, cycle=2)

    progress = cycle_service.get_material_progress(db_session, material)

    assert cycle_service.compute_completed_cycles(material, progress) == 2


def test_compute_completed_cycles_returns_zero_when_total_amount_is_zero(db_session):
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=0, planned_cycles=1)
    progress = cycle_service.MaterialProgress(
        total_work=0, completed=0, remaining=0, current_cycle=1
    )

    assert cycle_service.compute_completed_cycles(material, progress) == 0
