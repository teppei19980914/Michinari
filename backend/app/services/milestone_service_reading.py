"""節目のお祝い（開発Todo_節目のお祝い_v1.0）：読書（category=READING）固有の判定。

累計ページ数・読了冊数は利用者の読書全体（lifetime、複数の読書目標にわたる累計）を
対象とする（§0 M13。`Book.goal_id`にUNIQUE制約があり1目標=1冊のため、1目標の範囲では
意味が小さい）。到達を検知した目標（記録を確定した目標）に紐付けて記録する。
連続/累計記録日数は3種別共通のため`milestone_service_common.py`が判定する。
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.constants.app_setting_keys import (
    MILESTONE_READING_COMPLETED_BOOKS_THRESHOLDS,
    MILESTONE_READING_TOTAL_PAGES_THRESHOLDS,
)
from app.constants.enums import MilestoneType
from app.models.goal import Goal
from app.services import book_service
from app.services.milestone_service_common import PendingMilestone, threshold_milestones


@dataclass(frozen=True)
class ReadingTotals:
    """読書全体（lifetime）の集計結果。`compute_reading_totals`が1回で算出する値を、
    複数のREADING目標の判定にまたがって再利用するためのまとめ（performance-reviewer指摘
    2026-11-05：目標の数だけ同じ全件集計を繰り返さないため）。
    """

    total_pages: int
    completed_books: int


def compute_reading_totals(session: Session) -> ReadingTotals:
    """読書全体の累計ページ数・読了冊数を1回で算出する。"""
    return ReadingTotals(
        total_pages=book_service.sum_cumulative_pages_read(session),
        completed_books=book_service.count_completed_books(session),
    )


def detect_reading_milestones(
    session: Session,
    goal: Goal,
    today: dt.date,
    totals: ReadingTotals | None = None,
) -> list[PendingMilestone]:
    """`totals`を渡すと`compute_reading_totals`の再計算を省く（複数のREADING目標を
    一括判定するバッチ呼び出し元が使う。省略時はこの関数が自分で算出する）。
    """
    del today  # 読書の節目は日付に依存しない（lifetime集計）。他種別と判定関数の形を揺らせない。
    resolved = totals if totals is not None else compute_reading_totals(session)

    return threshold_milestones(
        session,
        MILESTONE_READING_TOTAL_PAGES_THRESHOLDS,
        resolved.total_pages,
        MilestoneType.READING_TOTAL_PAGES,
    ) + threshold_milestones(
        session,
        MILESTONE_READING_COMPLETED_BOOKS_THRESHOLDS,
        resolved.completed_books,
        MilestoneType.READING_COMPLETED_BOOKS,
    )
