"""案件情報のCRUD・仕事進捗の算出（設計書データ構造編5.3・6.2、仕様書6.2・6.10・7.1、
実装フェーズ分割計画書Phase21）。

仕事目標（category=WORK）はexam_subject/material/load_profileを持たず、日次ノルマ・
実効速度・完了予測日（第7〜10章）の対象外である（要件定義書R-74）。本ファイルはその代わりに
経過日数・直近記録日・連続記録日数・直近の月次報告有無を都度算出する
（保存しない、CLAUDE.md）。bookと異なりdue_dateに相当する列を持たないため、
残日数ではなく経過日数を算出する（案件は納期未定のことが多いため）。
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.constants.enums import GoalCategory, RetrospectivePeriodType
from app.models.goal import Goal
from app.models.record import DailyRecord, WorkLog
from app.models.retrospective import GoalRetrospective
from app.models.work import WorkAssignment
from app.services import goal_service
from app.services.exceptions import ValidationError, WorkAssignmentAlreadyExistsError


def _ensure_work_goal(goal: Goal) -> None:
    if goal.category != GoalCategory.WORK:
        raise ValidationError("仕事目標（category=WORK）にのみ案件情報を登録できます")


def create_work_assignment(
    session: Session,
    goal: Goal,
    *,
    client_name: str | None,
    expected_content: str,
    start_date: dt.date,
) -> WorkAssignment:
    goal_service.ensure_goal_editable(goal)
    _ensure_work_goal(goal)
    if goal.work_assignment is not None:
        raise WorkAssignmentAlreadyExistsError(goal.id)

    work_assignment = WorkAssignment(
        goal_id=goal.id,
        client_name=client_name,
        expected_content=expected_content,
        start_date=start_date,
    )
    session.add(work_assignment)
    session.flush()
    return work_assignment


def update_work_assignment(
    session: Session,
    work_assignment: WorkAssignment,
    *,
    client_name: str | None = None,
    expected_content: str | None = None,
    start_date: dt.date | None = None,
) -> WorkAssignment:
    goal_service.ensure_goal_editable(work_assignment.goal)

    if client_name is not None:
        work_assignment.client_name = client_name
    if expected_content is not None:
        work_assignment.expected_content = expected_content
    if start_date is not None:
        work_assignment.start_date = start_date

    session.flush()
    return work_assignment


@dataclass(frozen=True)
class WorkAssignmentProgress:
    """仕事進捗（データ構造編6.2、実装フェーズ分割計画書Phase21）。日次ノルマ等は算出しない。"""

    elapsed_days: int
    last_work_date: dt.date | None
    current_streak: int
    has_recent_monthly_report: bool


def get_work_assignment_progress(
    session: Session, work_assignment: WorkAssignment, today: dt.date
) -> WorkAssignmentProgress:
    """今日はquota_service・speed_serviceと同様に呼び出し側から明示的に渡す
    （システム時刻に依存させず決定論的にテストできるようにするため）。"""
    # record_date をまとめて1クエリで取得する（N+1禁止、CLAUDE.md）。
    rows = (
        session.query(DailyRecord.record_date)
        .join(WorkLog, WorkLog.daily_record_id == DailyRecord.id)
        .filter(WorkLog.work_assignment_id == work_assignment.id)
        .order_by(DailyRecord.record_date.desc())
        .all()
    )

    last_work_date = rows[0][0] if rows else None

    # 連続記録日数（book_service.get_book_progressと同じ考え方）：Tから遡り、
    # 記録が存在する日が連続する日数。バッファ日・除外日による中断除外は行わない
    # （仕事目標は日種別による計画運用の対象外、要件定義書R-74）。
    recorded_dates = {record_date for (record_date,) in rows}
    streak = 0
    day = today
    while day in recorded_dates:
        streak += 1
        day -= dt.timedelta(days=1)

    has_recent_monthly_report = (
        session.query(GoalRetrospective.id)
        .filter(
            GoalRetrospective.goal_id == work_assignment.goal_id,
            GoalRetrospective.period_type == RetrospectivePeriodType.MONTHLY,
            GoalRetrospective.is_anonymized.is_(False),
        )
        .first()
        is not None
    )

    return WorkAssignmentProgress(
        elapsed_days=(today - work_assignment.start_date).days,
        last_work_date=last_work_date,
        current_streak=streak,
        has_recent_monthly_report=has_recent_monthly_report,
    )
