"""1年前の今日（開発Todo_1年前の今日_v1.0）。ダッシュボードに過去の同じ日の記録を
ときどき表示する。表示するか否か・どの記録を選ぶかは、サーバーの論理日から完全に
決定的（同じ日に何度呼んでも同じ結果）に算出し、新規テーブルへの保存は行わない
（CLAUDE.md「日次ノルマ・残量・現在周回の保存」禁止と同じ、都度算出の考え方）。

対象は資格試験の日記（`DailyGoalDiary`）・読書の想起記録（`ReadingLog.recall_body`）・
仕事の業務記録（`WorkLog.body`）。削除済み目標は`goal_service_lifecycle.delete_goal`の
カスケード削除で物理的にDBへ残らないため、追加の除外フィルタなしで自動的に対象外となる。
アーカイブ済み・クローズ済みの目標は論理フラグのみで記録自体は残るため対象に含める
（開発Todo_1年前の今日_v1.0 §0 V7）。
"""

from __future__ import annotations

import calendar
import datetime as dt
import hashlib
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.constants.app_setting_keys import (
    ON_THIS_DAY_BODY_PREVIEW_CHARS,
    ON_THIS_DAY_CANDIDATE_MONTHS_AGO,
    ON_THIS_DAY_ENABLED,
    ON_THIS_DAY_SHOW_PROBABILITY,
)
from app.constants.enums import GoalCategory
from app.models.book import Book
from app.models.goal import Goal
from app.models.record import DailyGoalDiary, DailyRecord, ReadingLog, WorkLog, diary_text_expr
from app.models.work import WorkAssignment
from app.services import setting_reader


@dataclass(frozen=True)
class OnThisDayEntry:
    """表示する1件。APIスキーマ（`schemas/dashboard.OnThisDayRead`）への変換前の内部表現。"""

    record_date: dt.date
    goal_id: int
    goal_name: str
    category: GoalCategory
    excerpt: str
    months_ago: int


@dataclass(frozen=True)
class _Candidate:
    record_date: dt.date
    goal_id: int
    goal_name: str
    category: GoalCategory
    body: str


def subtract_months(base: dt.date, months: int) -> dt.date:
    """基準日からmonthsヶ月前の日付を返す。

    対象月にその日が存在しない場合（うるう年の2/29、各月末）は、その月の最終日に
    クランプする（例：3/31の1ヶ月前は2/28または2/29）。既存コードにも`dateutil`等の
    日付計算ライブラリは無く、本機能単独のために新規依存を追加しない方針とした。
    """
    total_months = base.month - 1 - months
    year = base.year + total_months // 12
    month = total_months % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return dt.date(year, month, day)


def _deterministic_unit_value(seed: str) -> float:
    """seed文字列から[0, 1)の決定的な値を返す。

    Python組込みの`hash()`は`PYTHONHASHSEED`によりプロセスごとに変わるため使用できない。
    `hashlib.sha256`は入力が同じなら常に同じ値を返すため、「同じ日に何度呼んでも同じ結果」
    （受け入れ基準）を満たせる。
    """
    digest = hashlib.sha256(seed.encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def resolve_show_today(today: dt.date, probability: float) -> bool:
    """当日、1年前の今日を表示するかどうかを決定的に判定する。"""
    return _deterministic_unit_value(f"on_this_day:show:{today.isoformat()}") < probability


def _select_candidate(today: dt.date, candidates: list[_Candidate]) -> _Candidate:
    """複数の候補がヒットした場合に、決定的タイブレークで1件を選ぶ。"""

    def sort_key(candidate: _Candidate) -> float:
        seed = (
            f"on_this_day:pick:{today.isoformat()}:{candidate.record_date.isoformat()}:"
            f"{candidate.category.value}:{candidate.goal_id}"
        )
        return _deterministic_unit_value(seed)

    return min(candidates, key=sort_key)


def _collect_candidates(session: Session, candidate_dates: set[dt.date]) -> list[_Candidate]:
    """候補日に本文のある記録を3カテゴリ分まとめて取得する（N+1回避のため候補日は
    `IN`句で1クエリにまとめ、カテゴリごとに1クエリの計3クエリで完結させる）。
    """
    candidates: list[_Candidate] = []

    diary_body = diary_text_expr()
    for record_date, goal_id, goal_name, body in (
        session.query(DailyRecord.record_date, DailyGoalDiary.goal_id, Goal.name, diary_body)
        .join(DailyGoalDiary, DailyGoalDiary.daily_record_id == DailyRecord.id)
        .join(Goal, Goal.id == DailyGoalDiary.goal_id)
        .filter(
            DailyRecord.record_date.in_(candidate_dates),
            diary_body.isnot(None),
            diary_body != "",
        )
    ):
        candidates.append(_Candidate(record_date, goal_id, goal_name, GoalCategory.EXAM, body))

    for record_date, goal_id, goal_name, body in (
        session.query(DailyRecord.record_date, Book.goal_id, Goal.name, ReadingLog.recall_body)
        .join(ReadingLog, ReadingLog.daily_record_id == DailyRecord.id)
        .join(Book, Book.id == ReadingLog.book_id)
        .join(Goal, Goal.id == Book.goal_id)
        .filter(
            DailyRecord.record_date.in_(candidate_dates),
            ReadingLog.recall_body != "",
        )
    ):
        candidates.append(_Candidate(record_date, goal_id, goal_name, GoalCategory.READING, body))

    for record_date, goal_id, goal_name, body in (
        session.query(DailyRecord.record_date, WorkAssignment.goal_id, Goal.name, WorkLog.body)
        .join(WorkLog, WorkLog.daily_record_id == DailyRecord.id)
        .join(WorkAssignment, WorkAssignment.id == WorkLog.work_assignment_id)
        .join(Goal, Goal.id == WorkAssignment.goal_id)
        .filter(
            DailyRecord.record_date.in_(candidate_dates),
            WorkLog.body != "",
        )
    ):
        candidates.append(_Candidate(record_date, goal_id, goal_name, GoalCategory.WORK, body))

    return candidates


def build_on_this_day_entry(session: Session, today: dt.date) -> OnThisDayEntry | None:
    """ダッシュボードに表示する「1年前の今日」を1件返す。表示しない日・候補が無い日は
    `None`を返す。
    """
    if not setting_reader.get_bool(session, ON_THIS_DAY_ENABLED):
        return None
    probability = setting_reader.get_float(session, ON_THIS_DAY_SHOW_PROBABILITY)
    if not resolve_show_today(today, probability):
        return None

    months_list = setting_reader.get_int_list(session, ON_THIS_DAY_CANDIDATE_MONTHS_AGO)
    if not months_list:
        return None
    date_by_months = {months: subtract_months(today, months) for months in months_list}

    candidates = _collect_candidates(session, set(date_by_months.values()))
    if not candidates:
        return None

    chosen = _select_candidate(today, candidates)
    months_ago = min(
        months
        for months, record_date in date_by_months.items()
        if record_date == chosen.record_date
    )
    preview_chars = setting_reader.get_int(session, ON_THIS_DAY_BODY_PREVIEW_CHARS)
    return OnThisDayEntry(
        record_date=chosen.record_date,
        goal_id=chosen.goal_id,
        goal_name=chosen.goal_name,
        category=chosen.category,
        excerpt=chosen.body[:preview_chars],
        months_ago=months_ago,
    )
