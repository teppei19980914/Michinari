"""record_service_work のテスト（設計書データ構造編5.4・6.2、仕様書6.4〜6.7・7.2・14章、
実装フェーズ分割計画書Phase21・S02）。共通処理・カテゴリ横断の相互独立性のテストは
test_record_service_common.pyを参照（実装フェーズ分割計画書S02、test_record_service.py
からの分割）。
"""

import datetime as dt

import pytest

from app.constants.enums import GoalCategory, GoalStatus, RecordState
from app.models.goal import Goal
from app.models.record import WeeklySummary
from app.models.work import WorkAssignment
from app.services import record_service_common, record_service_work
from app.services.exceptions import ImmutableRecordError, NotFoundError
from app.services.record_service_work import WorkLogItem


def _make_work_goal(session, status=GoalStatus.ACTIVE, name="仕事目標A"):
    goal = Goal(
        category=GoalCategory.WORK,
        name=name,
        start_date=dt.date(2026, 1, 1),
        status=status,
    )
    session.add(goal)
    session.flush()
    return goal


def _make_work_assignment(session, goal, **overrides):
    defaults = dict(
        goal_id=goal.id,
        expected_content="想定業務内容",
        start_date=dt.date(2026, 1, 1),
    )
    defaults.update(overrides)
    work_assignment = WorkAssignment(**defaults)
    session.add(work_assignment)
    session.flush()
    return work_assignment


def _work_log(work_assignment_id, **overrides):
    defaults = dict(work_assignment_id=work_assignment_id, body="今日の業務内容")
    defaults.update(overrides)
    return WorkLogItem(**defaults)


def test_register_progress_creates_work_log(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service_common.register_progress(
        seeded_session, today, [], today, work_items=[_work_log(work_assignment.id)]
    )

    assert len(record.work_logs) == 1
    assert record.work_logs[0].body == "今日の業務内容"


def test_register_progress_accepts_work_only_without_study_logs(seeded_session):
    """資格試験のstudy_logsが空でも、仕事のwork_logsのみで登録できる
    （複数カテゴリの目標が同時進行しうるため、study_logsを必須にできない）。"""
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service_common.register_progress(
        seeded_session, today, [], today, work_items=[_work_log(work_assignment.id)]
    )

    assert record.work_record_state == RecordState.PROGRESS_ONLY
    assert record.exam_record_state is None


def test_register_progress_rejects_unknown_work_assignment(seeded_session):
    today = dt.date(2026, 3, 10)

    with pytest.raises(NotFoundError):
        record_service_common.register_progress(
            seeded_session, today, [], today, work_items=[_work_log(9999)]
        )


def test_register_progress_updates_existing_work_log_for_same_assignment(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record_service_common.register_progress(
        seeded_session, today, [], today, work_items=[_work_log(work_assignment.id)]
    )
    record = record_service_common.register_progress(
        seeded_session,
        today,
        [],
        today,
        work_items=[_work_log(work_assignment.id, body="上書き後の業務内容")],
    )

    assert len(record.work_logs) == 1
    assert record.work_logs[0].body == "上書き後の業務内容"


def test_finalize_work_record_persists_work_log(seeded_session):
    """仕事の確定は/finalize（EXAM）とは独立した専用関数（仕様変更2026-09-05）。"""
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service_work.finalize_work_record(
        seeded_session, today, [_work_log(work_assignment.id)], today
    )

    assert record.work_record_state == RecordState.REPORTED
    assert record.exam_record_state is None
    assert len(record.work_logs) == 1


def test_finalize_work_record_allows_work_log_without_study_or_diary(seeded_session):
    """業務記録のみの入力でも確定できる（要件定義書R-75「数値実績の入力を必須としない」）。"""
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service_work.finalize_work_record(
        seeded_session, today, [_work_log(work_assignment.id)], today
    )

    assert record.work_record_state == RecordState.REPORTED
    assert len(record.work_logs) == 1


def test_finalize_work_record_rejects_already_reported(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    today = dt.date(2026, 3, 10)
    record_service_work.finalize_work_record(
        seeded_session, today, [_work_log(work_assignment.id)], today
    )

    with pytest.raises(ImmutableRecordError):
        record_service_work.finalize_work_record(
            seeded_session, today, [_work_log(work_assignment.id)], today
        )


# --- 前回の記録（記録画面改善タスク2026-09-17、get_previous_work_log） ---


def test_get_previous_work_log_returns_most_recent_before_target_date(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    record_service_work.finalize_work_record(
        seeded_session,
        dt.date(2026, 3, 8),
        [_work_log(work_assignment.id, body="3/8の業務内容")],
        dt.date(2026, 3, 8),
    )
    record_service_work.finalize_work_record(
        seeded_session,
        dt.date(2026, 3, 9),
        [_work_log(work_assignment.id, body="3/9の業務内容")],
        dt.date(2026, 3, 9),
    )

    entry = record_service_work.get_previous_work_log(
        seeded_session, work_assignment.id, dt.date(2026, 3, 10)
    )

    assert entry.record_date == dt.date(2026, 3, 9)
    assert entry.body == "3/9の業務内容"


def test_get_previous_work_log_returns_none_when_no_record_exists(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)

    entry = record_service_work.get_previous_work_log(
        seeded_session, work_assignment.id, dt.date(2026, 3, 10)
    )

    assert entry is None


# --- 週次要約の無効化（G4、開発Todo S06） ---


def test_register_progress_invalidates_existing_weekly_summary_for_edited_week(seeded_session):
    """既に週次要約が生成済みの過去週へ業務記録を追記すると、その週の要約（非匿名化・
    匿名化とも）が削除される（record_service_examと同じ理由の横展開）。"""
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    week_start = dt.date(2026, 3, 2)  # 月曜
    edited_date = dt.date(2026, 3, 4)  # 同じ週の水曜
    non_anon = WeeklySummary(
        goal_id=goal.id,
        week_start_date=week_start,
        week_end_date=week_start + dt.timedelta(days=6),
        summary_body="既に生成済み",
    )
    anon = WeeklySummary(
        goal_id=goal.id,
        week_start_date=week_start,
        week_end_date=week_start + dt.timedelta(days=6),
        summary_body="既に生成済み（匿名化版）",
        is_anonymized=True,
    )
    seeded_session.add_all([non_anon, anon])
    seeded_session.flush()

    record_service_common.register_progress(
        seeded_session,
        edited_date,
        [],
        dt.date(2026, 3, 10),
        work_items=[_work_log(work_assignment.id)],
    )

    assert seeded_session.get(WeeklySummary, non_anon.id) is None
    assert seeded_session.get(WeeklySummary, anon.id) is None
