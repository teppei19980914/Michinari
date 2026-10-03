"""振り返り（テーマ別・週またぎ累積）の報告収集と分類結果の取り込み（資格試験の日記・読書の
想起記録が対象）。AI呼び出しは含まず、分類結果の解釈と永続化だけを担う。

報告本文は RecapEntry に複製せず、参照（種類・ID）だけを持つ。振り返りの生成時に元の報告を
読み直すため、利用者が後から直した内容が反映される。
"""

import datetime as dt
import re
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.constants.enums import RecapSourceKind
from app.models.base import utcnow
from app.models.book import Book
from app.models.goal import Goal
from app.models.recap import RecapEntry, RecapTheme, RecapThemeLink
from app.models.record import DailyGoalDiary, DailyRecord, ReadingLog

#: テーマ名の最大文字数（recap_theme.name の列幅と同じ）。
THEME_NAME_MAX_LENGTH = 100

_CLASSIFICATION_LINE = re.compile(r"^\s*#(\d+)\s*[:：]\s*(.+?)\s*$")
_THEME_SEPARATORS = re.compile(r"[、,，]")


@dataclass(frozen=True)
class EntryText:
    entry_id: int
    record_date: dt.date
    text: str


def parse_classification(response_text: str, known_entry_ids: set[int]) -> dict[int, list[str]]:
    """AIの分類応答（1行1報告の「#報告ID: テーマ名、テーマ名」形式）を解釈する。

    知らないIDの行・形式に合わない行は無視する（その報告は未分類のまま残り、次回の
    バッチで再度分類される）。テーマ名は前後の空白を除き、重複を除いて順序を保つ。
    """
    result: dict[int, list[str]] = {}
    for line in response_text.splitlines():
        match = _CLASSIFICATION_LINE.match(line)
        if match is None:
            continue
        entry_id = int(match.group(1))
        if entry_id not in known_entry_ids:
            continue
        names: list[str] = []
        for raw_name in _THEME_SEPARATORS.split(match.group(2)):
            name = raw_name.strip()[:THEME_NAME_MAX_LENGTH]
            if name and name not in names:
                names.append(name)
        if names:
            result[entry_id] = names
    return result


def _nonempty(column):
    return column.isnot(None) & (column != "")


def collect_pending_entries(
    session: Session, goal: Goal, start: dt.date, end: dt.date
) -> list[RecapEntry]:
    """期間内の報告のうち、まだ RecapEntry がないものを登録し、未分類の全件を返す。

    資格試験は learned（学んだこと）を優先し、未入力の旧データだけ body（旧仕様の本文）を
    使う。報告が空のものは対象外（テーマ分類する内容が無い）。
    """
    diary_rows = session.execute(
        select(DailyGoalDiary.id, DailyRecord.record_date)
        .join(DailyRecord, DailyGoalDiary.daily_record_id == DailyRecord.id)
        .where(
            DailyGoalDiary.goal_id == goal.id,
            DailyRecord.record_date >= start,
            DailyRecord.record_date <= end,
            or_(
                _nonempty(DailyGoalDiary.diary_learned),
                _nonempty(DailyGoalDiary.diary_body),
            ),
        )
    ).all()
    reading_rows = session.execute(
        select(ReadingLog.id, DailyRecord.record_date)
        .join(Book, ReadingLog.book_id == Book.id)
        .join(DailyRecord, ReadingLog.daily_record_id == DailyRecord.id)
        .where(
            Book.goal_id == goal.id,
            DailyRecord.record_date >= start,
            DailyRecord.record_date <= end,
            _nonempty(ReadingLog.recall_body),
        )
    ).all()

    known = set(
        session.execute(
            select(RecapEntry.source_kind, RecapEntry.source_id).where(
                RecapEntry.goal_id == goal.id
            )
        ).all()
    )
    for kind, rows in (
        (RecapSourceKind.DIARY, diary_rows),
        (RecapSourceKind.READING, reading_rows),
    ):
        for source_id, record_date in rows:
            if (kind, source_id) not in known:
                session.add(
                    RecapEntry(
                        goal_id=goal.id,
                        source_kind=kind,
                        source_id=source_id,
                        record_date=record_date,
                    )
                )
    session.flush()

    return list(
        session.scalars(
            select(RecapEntry)
            .where(RecapEntry.goal_id == goal.id, RecapEntry.classified_at.is_(None))
            .order_by(RecapEntry.record_date, RecapEntry.id)
        ).all()
    )


def entry_texts(session: Session, entries: list[RecapEntry]) -> list[EntryText]:
    """分類・要約に渡す報告本文を、種類ごとに一括取得して返す（1件ずつ問い合わせない）。"""
    diary_ids = [e.source_id for e in entries if e.source_kind is RecapSourceKind.DIARY]
    reading_ids = [e.source_id for e in entries if e.source_kind is RecapSourceKind.READING]
    texts: dict[tuple[RecapSourceKind, int], str] = {}
    if diary_ids:
        for diary in session.scalars(
            select(DailyGoalDiary).where(DailyGoalDiary.id.in_(diary_ids))
        ):
            texts[(RecapSourceKind.DIARY, diary.id)] = diary.diary_learned or diary.diary_body or ""
    if reading_ids:
        for log in session.scalars(select(ReadingLog).where(ReadingLog.id.in_(reading_ids))):
            texts[(RecapSourceKind.READING, log.id)] = log.recall_body
    return [
        EntryText(
            entry_id=e.id,
            record_date=e.record_date,
            text=texts.get((e.source_kind, e.source_id), ""),
        )
        for e in entries
    ]


def apply_classification(
    session: Session,
    goal: Goal,
    classification: dict[int, list[str]],
    *,
    now: dt.datetime | None = None,
) -> set[int]:
    """分類結果をテーマとリンクへ反映する。既存テーマ名は再利用し、無ければ新規作成する。

    未分類の報告だけを対象とし、分類済みの報告へは二重にリンクしない。戻り値は影響を受けた
    テーマIDの集合（本文の再生成対象）。
    """
    stamp = now or utcnow()
    themes_by_name = {
        theme.name: theme
        for theme in session.scalars(select(RecapTheme).where(RecapTheme.goal_id == goal.id))
    }
    entries_by_id = {
        entry.id: entry
        for entry in session.scalars(
            select(RecapEntry).where(
                RecapEntry.goal_id == goal.id,
                RecapEntry.id.in_(list(classification)),
                RecapEntry.classified_at.is_(None),
            )
        )
    }
    touched: set[int] = set()
    for entry_id, names in classification.items():
        entry = entries_by_id.get(entry_id)
        if entry is None:
            continue
        for name in names:
            theme = themes_by_name.get(name)
            if theme is None:
                theme = RecapTheme(goal_id=goal.id, name=name, body="")
                session.add(theme)
                session.flush()
                themes_by_name[name] = theme
            session.add(RecapThemeLink(theme_id=theme.id, entry_id=entry.id))
            touched.add(theme.id)
        entry.classified_at = stamp
    session.flush()
    return touched
