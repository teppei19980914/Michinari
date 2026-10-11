"""AIプロンプトへ注入する変数の組み立て（読書目標、設計書 ロジック・プロンプト編
17.6〜17.7・17.11）。共通処理は`ai_context_common.py`を参照（実装フェーズ分割計画書S01、
`ai_context_service.py`からの分割）。
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.ai.prompt_builder import DatedLogEntry
from app.constants.enums import GoalCategory, GoalStatus
from app.models.book import Book
from app.models.goal import Goal
from app.models.record import DailyRecord, ReadingLog
from app.services.ai_context_common import _format_days_remaining
from app.services.record_service import ReadingLogItem


def list_active_reading_goals(session: Session) -> list[Goal]:
    """進行中（ACTIVE）の読書目標一覧を取得する（DAILY_FEEDBACK_READING用、Phase16）。"""
    return (
        session.query(Goal)
        .filter(Goal.status == GoalStatus.ACTIVE, Goal.category == GoalCategory.READING)
        .order_by(Goal.id)
        .all()
    )


def list_active_books(goals: list[Goal]) -> list[Book]:
    """指定した読書目標群に属する書籍一覧を取得する（1目標1冊のため高々1件ずつ）。"""
    return [goal.book for goal in goals if goal.book is not None]


# --- 読書日次報告フィードバック（DAILY_FEEDBACK_READING、17.6、実装フェーズ分割計画書Phase16） ---


def build_daily_book_summary_text(books: list[Book], today: dt.date) -> str:
    """{{book_summary}}（DAILY_FEEDBACK_READING、17.6）: 書名、著者、読了目標日、残日数。"""
    if not books:
        return "（進行中の読書目標はありません）"
    lines = []
    for book in books:
        author_text = f"、著者 {book.author}" if book.author else ""
        lines.append(
            f"■ {book.title}{author_text}\n"
            f"  読了目標日 {book.due_date.isoformat()}"
            f"（{_format_days_remaining(today, book.due_date)}）"
        )
    return "\n".join(lines)


def build_today_recall_text(items: list[ReadingLogItem], books_by_id: dict[int, Book]) -> str:
    """{{today_recall}}（DAILY_FEEDBACK_READING、17.6）: 本日の想起本文。

    ページに関する数値は一切注入しない（仕様変更2026-09-11）。読書の日次報告は評価の場
    ではなく利用者の思いを引き出す場であり（要件定義書R-66）、プロンプト本文も「ページ数や
    読了ペースを評価しないでください」と明示している（17.6）。評価に用いない数値を渡すのは
    その指示と矛盾するため、現在ページは画面上の進捗表示（21.2）専用とし注入対象から外す。
    """
    if not items:
        return "（本日の想起入力はまだありません）"
    return "\n\n".join(f"■ {books_by_id[item.book_id].title}\n{item.recall_body}" for item in items)


def build_recent_recalls_entries(
    session: Session, books: list[Book], today: dt.date, recent_days: int
) -> list[DatedLogEntry]:
    """{{recent_recalls}}（DAILY_FEEDBACK_READING、17.6）: 直近recent_days日分の想起記録
    （21.4）。週次要約を経由せず原文を直接注入する（読書目標は週次要約を持たないため）。

    対象日（today）自身は含めない。today分の想起は{{today_recall}}（下書きの値、
    reading_feedback_service）で別途渡すため、todayの想起がDBへ保存済み（確定後の
    再対話等）だと、含めた場合に同一内容が{{today_recall}}と本関数の結果で二重に
    プロンプトへ注入されてしまう（2026-09-15、実運用で確認・是正）。そのためtodayを
    含まないrecent_days日分（today-recent_days 〜 today-1）を対象とする。

    record_date の古い順（昇順）で返す。整形（空の場合の表示・段階的縮退）は
    prompt_builder.build_with_degradable_entries側の責務とする（CLAUDE.md DRYの原則。
    仕事のbuild_recent_work_logs_entriesと同じ形）。
    """
    if not books:
        return []
    book_ids = [book.id for book in books]
    book_titles = {book.id: book.title for book in books}
    period_start = today - dt.timedelta(days=recent_days)
    rows = (
        session.query(DailyRecord.record_date, ReadingLog.book_id, ReadingLog.recall_body)
        .join(ReadingLog, ReadingLog.daily_record_id == DailyRecord.id)
        .filter(
            ReadingLog.book_id.in_(book_ids),
            DailyRecord.record_date >= period_start,
            DailyRecord.record_date < today,
        )
        .order_by(DailyRecord.record_date)
        .all()
    )
    return [
        DatedLogEntry(
            record_date=record_date,
            text=f"【{record_date.isoformat()} {book_titles[book_id]}】\n{recall_body}",
        )
        for record_date, book_id, recall_body in rows
    ]


# --- 読了レポート（GOAL_RETROSPECTIVE_READING、17.7、実装フェーズ分割計画書Phase16） ---


def build_retrospective_book_summary_text(book: Book) -> str:
    """{{book_summary}}（GOAL_RETROSPECTIVE_READING、17.7）: 書名、著者、読書期間。"""
    author_text = f"、著者 {book.author}" if book.author else ""
    return (
        f"{book.title}{author_text}\n"
        f"読書期間: {book.start_date.isoformat()} 〜 {book.due_date.isoformat()}"
    )


def build_reading_overall_metrics_text(session: Session, book: Book) -> str:
    """{{overall_metrics}}（GOAL_RETROSPECTIVE_READING、17.7）: 記録日数、最長連続記録日数。

    データ構造編7.1の読書用summary（record_days・max_streak_days）と同じ定義。
    21.3の連続記録日数（Tから遡る現在のストリーク）とは異なり、過去全期間で最長だった
    連続記録日数を求める点に注意する。
    """
    dates = sorted(
        row[0]
        for row in session.query(DailyRecord.record_date)
        .join(ReadingLog, ReadingLog.daily_record_id == DailyRecord.id)
        .filter(ReadingLog.book_id == book.id)
        .distinct()
    )
    record_days = len(dates)
    max_streak = 0
    current_streak = 0
    previous_date: dt.date | None = None
    for record_date in dates:
        if previous_date is not None and record_date == previous_date + dt.timedelta(days=1):
            current_streak += 1
        else:
            current_streak = 1
        max_streak = max(max_streak, current_streak)
        previous_date = record_date
    return f"記録日数: {record_days}日\n最長連続記録日数: {max_streak}日"


def build_reading_logs_entries(
    session: Session, book: Book, *, date_from: dt.date | None = None
) -> list[DatedLogEntry]:
    """{{reading_logs}}（GOAL_RETROSPECTIVE_READING、17.7）: 想起記録を record_date の
    昇順で連結したもの（21.4）。

    date_from省略時は全期間（従来どおり）。L-11で読了レポートに週次要約を追加した際、
    下限の指定に対応した（通常はbook.start_dateを渡す）。既に週次要約が生成済みの日付を
    重複させずに除外する処理は、呼び出し側がexclude_covered_datesで行う。

    整形前のlist[DatedLogEntry]を返し、空の場合の表示・段階的縮退はprompt_builder.
    build_with_degradable_entries側の責務とする（CLAUDE.md DRYの原則）。
    """
    query = (
        session.query(DailyRecord.record_date, ReadingLog.recall_body)
        .join(ReadingLog, ReadingLog.daily_record_id == DailyRecord.id)
        .filter(ReadingLog.book_id == book.id)
    )
    if date_from is not None:
        query = query.filter(DailyRecord.record_date >= date_from)
    rows = query.order_by(DailyRecord.record_date).all()
    return [
        DatedLogEntry(record_date=record_date, text=f"【{record_date.isoformat()}】\n{recall_body}")
        for record_date, recall_body in rows
    ]


# --- 読書用週次要約（WEEKLY_SUMMARY_READING、17.11、L-11） ---


def build_week_recalls_text(
    session: Session, book: Book, week_start: dt.date, week_end: dt.date
) -> str:
    """{{week_recalls}}（WEEKLY_SUMMARY_READING、17.11）: 週内の想起記録を record_date の
    昇順で連結したもの。読書は実績・日記の区別を持たないため（17.6参照）、資格試験の
    build_week_logs_text／build_week_diaries_textに相当する変数を1本に統合する。
    """
    rows = (
        session.query(DailyRecord.record_date, ReadingLog.recall_body)
        .join(ReadingLog, ReadingLog.daily_record_id == DailyRecord.id)
        .filter(
            ReadingLog.book_id == book.id,
            DailyRecord.record_date >= week_start,
            DailyRecord.record_date <= week_end,
        )
        .order_by(DailyRecord.record_date)
        .all()
    )
    if not rows:
        return "（この週の想起記録はありません）"
    return "\n\n".join(
        f"【{record_date.isoformat()}】\n{recall_body}" for record_date, recall_body in rows
    )
