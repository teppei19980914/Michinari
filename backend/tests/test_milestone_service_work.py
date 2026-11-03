"""milestone_service_work のテスト（開発Todo_節目のお祝い_v1.0 §3.3 B-09）。"""

import datetime as dt

from app.constants.app_setting_keys import MILESTONE_WORK_RECORD_COUNT_THRESHOLDS
from app.constants.enums import (
    GoalCategory,
    GoalStatus,
    MilestoneType,
    RecordState,
    RetrospectivePeriodType,
)
from app.models.goal import Goal
from app.models.record import DailyRecord, WorkLog
from app.models.retrospective import GoalRetrospective
from app.models.setting import AppSetting
from app.models.work import WorkAssignment
from app.services import milestone_service_work as svc


def _make_work_goal(session, *, name="仕事目標", start_date=dt.date(2026, 1, 1)) -> Goal:
    goal = Goal(
        category=GoalCategory.WORK, name=name, start_date=start_date, status=GoalStatus.ACTIVE
    )
    session.add(goal)
    session.flush()
    return goal


def _make_work_assignment(session, goal, start_date=dt.date(2026, 1, 1)) -> WorkAssignment:
    work_assignment = WorkAssignment(
        goal_id=goal.id,
        client_name="取引先A",
        expected_content="想定業務内容",
        start_date=start_date,
    )
    session.add(work_assignment)
    session.flush()
    return work_assignment


def _add_work_log(session, work_assignment_id, record_date):
    record = DailyRecord(record_date=record_date, work_record_state=RecordState.PROGRESS_ONLY)
    session.add(record)
    session.flush()
    session.add(
        WorkLog(daily_record_id=record.id, work_assignment_id=work_assignment_id, body="業務内容")
    )
    session.flush()


def _add_monthly_report(session, goal_id, period_key):
    session.add(
        GoalRetrospective(
            goal_id=goal_id,
            body="月次報告",
            period_type=RetrospectivePeriodType.MONTHLY,
            period_key=period_key,
            is_anonymized=False,
        )
    )
    session.flush()


def _set_threshold(session, key, value):
    row = session.get(AppSetting, key)
    row.value = value


def test_detect_work_milestones_returns_empty_without_assignment(seeded_session):
    goal = _make_work_goal(seeded_session)

    assert svc.detect_work_milestones(seeded_session, goal, dt.date(2026, 1, 1)) == []


def test_detect_work_milestones_reports_record_count_threshold(seeded_session):
    _set_threshold(seeded_session, MILESTONE_WORK_RECORD_COUNT_THRESHOLDS, "2,5")
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 1))
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 2))

    pending = svc.detect_work_milestones(seeded_session, goal, dt.date(2026, 1, 2))

    keys = {p.milestone_key for p in pending if p.milestone_type == MilestoneType.WORK_RECORD_COUNT}
    assert keys == {"2"}


def test_detect_work_milestones_reports_evaluation_period_completed_when_all_months_reported(
    seeded_session,
):
    goal = _make_work_goal(seeded_session, start_date=dt.date(2025, 3, 1))
    _make_work_assignment(seeded_session, goal, start_date=dt.date(2025, 3, 1))
    for month in range(3, 9):
        _add_monthly_report(seeded_session, goal.id, f"2025-{month:02d}")

    # todayが2025-H2（2025-09-01以降）に入った直後に、直前のH1（2025-03〜08）を判定する。
    pending = svc.detect_work_milestones(seeded_session, goal, dt.date(2025, 9, 1))

    keys = {
        p.milestone_key
        for p in pending
        if p.milestone_type == MilestoneType.WORK_EVALUATION_PERIOD_COMPLETED
    }
    assert keys == {"2025-H1"}


def test_detect_work_milestones_does_not_report_when_a_month_is_missing(seeded_session):
    goal = _make_work_goal(seeded_session, start_date=dt.date(2025, 3, 1))
    _make_work_assignment(seeded_session, goal, start_date=dt.date(2025, 3, 1))
    for month in (3, 4, 5, 6, 8):  # 7月分が無い
        _add_monthly_report(seeded_session, goal.id, f"2025-{month:02d}")

    pending = svc.detect_work_milestones(seeded_session, goal, dt.date(2025, 9, 1))

    keys = {
        p.milestone_key
        for p in pending
        if p.milestone_type == MilestoneType.WORK_EVALUATION_PERIOD_COMPLETED
    }
    assert keys == set()


def test_monthly_keys_in_semiannual_h2_spans_the_year_boundary():
    assert svc._monthly_keys_in_semiannual("2025-H2") == [
        "2025-09",
        "2025-10",
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
    ]


def test_monthly_keys_in_semiannual_h1():
    assert svc._monthly_keys_in_semiannual("2026-H1") == [
        "2026-03",
        "2026-04",
        "2026-05",
        "2026-06",
        "2026-07",
        "2026-08",
    ]
