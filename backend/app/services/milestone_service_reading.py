"""節目のお祝い（開発Todo_節目のお祝い_v1.0）：読書（category=READING）固有の判定。

累計ページ数・読了冊数は利用者の読書全体（lifetime、複数の読書目標にわたる累計）を
対象とする（§0 M13。`Book.goal_id`にUNIQUE制約があり1目標=1冊のため、1目標の範囲では
意味が小さい）。到達を検知した目標（記録を確定した目標）に紐付けて記録する。
連続/累計記録日数は3種別共通のため`milestone_service_common.py`が判定する。
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.constants.app_setting_keys import (
    MILESTONE_READING_COMPLETED_BOOKS_THRESHOLDS,
    MILESTONE_READING_TOTAL_PAGES_THRESHOLDS,
)
from app.constants.enums import MilestoneType
from app.models.goal import Goal
from app.services import book_service, setting_reader
from app.services.milestone_service_common import PendingMilestone


def detect_reading_milestones(
    session: Session, goal: Goal, today: dt.date
) -> list[PendingMilestone]:
    del today  # 読書の節目は日付に依存しない（lifetime集計）。他種別と判定関数の形を揺らせない。
    pending: list[PendingMilestone] = []

    total_pages = book_service.sum_cumulative_pages_read(session)
    for threshold in setting_reader.get_int_list(
        session, MILESTONE_READING_TOTAL_PAGES_THRESHOLDS
    ):
        if total_pages >= threshold:
            pending.append(PendingMilestone(MilestoneType.READING_TOTAL_PAGES, str(threshold)))

    completed_books = book_service.count_completed_books(session)
    for threshold in setting_reader.get_int_list(
        session, MILESTONE_READING_COMPLETED_BOOKS_THRESHOLDS
    ):
        if completed_books >= threshold:
            pending.append(
                PendingMilestone(MilestoneType.READING_COMPLETED_BOOKS, str(threshold))
            )

    return pending
