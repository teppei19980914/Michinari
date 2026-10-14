"""ナレッジエクスポートのうち読書（READING）固有の処理（設計書データ構造編7章、
仕様書6.10 SC-13）。共通処理は`export_service_common.py`を参照（実装フェーズ分割計画書
S02、`export_service.py`からの分割）。
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.constants.export_markdown import (
    EXPORT_DEFAULT_TITLE,
    EXPORT_HEADING_APPENDIX_READING_RECALLS,
    EXPORT_HEADING_OVERVIEW,
    EXPORT_HEADING_READING_RETROSPECTIVE,
    EXPORT_HEADING_RECORD_VOLUME,
    EXPORT_LABEL_BOOK_AUTHOR,
    EXPORT_LABEL_BOOK_DUE_DATE,
    EXPORT_LABEL_BOOK_TITLE,
    EXPORT_LABEL_MAX_STREAK,
    EXPORT_LABEL_READING_PERIOD,
    EXPORT_LABEL_RECORD_DAYS,
    EXPORT_PLACEHOLDER_NO_READING_RETROSPECTIVE,
    EXPORT_PLACEHOLDER_UNREGISTERED,
    EXPORT_TABLE_HEAD_READING_RECALLS,
    EXPORT_UNIT_DAYS,
)
from app.models.book import Book
from app.models.goal import Goal
from app.models.record import DailyRecord, ReadingLog
from app.services import retrospective_service
from app.services.export_service_common import ExportSelection


def _build_book(book: Book) -> dict:
    return {
        "title": book.title,
        "author": book.author,
        "total_pages": book.total_pages,
        "start_date": book.start_date.isoformat(),
        "due_date": book.due_date.isoformat(),
    }


def _reading_log_dates(session: Session, book: Book) -> set[dt.date]:
    return {
        row[0]
        for row in session.query(DailyRecord.record_date)
        .join(ReadingLog, ReadingLog.daily_record_id == DailyRecord.id)
        .filter(ReadingLog.book_id == book.id)
        .distinct()
    }


def _compute_max_streak_days(record_dates: set[dt.date]) -> int:
    if not record_dates:
        return 0
    sorted_dates = sorted(record_dates)
    longest = current = 1
    for previous, current_date in zip(sorted_dates, sorted_dates[1:], strict=False):
        if current_date - previous == dt.timedelta(days=1):
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def _build_reading_summary(session: Session, book: Book) -> dict:
    """読書サマリ（設計書データ構造編7.1「読書目標の場合」）：記録日数・最長連続記録日数。"""
    record_dates = _reading_log_dates(session, book)
    return {
        "record_days": len(record_dates),
        "max_streak_days": _compute_max_streak_days(record_dates),
    }


def _build_reading_daily_records(session: Session, book: Book) -> list[dict]:
    """日別の想起記録一覧（仕様書6.10「実績推移」は日別の想起記録一覧と読み替え）。"""
    rows = (
        session.query(
            DailyRecord.record_date,
            ReadingLog.recall_body,
            ReadingLog.current_page,
        )
        .join(ReadingLog, ReadingLog.daily_record_id == DailyRecord.id)
        .filter(ReadingLog.book_id == book.id)
        .order_by(DailyRecord.record_date)
        .all()
    )
    return [
        {
            "date": record_date.isoformat(),
            "recall": recall_body,
            "current_page": current_page,
        }
        for record_date, recall_body, current_page in rows
    ]


def build_reading_export_data(
    session: Session, goal: Goal, selection: ExportSelection, *, anonymized: bool, data: dict
) -> dict:
    """読書目標（category=READING）向けのエクスポートデータ組み立て（仕様書6.10、
    設計書データ構造編7.1「読書目標の場合」）。

    教材構成・品質指標推移・受験結果・週次要約・リプラン履歴は該当データを持たないため
    出力しない。日記本文・AI対話履歴も、想起記録（daily_records）がその代替であるため
    出力しない（データ構造編7.3「日記本文・AI対話履歴は出力から除外する」）。
    """
    book = goal.book
    if selection.goal_overview and book is not None:
        data["book"] = _build_book(book)
    if selection.summary and book is not None:
        data["summary"] = _build_reading_summary(session, book)
    if selection.daily_records and not anonymized and book is not None:
        data["daily_records"] = _build_reading_daily_records(session, book)
    if selection.retrospective:
        retrospective = retrospective_service.get_latest_retrospective(
            session, goal, anonymized=anonymized
        )
        data["retrospective"] = retrospective.body if retrospective is not None else None
    return data


def render_reading_markdown(data: dict) -> str:
    """読書目標のMarkdown構成（設計書データ構造編7.2「読書目標の場合」）。"""
    sections: list[str] = []

    if "book" in data:
        book = data["book"]
        sections.append(
            f"{EXPORT_HEADING_OVERVIEW}\n\n"
            f"{EXPORT_LABEL_BOOK_TITLE}{book['title']}\n"
            f"{EXPORT_LABEL_BOOK_AUTHOR}{book['author'] or EXPORT_PLACEHOLDER_UNREGISTERED}\n"
            f"{EXPORT_LABEL_BOOK_DUE_DATE}{book['due_date']}\n"
            f"{EXPORT_LABEL_READING_PERIOD}{book['start_date']} 〜 {book['due_date']}"
        )

    if "retrospective" in data:
        body = data["retrospective"] or EXPORT_PLACEHOLDER_NO_READING_RETROSPECTIVE
        sections.append(f"{EXPORT_HEADING_READING_RETROSPECTIVE}\n\n{body}")

    if "summary" in data:
        s = data["summary"]
        sections.append(
            f"{EXPORT_HEADING_RECORD_VOLUME}\n\n"
            f"{EXPORT_LABEL_RECORD_DAYS}{s['record_days']}{EXPORT_UNIT_DAYS}\n"
            f"{EXPORT_LABEL_MAX_STREAK}{s['max_streak_days']}{EXPORT_UNIT_DAYS}"
        )

    if "daily_records" in data:
        rows = "\n".join(
            f"| {r['date']} | {r['recall']} | "
            f"{r['current_page'] if r['current_page'] is not None else '-'} |"
            for r in data["daily_records"]
        )
        sections.append(
            f"{EXPORT_HEADING_APPENDIX_READING_RECALLS}\n\n"
            f"{EXPORT_TABLE_HEAD_READING_RECALLS}\n"
            "| --- | --- | --- |\n"
            f"{rows}"
        )

    title = data.get("book", {}).get("title", EXPORT_DEFAULT_TITLE)
    return f"# {title}\n\n" + "\n\n".join(sections)
