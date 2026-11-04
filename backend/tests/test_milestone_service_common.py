"""milestone_service_common のテスト（開発Todo_節目のお祝い_v1.0 §3.3 B-06）。"""

import datetime as dt

import pytest

from app.constants.app_setting_keys import (
    MILESTONE_CONSECUTIVE_DAYS_THRESHOLDS,
    MILESTONE_TOTAL_RECORD_DAYS_THRESHOLDS,
)
from app.constants.enums import GoalCategory, GoalStatus, MilestoneType, RecordState
from app.models.goal import Goal
from app.models.milestone import GoalMilestoneAchievement
from app.models.record import DailyRecord
from app.services import milestone_service_common as svc
from app.services.exceptions import NotFoundError


def _make_goal(
    db_session,
    category=GoalCategory.EXAM,
    name="節目検証",
    start_date=dt.date(2026, 1, 1),
    status=GoalStatus.ACTIVE,
    **overrides,
):
    goal = Goal(
        name=name,
        category=category,
        start_date=start_date,
        status=status,
        **overrides,
    )
    db_session.add(goal)
    db_session.flush()
    return goal


def _set_threshold(session, key, value):
    from app.models.setting import AppSetting

    row = session.get(AppSetting, key)
    row.value = value


def _report(session, record_date, category=GoalCategory.EXAM):
    record = session.query(DailyRecord).filter(DailyRecord.record_date == record_date).first()
    if record is None:
        record = DailyRecord(record_date=record_date)
        session.add(record)
        session.flush()
    if category == GoalCategory.EXAM:
        record.exam_record_state = RecordState.REPORTED
    elif category == GoalCategory.READING:
        record.reading_record_state = RecordState.REPORTED
    else:
        record.work_record_state = RecordState.REPORTED
    session.flush()
    return record


def test_threshold_milestones_returns_one_entry_per_threshold_reached(seeded_session):
    _set_threshold(seeded_session, MILESTONE_CONSECUTIVE_DAYS_THRESHOLDS, "3,7,14")

    pending = svc.threshold_milestones(
        seeded_session, MILESTONE_CONSECUTIVE_DAYS_THRESHOLDS, 10, MilestoneType.CONSECUTIVE_DAYS
    )

    assert {p.milestone_key for p in pending} == {"3", "7"}


def test_threshold_milestones_accepts_a_float_current_value(seeded_session):
    """資格の全体進捗率(%)はfloatで渡されるため、int専用にしない。"""
    _set_threshold(seeded_session, MILESTONE_CONSECUTIVE_DAYS_THRESHOLDS, "25,50,75")

    pending = svc.threshold_milestones(
        seeded_session, MILESTONE_CONSECUTIVE_DAYS_THRESHOLDS, 60.0, MilestoneType.CONSECUTIVE_DAYS
    )

    assert {p.milestone_key for p in pending} == {"25", "50"}


def test_detect_common_milestones_returns_thresholds_at_or_below_current_value(seeded_session):
    _set_threshold(seeded_session, MILESTONE_CONSECUTIVE_DAYS_THRESHOLDS, "3,7,14")
    _set_threshold(seeded_session, MILESTONE_TOTAL_RECORD_DAYS_THRESHOLDS, "2,5")
    goal = _make_goal(seeded_session, start_date=dt.date(2026, 1, 1))
    for day in range(1, 4):
        _report(seeded_session, dt.date(2026, 1, day))

    pending = svc.detect_common_milestones(seeded_session, goal, dt.date(2026, 1, 3))

    kinds = {(p.milestone_type, p.milestone_key) for p in pending}
    assert (MilestoneType.CONSECUTIVE_DAYS, "3") in kinds
    assert (MilestoneType.CONSECUTIVE_DAYS, "7") not in kinds
    assert (MilestoneType.TOTAL_RECORD_DAYS, "2") in kinds
    assert (MilestoneType.TOTAL_RECORD_DAYS, "5") not in kinds


def test_detect_and_record_new_achievements_persists_and_is_idempotent(seeded_session):
    _set_threshold(seeded_session, MILESTONE_CONSECUTIVE_DAYS_THRESHOLDS, "3")
    _set_threshold(seeded_session, MILESTONE_TOTAL_RECORD_DAYS_THRESHOLDS, "3")
    goal = _make_goal(seeded_session, start_date=dt.date(2026, 2, 1))
    for day in range(1, 4):
        _report(seeded_session, dt.date(2026, 2, day))

    created_first = svc.detect_and_record_new_achievements(
        seeded_session, goal, dt.date(2026, 2, 3)
    )
    assert len(created_first) == 2
    assert all(row.celebrated_at is None for row in created_first)

    created_second = svc.detect_and_record_new_achievements(
        seeded_session, goal, dt.date(2026, 2, 3)
    )
    assert created_second == []

    total_rows = (
        seeded_session.query(GoalMilestoneAchievement)
        .filter(GoalMilestoneAchievement.goal_id == goal.id)
        .count()
    )
    assert total_rows == 2


def test_detect_and_record_for_category_only_targets_active_goals_of_that_category(seeded_session):
    _set_threshold(seeded_session, MILESTONE_CONSECUTIVE_DAYS_THRESHOLDS, "1")
    _set_threshold(seeded_session, MILESTONE_TOTAL_RECORD_DAYS_THRESHOLDS, "999")
    active_goal = _make_goal(
        seeded_session, start_date=dt.date(2026, 3, 1), status=GoalStatus.ACTIVE
    )
    paused_goal = _make_goal(
        seeded_session, start_date=dt.date(2026, 3, 1), status=GoalStatus.PAUSED
    )
    other_category_goal = _make_goal(
        seeded_session,
        category=GoalCategory.READING,
        start_date=dt.date(2026, 3, 1),
        status=GoalStatus.ACTIVE,
    )
    _report(seeded_session, dt.date(2026, 3, 1))

    svc.detect_and_record_for_category(seeded_session, GoalCategory.EXAM, dt.date(2026, 3, 1))

    assert (
        seeded_session.query(GoalMilestoneAchievement)
        .filter(GoalMilestoneAchievement.goal_id == active_goal.id)
        .count()
        == 1
    )
    assert (
        seeded_session.query(GoalMilestoneAchievement)
        .filter(GoalMilestoneAchievement.goal_id == paused_goal.id)
        .count()
        == 0
    )
    assert (
        seeded_session.query(GoalMilestoneAchievement)
        .filter(GoalMilestoneAchievement.goal_id == other_category_goal.id)
        .count()
        == 0
    )


def test_detect_and_record_for_category_computes_reading_totals_once(seeded_session, monkeypatch):
    """performance-reviewer指摘（2026-11-05）の回帰テスト：READING目標が複数あっても、
    利用者の読書全体を対象とするlifetime集計（累計ページ数・読了冊数）は1回だけ算出する。
    """
    from app.services import book_service

    _make_goal(seeded_session, category=GoalCategory.READING, name="読書目標A")
    _make_goal(seeded_session, category=GoalCategory.READING, name="読書目標B")
    _make_goal(seeded_session, category=GoalCategory.READING, name="読書目標C")

    call_count = 0
    original = book_service.sum_cumulative_pages_read

    def _counting_sum(session):
        nonlocal call_count
        call_count += 1
        return original(session)

    monkeypatch.setattr(book_service, "sum_cumulative_pages_read", _counting_sum)

    svc.detect_and_record_for_category(seeded_session, GoalCategory.READING, dt.date(2026, 1, 1))

    assert call_count == 1


def test_backfill_computes_reading_totals_once_across_all_reading_goals(
    seeded_session, monkeypatch
):
    """同上（起動時バックフィルも同じ対象）。"""
    from app.services import book_service

    _make_goal(seeded_session, category=GoalCategory.READING, name="読書目標A")
    _make_goal(seeded_session, category=GoalCategory.READING, name="読書目標B")

    call_count = 0
    original = book_service.count_completed_books

    def _counting_count(session):
        nonlocal call_count
        call_count += 1
        return original(session)

    monkeypatch.setattr(book_service, "count_completed_books", _counting_count)

    svc.backfill_achievements_if_needed(seeded_session, dt.date(2026, 1, 1))

    assert call_count == 1


def test_list_pending_celebrations_excludes_already_celebrated(seeded_session):
    goal = _make_goal(seeded_session)
    now = dt.datetime(2026, 1, 1, 0, 0, 0)
    seeded_session.add_all(
        [
            GoalMilestoneAchievement(
                goal_id=goal.id,
                milestone_type=MilestoneType.CONSECUTIVE_DAYS,
                milestone_key="3",
                achieved_at=now,
                celebrated_at=None,
            ),
            GoalMilestoneAchievement(
                goal_id=goal.id,
                milestone_type=MilestoneType.CONSECUTIVE_DAYS,
                milestone_key="7",
                achieved_at=now,
                celebrated_at=now,
            ),
        ]
    )
    seeded_session.flush()

    pending = svc.list_pending_celebrations(seeded_session, goal.id)

    assert [row.milestone_key for row in pending] == ["3"]


def test_list_achievements_returns_newest_first(seeded_session):
    goal = _make_goal(seeded_session)
    earlier = dt.datetime(2026, 1, 1, 0, 0, 0)
    later = dt.datetime(2026, 1, 5, 0, 0, 0)
    seeded_session.add_all(
        [
            GoalMilestoneAchievement(
                goal_id=goal.id,
                milestone_type=MilestoneType.CONSECUTIVE_DAYS,
                milestone_key="3",
                achieved_at=earlier,
                celebrated_at=earlier,
            ),
            GoalMilestoneAchievement(
                goal_id=goal.id,
                milestone_type=MilestoneType.CONSECUTIVE_DAYS,
                milestone_key="7",
                achieved_at=later,
                celebrated_at=None,
            ),
        ]
    )
    seeded_session.flush()

    rows = svc.list_achievements(seeded_session, goal.id)

    assert [row.milestone_key for row in rows] == ["7", "3"]


def test_mark_celebrated_sets_timestamp(seeded_session):
    goal = _make_goal(seeded_session)
    row = GoalMilestoneAchievement(
        goal_id=goal.id,
        milestone_type=MilestoneType.CONSECUTIVE_DAYS,
        milestone_key="3",
        achieved_at=dt.datetime(2026, 1, 1),
        celebrated_at=None,
    )
    seeded_session.add(row)
    seeded_session.flush()

    now = dt.datetime(2026, 1, 2)
    updated = svc.mark_celebrated(seeded_session, goal.id, row.id, now)

    assert updated.celebrated_at == now


def test_mark_celebrated_rejects_milestone_of_another_goal(seeded_session):
    goal = _make_goal(seeded_session)
    other_goal = _make_goal(seeded_session, name="別の目標")
    row = GoalMilestoneAchievement(
        goal_id=other_goal.id,
        milestone_type=MilestoneType.CONSECUTIVE_DAYS,
        milestone_key="3",
        achieved_at=dt.datetime(2026, 1, 1),
        celebrated_at=None,
    )
    seeded_session.add(row)
    seeded_session.flush()

    with pytest.raises(NotFoundError):
        svc.mark_celebrated(seeded_session, goal.id, row.id, dt.datetime(2026, 1, 2))


def test_mark_celebrated_rejects_nonexistent_id(seeded_session):
    goal = _make_goal(seeded_session)

    with pytest.raises(NotFoundError):
        svc.mark_celebrated(seeded_session, goal.id, 999999, dt.datetime(2026, 1, 2))


def test_backfill_marks_existing_milestones_as_already_celebrated(seeded_session):
    _set_threshold(seeded_session, MILESTONE_CONSECUTIVE_DAYS_THRESHOLDS, "1")
    _set_threshold(seeded_session, MILESTONE_TOTAL_RECORD_DAYS_THRESHOLDS, "999")
    goal = _make_goal(seeded_session, start_date=dt.date(2026, 4, 1))
    _report(seeded_session, dt.date(2026, 4, 1))

    svc.backfill_achievements_if_needed(seeded_session, dt.date(2026, 4, 1))

    rows = (
        seeded_session.query(GoalMilestoneAchievement)
        .filter(GoalMilestoneAchievement.goal_id == goal.id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].celebrated_at is not None
    assert rows[0].achieved_at == rows[0].celebrated_at


def test_detect_and_record_new_achievements_dispatches_to_reading(seeded_session):
    """READING目標への種別固有ディスパッチ（本棚が無い状態でも空リストで安全に動くこと）。"""
    goal = _make_goal(seeded_session, category=GoalCategory.READING)

    created = svc.detect_and_record_new_achievements(seeded_session, goal, dt.date(2026, 1, 1))

    assert isinstance(created, list)


def test_detect_and_record_new_achievements_dispatches_to_work(seeded_session):
    """WORK目標への種別固有ディスパッチ（案件情報が無い状態でも空リストで安全に動くこと）。"""
    goal = _make_goal(seeded_session, category=GoalCategory.WORK)

    created = svc.detect_and_record_new_achievements(seeded_session, goal, dt.date(2026, 1, 1))

    assert isinstance(created, list)


def test_backfill_is_a_no_op_on_second_call(seeded_session):
    _set_threshold(seeded_session, MILESTONE_CONSECUTIVE_DAYS_THRESHOLDS, "1")
    goal = _make_goal(seeded_session, start_date=dt.date(2026, 5, 1))
    _report(seeded_session, dt.date(2026, 5, 1))

    svc.backfill_achievements_if_needed(seeded_session, dt.date(2026, 5, 1))
    first_count = (
        seeded_session.query(GoalMilestoneAchievement)
        .filter(GoalMilestoneAchievement.goal_id == goal.id)
        .count()
    )

    # 2回目はフラグが立っているため、新たな記録確定が無くても何も増えない
    # （新規到達があっても拾わない＝これが「一度きり」の意図した挙動）。
    _report(seeded_session, dt.date(2026, 5, 2))
    svc.backfill_achievements_if_needed(seeded_session, dt.date(2026, 5, 2))
    second_count = (
        seeded_session.query(GoalMilestoneAchievement)
        .filter(GoalMilestoneAchievement.goal_id == goal.id)
        .count()
    )

    assert first_count == 1
    assert second_count == 1
