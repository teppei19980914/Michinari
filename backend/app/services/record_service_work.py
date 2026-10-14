"""日次記録のうち仕事（WORK）固有の処理（設計書データ構造編5.4・6.2、
仕様書6.4〜6.7・7.2・14章）。共通処理は`record_service_common.py`を参照（実装フェーズ
分割計画書S02、`record_service.py`からの分割）。
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.constants.enums import GoalCategory, RecordState
from app.constants.goal_transitions import GoalOperation
from app.models.record import DailyRecord, WorkLog
from app.models.work import WorkAssignment
from app.services import goal_service
from app.services.exceptions import NotFoundError
from app.services.record_service_common import (
    PreviousEntry,
    _create_record,
    _ensure_category_not_reported,
    _ensure_finalizable_date,
    _get_category_state,
    _get_previous_entry,
    _set_category_state,
    get_daily_record,
)


def load_work_assignments_by_id(
    session: Session, work_assignment_ids: set[int]
) -> dict[int, WorkAssignment]:
    """案件情報IDの集合からWorkAssignmentを一括取得する（AI連携のプロンプト組み立てで
    使用、Phase22）。"""
    return _load_work_assignments(session, work_assignment_ids)


@dataclass(frozen=True)
class WorkLogItem:
    """業務記録の登録入力（API層のスキーマから変換して渡す。study_logの仕事版。
    読書と異なりページ数等の付随フィールドは持たない、自由記述1本）。"""

    work_assignment_id: int
    body: str


def _load_work_assignments(
    session: Session, work_assignment_ids: set[int]
) -> dict[int, WorkAssignment]:
    if not work_assignment_ids:
        return {}
    work_assignments = (
        session.query(WorkAssignment).filter(WorkAssignment.id.in_(work_assignment_ids)).all()
    )
    found = {w.id: w for w in work_assignments}
    missing = work_assignment_ids - set(found)
    if missing:
        raise NotFoundError("WorkAssignment", sorted(missing))
    return found


def _upsert_work_log(
    session: Session, daily_record: DailyRecord, work_assignment: WorkAssignment, item: WorkLogItem
) -> WorkLog:
    work_log = (
        session.query(WorkLog)
        .filter(
            WorkLog.daily_record_id == daily_record.id,
            WorkLog.work_assignment_id == work_assignment.id,
        )
        .first()
    )
    if work_log is None:
        work_log = WorkLog(daily_record_id=daily_record.id, work_assignment_id=work_assignment.id)
        session.add(work_log)
    work_log.body = item.body
    session.flush()
    return work_log


def _apply_work_logs(session: Session, daily_record: DailyRecord, items: list[WorkLogItem]) -> None:
    work_assignments = _load_work_assignments(session, {item.work_assignment_id for item in items})
    for work_assignment in work_assignments.values():
        goal_service.ensure_operation_allowed(work_assignment.goal, GoalOperation.RECORD)
    for item in items:
        _upsert_work_log(session, daily_record, work_assignments[item.work_assignment_id], item)


def apply_progress(session: Session, daily_record: DailyRecord, items: list[WorkLogItem]) -> None:
    """`record_service_common.register_progress`から呼ばれる、仕事（WORK）分の適用。

    入力が無ければ何もしない（register_progressのディスパッチから無条件に呼ばれるため、
    空リストの早期returnをここで行う。実装フェーズ分割計画書S02、複雑度分割）。
    """
    if not items:
        return
    _apply_work_logs(session, daily_record, items)
    if _get_category_state(daily_record, GoalCategory.WORK) is None:
        _set_category_state(daily_record, GoalCategory.WORK, RecordState.PROGRESS_ONLY)


def finalize_work_record(
    session: Session,
    target_date: dt.date,
    items: list[WorkLogItem],
    today: dt.date,
) -> DailyRecord:
    """仕事の報告を確定する（未入力/進捗のみ登録済 → 報告済）。

    資格勉強・読書の確定状態には影響しない（仕様変更2026-09-05）。
    """
    record = get_daily_record(session, target_date)
    _ensure_category_not_reported(record, target_date, GoalCategory.WORK)
    _ensure_finalizable_date(target_date, today)

    record = record or _create_record(session, target_date)
    _apply_work_logs(session, record, items)
    _set_category_state(record, GoalCategory.WORK, RecordState.REPORTED)
    session.flush()
    return record


def get_previous_work_log(
    session: Session, work_assignment_id: int, before_date: dt.date
) -> PreviousEntry | None:
    """対象案件について、対象日より前で直近の業務記録を取得する。"""
    return _get_previous_entry(
        session, WorkLog, WorkLog.work_assignment_id, work_assignment_id, WorkLog.body, before_date
    )
