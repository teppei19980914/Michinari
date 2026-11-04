"""milestone_service_reading のテスト（開発Todo_節目のお祝い_v1.0 §3.3 B-08）。"""

import datetime as dt

from app.constants.app_setting_keys import (
    MILESTONE_READING_COMPLETED_BOOKS_THRESHOLDS,
    MILESTONE_READING_TOTAL_PAGES_THRESHOLDS,
)
from app.constants.enums import GoalStatus, MilestoneType, RecordState
from app.models.record import DailyRecord, ReadingLog
from app.models.setting import AppSetting
from app.services import milestone_service_reading as svc
from tests import reading_helpers


def _add_reading_log(session, book_id, record_date, current_page):
    record = DailyRecord(record_date=record_date, reading_record_state=RecordState.PROGRESS_ONLY)
    session.add(record)
    session.flush()
    session.add(
        ReadingLog(
            daily_record_id=record.id,
            book_id=book_id,
            recall_body="想起本文",
            current_page=current_page,
        )
    )
    session.flush()


def _set_threshold(session, key, value):
    row = session.get(AppSetting, key)
    row.value = value


def test_detect_reading_milestones_reports_total_pages_threshold(seeded_session):
    _set_threshold(seeded_session, MILESTONE_READING_TOTAL_PAGES_THRESHOLDS, "100,500")
    goal = reading_helpers.make_reading_goal(seeded_session)
    book = reading_helpers.make_book(seeded_session, goal.id)
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 1), 150)

    pending = svc.detect_reading_milestones(seeded_session, goal, dt.date(2026, 1, 1))

    keys = {
        p.milestone_key for p in pending if p.milestone_type == MilestoneType.READING_TOTAL_PAGES
    }
    assert keys == {"100"}


def test_detect_reading_milestones_reports_completed_books_threshold(seeded_session):
    _set_threshold(seeded_session, MILESTONE_READING_COMPLETED_BOOKS_THRESHOLDS, "1,3")
    goal = reading_helpers.make_reading_goal(seeded_session, name="読了済み")
    goal.status = GoalStatus.CLOSED_WITH_RESULT
    reading_helpers.make_book(seeded_session, goal.id)
    seeded_session.flush()

    pending = svc.detect_reading_milestones(seeded_session, goal, dt.date(2026, 1, 1))

    keys = {
        p.milestone_key
        for p in pending
        if p.milestone_type == MilestoneType.READING_COMPLETED_BOOKS
    }
    assert keys == {"1"}


def test_detect_reading_milestones_is_empty_without_progress(seeded_session):
    goal = reading_helpers.make_reading_goal(seeded_session)
    reading_helpers.make_book(seeded_session, goal.id)

    assert svc.detect_reading_milestones(seeded_session, goal, dt.date(2026, 1, 1)) == []


def test_compute_reading_totals_aggregates_across_all_reading_goals(seeded_session):
    goal_a = reading_helpers.make_reading_goal(seeded_session, name="読書目標A")
    goal_b = reading_helpers.make_reading_goal(seeded_session, name="読書目標B")
    goal_b.status = GoalStatus.CLOSED_WITH_RESULT
    book_a = reading_helpers.make_book(seeded_session, goal_a.id)
    reading_helpers.make_book(seeded_session, goal_b.id)
    _add_reading_log(seeded_session, book_a.id, dt.date(2026, 1, 1), 50)

    totals = svc.compute_reading_totals(seeded_session)

    assert totals.total_pages == 50
    assert totals.completed_books == 1


def test_detect_reading_milestones_uses_the_precomputed_totals_when_given(seeded_session):
    """`totals`を渡した場合、`compute_reading_totals`を再計算しない
    （performance-reviewer指摘2026-11-05の回帰テスト）。"""
    _set_threshold(seeded_session, MILESTONE_READING_TOTAL_PAGES_THRESHOLDS, "100")
    goal = reading_helpers.make_reading_goal(seeded_session)
    reading_helpers.make_book(seeded_session, goal.id)
    totals = svc.ReadingTotals(total_pages=500, completed_books=0)

    pending = svc.detect_reading_milestones(seeded_session, goal, dt.date(2026, 1, 1), totals)

    keys = {
        p.milestone_key for p in pending if p.milestone_type == MilestoneType.READING_TOTAL_PAGES
    }
    assert keys == {"100"}
