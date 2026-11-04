"""節目のお祝い（開発Todo_節目のお祝い_v1.0）：仕事（category=WORK）固有の判定。

記録件数（閾値あり）と、評価期間（半期、work_report_service.semiannual_period_range）を
通して月次報告を出し続けたこと（閾値を持たないイベント型）を判定する。連続/累計記録日数は
3種別共通のため`milestone_service_common.py`が判定する。
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.constants.app_setting_keys import MILESTONE_WORK_RECORD_COUNT_THRESHOLDS
from app.constants.enums import MilestoneType, RetrospectivePeriodType
from app.models.goal import Goal
from app.models.retrospective import GoalRetrospective
from app.services import work_report_service, work_service
from app.services.milestone_service_common import PendingMilestone, threshold_milestones


def _monthly_keys_in_semiannual(period_key: str) -> list[str]:
    """半期評価の対象期間に含まれる月のperiod_key一覧（"YYYY-MM"）を返す。

    `work_report_service.semiannual_period_range`は日付（開始日・終了日）を返すが、
    月次報告の存在確認には月単位のperiod_keyが必要なため、ここで月キーへ分解する
    （既存にこの分解を行う関数は無かった）。
    """
    year_text, half = period_key.split("-")
    year = int(year_text)
    if half == "H1":
        return [f"{year}-{month:02d}" for month in range(3, 9)]
    return [f"{year}-{month:02d}" for month in (9, 10, 11, 12)] + [
        f"{year + 1}-{month:02d}" for month in (1, 2)
    ]


def _recorded_every_month(session: Session, goal: Goal, period_key: str) -> bool:
    month_keys = _monthly_keys_in_semiannual(period_key)
    reported_keys = {
        row[0]
        for row in session.query(GoalRetrospective.period_key).filter(
            GoalRetrospective.goal_id == goal.id,
            GoalRetrospective.period_type == RetrospectivePeriodType.MONTHLY,
            GoalRetrospective.period_key.in_(month_keys),
            GoalRetrospective.is_anonymized.is_(False),
        )
    }
    return set(month_keys).issubset(reported_keys)


def detect_work_milestones(session: Session, goal: Goal, today: dt.date) -> list[PendingMilestone]:
    """仕事目標の節目を判定する。案件情報（`work_assignment`）が未登録の場合は空リストを
    返す（記録件数・評価期間完走のいずれも案件情報を前提とするため）。
    """
    work_assignment = goal.work_assignment
    if work_assignment is None:
        return []

    record_count = work_service.count_work_records(session, work_assignment)
    pending = threshold_milestones(
        session,
        MILESTONE_WORK_RECORD_COUNT_THRESHOLDS,
        record_count,
        MilestoneType.WORK_RECORD_COUNT,
    )

    # 評価期間（直近に終了した半期）を通して月次報告を出し続けたことを祝う。進行中の
    # 半期（todayが属する期間）は対象外（期間が終わるまで「通して」出し続けたかどうかを
    # 確定できない）ため、1つ前の半期を見る。
    previous_period_key = work_report_service.previous_semiannual_period_key(
        work_report_service.default_semiannual_period_key(today)
    )
    if _recorded_every_month(session, goal, previous_period_key):
        pending.append(
            PendingMilestone(MilestoneType.WORK_EVALUATION_PERIOD_COMPLETED, previous_period_key)
        )

    return pending
