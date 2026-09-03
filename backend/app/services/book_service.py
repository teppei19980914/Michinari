"""書籍のCRUD・読了処理・読書進捗の算出（設計書データ構造編5.3・6.2、
仕様書6.2・6.10・7.1、ロジック・プロンプト編21章、実装フェーズ分割計画書Phase15）。

読書目標（category=READING）はexam_subject/material/load_profileを持たず、日次ノルマ・
実効速度・完了予測日（第7〜10章）の対象外である（要件定義書R-66）。本ファイルはその代わりに
残日数・直近記録日・連続記録日数（・ページ進捗）を都度算出する（保存しない、CLAUDE.md）。
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.constants.enums import GoalCategory, GoalStatus
from app.models.base import utcnow
from app.models.book import Book
from app.models.goal import Goal
from app.models.record import DailyRecord, ReadingLog
from app.services import goal_service
from app.services.exceptions import (
    BookAlreadyExistsError,
    InvalidStateTransitionError,
    NotFoundError,
    ValidationError,
)

_MSG_START_DATE_AFTER_DUE_DATE = "読書開始日は読了目標日より前の日付にしてください"


def get_book(session: Session, book_id: int) -> Book:
    book = session.get(Book, book_id)
    if book is None:
        raise NotFoundError("書籍", book_id)
    return book


def _ensure_reading_goal(goal: Goal) -> None:
    if goal.category != GoalCategory.READING:
        raise ValidationError("読書目標（category=READING）にのみ書籍を登録できます")


def create_book(
    session: Session,
    goal: Goal,
    *,
    title: str,
    author: str | None,
    total_pages: int | None,
    start_date: dt.date,
    due_date: dt.date,
) -> Book:
    goal_service.ensure_goal_editable(goal)
    _ensure_reading_goal(goal)
    if goal.book is not None:
        raise BookAlreadyExistsError(goal.id)
    if start_date > due_date:
        raise ValidationError(_MSG_START_DATE_AFTER_DUE_DATE)

    book = Book(
        goal_id=goal.id,
        title=title,
        author=author,
        total_pages=total_pages,
        start_date=start_date,
        due_date=due_date,
    )
    session.add(book)
    session.flush()
    return book


def update_book(
    session: Session,
    book: Book,
    *,
    title: str | None = None,
    author: str | None = None,
    total_pages: int | None = None,
    start_date: dt.date | None = None,
    due_date: dt.date | None = None,
) -> Book:
    goal_service.ensure_goal_editable(book.goal)

    if title is not None:
        book.title = title
    if author is not None:
        book.author = author
    if total_pages is not None:
        book.total_pages = total_pages
    if start_date is not None:
        book.start_date = start_date
    if due_date is not None:
        book.due_date = due_date
    if book.start_date > book.due_date:
        raise ValidationError(_MSG_START_DATE_AFTER_DUE_DATE)

    session.flush()
    return book


def complete_book(session: Session, book: Book) -> Goal:
    """読了として記録する（仕様書6.2「読了操作」、7.1のCLOSED_WITH_RESULT遷移）。

    資格試験のクローズ（結果あり）が全科目の受験結果登録を契機に自動遷移するのに対し、
    読書には登録すべき結果が無いため、本関数の呼び出し自体が読了の意思表示となる
    （データ構造編5.3「読書目標のクローズ」）。
    """
    goal = book.goal
    if goal.status != GoalStatus.ACTIVE:
        raise InvalidStateTransitionError("進行中の読書目標のみ読了として記録できます")
    goal.status = GoalStatus.CLOSED_WITH_RESULT
    goal.closed_at = utcnow()
    session.flush()
    return goal


@dataclass(frozen=True)
class BookProgress:
    """読書進捗（ロジック・プロンプト編21.2）。日次ノルマ等は算出しない（21.1）。"""

    remaining_days: int
    last_reading_date: dt.date | None
    current_streak: int
    current_page: int | None
    progress_rate: float | None


def get_book_progress(session: Session, book: Book, today: dt.date) -> BookProgress:
    """今日はquota_service・speed_serviceと同様に呼び出し側から明示的に渡す
    （システム時刻に依存させず決定論的にテストできるようにするため）。"""
    # record_date・current_page をまとめて1クエリで取得する（N+1禁止、CLAUDE.md）。
    rows = (
        session.query(DailyRecord.record_date, ReadingLog.current_page)
        .join(ReadingLog, ReadingLog.daily_record_id == DailyRecord.id)
        .filter(ReadingLog.book_id == book.id)
        .order_by(DailyRecord.record_date.desc())
        .all()
    )

    last_reading_date = rows[0][0] if rows else None
    current_page = next((page for _, page in rows if page is not None), None)

    # 連続記録日数（ロジック・プロンプト編21.3）：Tから遡り、記録が存在する日が連続する日数。
    # 13.4（連続報告日数）と異なり、バッファ日・除外日による中断除外を行わない
    # （読書は日種別による計画運用の対象外、要件定義書R-64）。
    recorded_dates = {record_date for record_date, _ in rows}
    streak = 0
    day = today
    while day in recorded_dates:
        streak += 1
        day -= dt.timedelta(days=1)

    progress_rate = (
        current_page / book.total_pages
        if current_page is not None and book.total_pages
        else None
    )

    return BookProgress(
        remaining_days=(book.due_date - today).days,
        last_reading_date=last_reading_date,
        current_streak=streak,
        current_page=current_page,
        progress_rate=progress_rate,
    )
