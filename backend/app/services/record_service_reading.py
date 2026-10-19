"""日次記録のうち読書（READING）固有の処理（設計書データ構造編5.4・6.2、
仕様書6.4〜6.7・7.2・14章）。共通処理は`record_service_common.py`を参照（実装フェーズ
分割計画書S02、`record_service.py`からの分割）。
"""

import datetime as dt
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.constants.enums import GoalCategory, RecordState
from app.constants.goal_transitions import GoalOperation
from app.models.book import Book
from app.models.record import DailyRecord, ReadingLog, ReadingLogSlotTime
from app.services import goal_service
from app.services.exceptions import CurrentPageExceedsTotalPagesError, NotFoundError
from app.services.record_service_common import (
    PreviousEntry,
    SlotMinutes,
    _create_record,
    _ensure_category_not_reported,
    _ensure_finalizable_date,
    _get_category_state,
    _get_previous_entry,
    _replace_slot_times,
    _set_category_state,
    _total_minutes,
    _validate_slot_minutes,
    get_daily_record,
)


def load_books_by_id(session: Session, book_ids: set[int]) -> dict[int, Book]:
    """書籍IDの集合からBookを一括取得する（AI連携のプロンプト組み立てで使用、Phase16）。"""
    return _load_books(session, book_ids)


@dataclass(frozen=True)
class ReadingLogItem:
    """読書記録の登録入力（API層のスキーマから変換して渡す。study_logの読書版）。

    読書もリソース配分の対象となったため（要件定義書R-64）、投下時間を時間枠ごとに
    記録する。ただし読書は実効速度・完了予測を持たないため、記録した時間は集計・表示・
    AIへの文脈提供にのみ用いる（R-71）。
    """

    book_id: int
    recall_body: str
    #: 現在ページは任意入力（要件定義書R-65）。ページの数値項目はこれ1つだけとし、
    #: 「読んだページ数」は保持しない（仕様変更2026-09-11、models/record.py参照）。
    current_page: int | None
    #: 読書時間は任意入力（要件定義書R-65）。
    slot_minutes: SlotMinutes = field(default_factory=dict)


def _load_books(session: Session, book_ids: set[int]) -> dict[int, Book]:
    if not book_ids:
        return {}
    books = session.query(Book).filter(Book.id.in_(book_ids)).all()
    found = {b.id: b for b in books}
    missing = book_ids - set(found)
    if missing:
        raise NotFoundError("Book", sorted(missing))
    return found


def _ensure_current_page_within_total_pages(book: Book, current_page: int | None) -> None:
    """現在ページが書籍の総ページ数を超えないことを確認する（仕様変更2026-09-11）。

    進捗率が100%を超えることは許されないため、入力の時点で上限を超える値を拒否する。
    総ページ数を後から引き下げる訂正（book_service.update_book）は許容しており、その
    場合に限り既存データが上限を超えうる。その扱いはbook_serviceの進捗率算出に集約する。
    """
    if current_page is not None and current_page > book.total_pages:
        raise CurrentPageExceedsTotalPagesError(book.id, book.total_pages)


def _upsert_reading_log(
    session: Session, daily_record: DailyRecord, book: Book, item: ReadingLogItem
) -> ReadingLog:
    # weekly_summary_serviceとの循環import対策（record_service_exam._upsert_study_log
    # と同じ理由。CLAUDE.md DRYの原則）。
    from app.services import weekly_summary_service

    _ensure_current_page_within_total_pages(book, item.current_page)
    reading_log = (
        session.query(ReadingLog)
        .filter(ReadingLog.daily_record_id == daily_record.id, ReadingLog.book_id == book.id)
        .first()
    )
    if reading_log is None:
        reading_log = ReadingLog(daily_record_id=daily_record.id, book_id=book.id)
        session.add(reading_log)
    slot_minutes = _validate_slot_minutes(session, item.slot_minutes)
    reading_log.recall_body = item.recall_body
    reading_log.minutes_spent = _total_minutes(slot_minutes)
    reading_log.current_page = item.current_page
    session.flush()
    _replace_slot_times(
        session,
        ReadingLogSlotTime,
        ReadingLogSlotTime.reading_log_id,
        reading_log.id,
        slot_minutes,
    )
    weekly_summary_service.invalidate_week(session, book.goal, daily_record.record_date)
    return reading_log


def _apply_reading_logs(
    session: Session, daily_record: DailyRecord, items: list[ReadingLogItem]
) -> None:
    books = _load_books(session, {item.book_id for item in items})
    for book in books.values():
        goal_service.ensure_operation_allowed(book.goal, GoalOperation.RECORD)
    for item in items:
        _upsert_reading_log(session, daily_record, books[item.book_id], item)


def apply_progress(
    session: Session, daily_record: DailyRecord, items: list[ReadingLogItem]
) -> None:
    """`record_service_common.register_progress`から呼ばれる、読書（READING）分の適用。

    入力が無ければ何もしない（register_progressのディスパッチから無条件に呼ばれるため、
    空リストの早期returnをここで行う。実装フェーズ分割計画書S02、複雑度分割）。
    """
    if not items:
        return
    _apply_reading_logs(session, daily_record, items)
    if _get_category_state(daily_record, GoalCategory.READING) is None:
        _set_category_state(daily_record, GoalCategory.READING, RecordState.PROGRESS_ONLY)


def finalize_reading_record(
    session: Session,
    target_date: dt.date,
    items: list[ReadingLogItem],
    today: dt.date,
) -> DailyRecord:
    """読書の報告を確定する（未入力/進捗のみ登録済 → 報告済）。

    資格勉強・仕事の確定状態には影響しない（仕様変更2026-09-05）。
    """
    record = get_daily_record(session, target_date)
    _ensure_category_not_reported(record, target_date, GoalCategory.READING)
    _ensure_finalizable_date(target_date, today)

    record = record or _create_record(session, target_date)
    _apply_reading_logs(session, record, items)
    _set_category_state(record, GoalCategory.READING, RecordState.REPORTED)
    session.flush()
    return record


def get_previous_reading_log(
    session: Session, book_id: int, before_date: dt.date
) -> PreviousEntry | None:
    """対象書籍について、対象日より前で直近の想起記録を取得する。"""
    return _get_previous_entry(
        session, ReadingLog, ReadingLog.book_id, book_id, ReadingLog.recall_body, before_date
    )
