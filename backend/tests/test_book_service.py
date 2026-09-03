"""book_service.get_book_progress のテスト（ロジック・プロンプト編21.2〜21.3、
実装フェーズ分割計画書Phase15）。

CRUD（create_book/update_book/complete_book）はgoal_service・material_serviceと同様に
API層のテスト（test_api_books.py）で検証し、ここでは算出ロジック（残日数・直近記録日・
連続記録日数・ページ進捗）のみを対象とする（cycle_service・speed_serviceと同じ方針、
CLAUDE.md DRYの原則）。today はrecord_service等と同様に呼び出し側から明示的に渡す設計の
ため、システム時刻に依存せず決定論的にテストできる。
"""

import datetime as dt

from app.constants.enums import GoalCategory, GoalStatus, RecordState
from app.models.book import Book
from app.models.goal import Goal
from app.models.record import DailyRecord, ReadingLog
from app.services import book_service


def _make_reading_goal(session, *, name="読書目標") -> Goal:
    goal = Goal(
        category=GoalCategory.READING,
        name=name,
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
        resource_ratio=0,
    )
    session.add(goal)
    session.flush()
    return goal


def _make_book(session, goal, *, total_pages=None, due_date=dt.date(2026, 3, 1)) -> Book:
    book = Book(
        goal_id=goal.id,
        title="書籍A",
        total_pages=total_pages,
        start_date=dt.date(2026, 1, 1),
        due_date=due_date,
    )
    session.add(book)
    session.flush()
    return book


def _add_reading_log(session, book_id: int, record_date: dt.date, **overrides) -> None:
    record = DailyRecord(record_date=record_date, record_state=RecordState.PROGRESS_ONLY)
    session.add(record)
    session.flush()
    defaults = dict(daily_record_id=record.id, book_id=book_id, recall_body="想起本文")
    defaults.update(overrides)
    session.add(ReadingLog(**defaults))
    session.flush()


def test_remaining_days_is_due_date_minus_today(db_session):
    goal = _make_reading_goal(db_session)
    book = _make_book(db_session, goal, due_date=dt.date(2026, 3, 10))

    progress = book_service.get_book_progress(db_session, book, dt.date(2026, 3, 1))

    assert progress.remaining_days == 9


def test_remaining_days_is_negative_when_overdue(db_session):
    goal = _make_reading_goal(db_session)
    book = _make_book(db_session, goal, due_date=dt.date(2026, 3, 1))

    progress = book_service.get_book_progress(db_session, book, dt.date(2026, 3, 10))

    assert progress.remaining_days == -9


def test_last_reading_date_and_current_page_from_latest_entry(db_session):
    goal = _make_reading_goal(db_session)
    book = _make_book(db_session, goal, total_pages=300)
    _add_reading_log(db_session, book.id, dt.date(2026, 1, 1), current_page=10)
    _add_reading_log(db_session, book.id, dt.date(2026, 1, 2), current_page=25)

    progress = book_service.get_book_progress(db_session, book, dt.date(2026, 1, 5))

    assert progress.last_reading_date == dt.date(2026, 1, 2)
    assert progress.current_page == 25
    assert progress.progress_rate == 25 / 300


def test_current_page_falls_back_to_latest_non_null_value(db_session):
    """最新日の current_page が未入力(None)の場合、それより前の非NULL値を採用する。"""
    goal = _make_reading_goal(db_session)
    book = _make_book(db_session, goal, total_pages=300)
    _add_reading_log(db_session, book.id, dt.date(2026, 1, 1), current_page=10)
    _add_reading_log(db_session, book.id, dt.date(2026, 1, 2), current_page=None)

    progress = book_service.get_book_progress(db_session, book, dt.date(2026, 1, 5))

    assert progress.last_reading_date == dt.date(2026, 1, 2)
    assert progress.current_page == 10


def test_progress_rate_is_none_when_total_pages_not_set(db_session):
    goal = _make_reading_goal(db_session)
    book = _make_book(db_session, goal, total_pages=None)
    _add_reading_log(db_session, book.id, dt.date(2026, 1, 1), current_page=10)

    progress = book_service.get_book_progress(db_session, book, dt.date(2026, 1, 5))

    assert progress.progress_rate is None


def test_no_reading_logs_returns_none_last_date_and_zero_streak(db_session):
    goal = _make_reading_goal(db_session)
    book = _make_book(db_session, goal)

    progress = book_service.get_book_progress(db_session, book, dt.date(2026, 1, 5))

    assert progress.last_reading_date is None
    assert progress.current_page is None
    assert progress.current_streak == 0


def test_current_streak_counts_consecutive_days_ending_today(db_session):
    goal = _make_reading_goal(db_session)
    book = _make_book(db_session, goal, due_date=dt.date(2026, 12, 31))
    today = dt.date(2026, 1, 10)
    _add_reading_log(db_session, book.id, today)
    _add_reading_log(db_session, book.id, today - dt.timedelta(days=1))
    _add_reading_log(db_session, book.id, today - dt.timedelta(days=2))
    # 3日連続の手前（4日前）は記録なし。

    progress = book_service.get_book_progress(db_session, book, today)

    assert progress.current_streak == 3


def test_current_streak_is_zero_when_today_has_no_entry(db_session):
    """ロジック・プロンプト編21.3「Tから遡り」：当日に記録が無ければ直ちに0とする
    （13.4の連続報告日数と異なり、バッファ日等による中断除外を行わないため）。"""
    goal = _make_reading_goal(db_session)
    book = _make_book(db_session, goal, due_date=dt.date(2026, 12, 31))
    today = dt.date(2026, 1, 10)
    _add_reading_log(db_session, book.id, today - dt.timedelta(days=1))

    progress = book_service.get_book_progress(db_session, book, today)

    assert progress.current_streak == 0


def test_current_streak_ignores_other_books(db_session):
    """他の書籍のreading_logは連続記録日数に影響しない（book_idでの絞り込み確認）。"""
    goal_a = _make_reading_goal(db_session, name="読書目標A")
    goal_b = _make_reading_goal(db_session, name="読書目標B")
    book_a = _make_book(db_session, goal_a, due_date=dt.date(2026, 12, 31))
    book_b = _make_book(db_session, goal_b, due_date=dt.date(2026, 12, 31))
    today = dt.date(2026, 1, 10)
    _add_reading_log(db_session, book_b.id, today)

    progress = book_service.get_book_progress(db_session, book_a, today)

    assert progress.current_streak == 0
    assert progress.last_reading_date is None
