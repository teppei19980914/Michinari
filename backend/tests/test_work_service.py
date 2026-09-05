"""work_service のテスト（データ構造編6.2、実装フェーズ分割計画書Phase21）。

CRUDはgoal_service・book_serviceと同様にAPI層のテスト（test_api_goals.py）で検証し、
ここでは算出ロジック（経過日数・直近記録日・連続記録日数・直近の月次報告有無）のみを
対象とする（test_book_service.pyと同じ方針、CLAUDE.md DRYの原則）。today はrecord_service等
と同様に呼び出し側から明示的に渡す設計のため、システム時刻に依存せず決定論的にテストできる。
"""

import datetime as dt

from app.constants.enums import GoalCategory, GoalStatus, RecordState, RetrospectivePeriodType
from app.models.goal import Goal
from app.models.record import DailyRecord, WorkLog
from app.models.retrospective import GoalRetrospective
from app.models.work import WorkAssignment
from app.services import work_service


def _make_work_goal(session, *, name="仕事目標") -> Goal:
    goal = Goal(
        category=GoalCategory.WORK,
        name=name,
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
        resource_ratio=0,
    )
    session.add(goal)
    session.flush()
    return goal


def _make_work_assignment(session, goal, *, start_date=dt.date(2026, 1, 1)) -> WorkAssignment:
    work_assignment = WorkAssignment(
        goal_id=goal.id,
        client_name="取引先A",
        expected_content="想定業務内容",
        start_date=start_date,
    )
    session.add(work_assignment)
    session.flush()
    return work_assignment


def _add_work_log(session, work_assignment_id: int, record_date: dt.date, body="業務内容") -> None:
    record = DailyRecord(record_date=record_date, work_record_state=RecordState.PROGRESS_ONLY)
    session.add(record)
    session.flush()
    session.add(
        WorkLog(daily_record_id=record.id, work_assignment_id=work_assignment_id, body=body)
    )
    session.flush()


def test_elapsed_days_is_today_minus_start_date(db_session):
    goal = _make_work_goal(db_session)
    work_assignment = _make_work_assignment(db_session, goal, start_date=dt.date(2026, 1, 1))

    progress = work_service.get_work_assignment_progress(
        db_session, work_assignment, dt.date(2026, 1, 10)
    )

    assert progress.elapsed_days == 9


def test_last_work_date_from_latest_entry(db_session):
    goal = _make_work_goal(db_session)
    work_assignment = _make_work_assignment(db_session, goal)
    _add_work_log(db_session, work_assignment.id, dt.date(2026, 1, 1))
    _add_work_log(db_session, work_assignment.id, dt.date(2026, 1, 3))

    progress = work_service.get_work_assignment_progress(
        db_session, work_assignment, dt.date(2026, 1, 5)
    )

    assert progress.last_work_date == dt.date(2026, 1, 3)


def test_no_work_logs_returns_none_last_date_and_zero_streak(db_session):
    goal = _make_work_goal(db_session)
    work_assignment = _make_work_assignment(db_session, goal)

    progress = work_service.get_work_assignment_progress(
        db_session, work_assignment, dt.date(2026, 1, 5)
    )

    assert progress.last_work_date is None
    assert progress.current_streak == 0
    assert progress.has_recent_monthly_report is False


def test_current_streak_counts_consecutive_days_ending_today(db_session):
    goal = _make_work_goal(db_session)
    work_assignment = _make_work_assignment(db_session, goal)
    today = dt.date(2026, 1, 10)
    _add_work_log(db_session, work_assignment.id, today)
    _add_work_log(db_session, work_assignment.id, today - dt.timedelta(days=1))
    _add_work_log(db_session, work_assignment.id, today - dt.timedelta(days=2))
    # 3日連続の手前（4日前）は記録なし。

    progress = work_service.get_work_assignment_progress(db_session, work_assignment, today)

    assert progress.current_streak == 3


def test_current_streak_is_zero_when_today_has_no_entry(db_session):
    goal = _make_work_goal(db_session)
    work_assignment = _make_work_assignment(db_session, goal)
    today = dt.date(2026, 1, 10)
    _add_work_log(db_session, work_assignment.id, today - dt.timedelta(days=1))

    progress = work_service.get_work_assignment_progress(db_session, work_assignment, today)

    assert progress.current_streak == 0


def test_current_streak_ignores_other_work_assignments(db_session):
    """他の案件のwork_logは連続記録日数に影響しない（work_assignment_idでの絞り込み確認）。"""
    goal_a = _make_work_goal(db_session, name="仕事目標A")
    goal_b = _make_work_goal(db_session, name="仕事目標B")
    work_assignment_a = _make_work_assignment(db_session, goal_a)
    work_assignment_b = _make_work_assignment(db_session, goal_b)
    today = dt.date(2026, 1, 10)
    _add_work_log(db_session, work_assignment_b.id, today)

    progress = work_service.get_work_assignment_progress(db_session, work_assignment_a, today)

    assert progress.current_streak == 0
    assert progress.last_work_date is None


def test_has_recent_monthly_report_true_when_monthly_retrospective_exists(db_session):
    goal = _make_work_goal(db_session)
    work_assignment = _make_work_assignment(db_session, goal)
    db_session.add(
        GoalRetrospective(
            goal_id=goal.id,
            body="月次報告本文",
            period_type=RetrospectivePeriodType.MONTHLY,
            period_key="2026-01",
        )
    )
    db_session.flush()

    progress = work_service.get_work_assignment_progress(
        db_session, work_assignment, dt.date(2026, 2, 1)
    )

    assert progress.has_recent_monthly_report is True


def test_has_recent_monthly_report_false_for_semiannual_only(db_session):
    """半期評価のみでは「直近の月次報告有無」はFalseのまま（period_type=MONTHLYのみ対象）。"""
    goal = _make_work_goal(db_session)
    work_assignment = _make_work_assignment(db_session, goal)
    db_session.add(
        GoalRetrospective(
            goal_id=goal.id,
            body="半期評価本文",
            period_type=RetrospectivePeriodType.SEMI_ANNUAL,
            period_key="2026-H1",
        )
    )
    db_session.flush()

    progress = work_service.get_work_assignment_progress(
        db_session, work_assignment, dt.date(2026, 9, 1)
    )

    assert progress.has_recent_monthly_report is False


def test_has_recent_monthly_report_ignores_anonymized_only(db_session):
    """匿名化版のみが存在する場合は対象外（is_anonymized=Falseの行のみ数える）。"""
    goal = _make_work_goal(db_session)
    work_assignment = _make_work_assignment(db_session, goal)
    db_session.add(
        GoalRetrospective(
            goal_id=goal.id,
            body="匿名化版",
            period_type=RetrospectivePeriodType.MONTHLY,
            period_key="2026-01",
            is_anonymized=True,
        )
    )
    db_session.flush()

    progress = work_service.get_work_assignment_progress(
        db_session, work_assignment, dt.date(2026, 2, 1)
    )

    assert progress.has_recent_monthly_report is False
