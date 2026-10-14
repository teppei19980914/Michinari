"""目標の状態遷移（設計書データ構造編5.3・6.2、仕様書6.2・7.1章、開発Todo 1-1〜1-7）。

共通ガード・CRUDは`goal_service.py`を参照（実装フェーズ分割計画書S02、`goal_service.py`
からの分割。資格試験・読書・仕事の3カテゴリの分岐がほとんどの関数内に混在しており
カテゴリ別ファイルには馴染まないため、処理の段階別に分割した）。
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.constants.app_setting_keys import RESUME_QUOTA_WARNING_RATIO
from app.constants.enums import BaselineReason, ExamResultType, GoalCategory, GoalStatus
from app.constants.goal_transitions import RESUME_WARNING_QUOTA_INCREASED, GoalOperation
from app.models.base import utcnow
from app.models.goal import Goal
from app.services import allocation_service, baseline_service, goal_service, setting_reader
from app.services.exceptions import (
    ExamResultsIncompleteError,
    ExamSubjectRequiredError,
    InvalidStateTransitionError,
    MaterialRequiredError,
    ResourceAllocationRequiredError,
    ValidationError,
)


def _change_status(session: Session, goal: Goal, new_status: GoalStatus) -> None:
    """目標の状態を変更し、状態遷移履歴に1行追加する（開発Todo 1-6、履歴は報告率の計算に使う）。

    状態変更はこの関数に集約する。遷移の判定で拒否された場合はここに到達しないため、履歴も残らない。
    """
    goal_service._append_status_history(
        session, goal, from_status=goal.status, to_status=new_status
    )
    goal.status = new_status


def _validate_allocation_capacity(session: Session, goal: Goal) -> None:
    """目標の現在の配分が、各スロットの容量に収まることを検証する（データ構造編5.2）。

    開始・復帰の時点で、他のACTIVEな目標の配分と合わせて超過しないかを見る。設定時点では
    ACTIVEでなかった目標（DRAFT・PAUSED）が合計計算に算入されていないため、状態遷移の
    たびに検証し直す必要がある（仕様書7.1）。
    """
    allocation_service.validate_capacity(
        session,
        allocation_service.get_allocation_minutes(session, goal.id),
        exclude_goal_id=goal.id,
    )


def activate_goal(session: Session, goal: Goal) -> Goal:
    """下書き→進行中（仕様書7.1）。前提未達・リソース超過時は例外を送出する。

    読書目標（category=READING）は書籍の登録のみを前提とし、教材・リソース配分・
    計画基準値（EXAM固有の計画管理、要件定義書R-71）は対象外とする。仕事目標
    （category=WORK）は案件情報の登録のみを前提とする（要件定義書R-74）。
    """
    goal_service.ensure_operation_allowed(goal, GoalOperation.ACTIVATE)
    if goal.archived_at is not None:
        raise InvalidStateTransitionError("Goal is archived; restore it before starting")

    if goal.category == GoalCategory.READING:
        if goal.book is None:
            raise ValidationError("Register a book first")
    elif goal.category == GoalCategory.WORK:
        if goal.work_assignment is None:
            raise ValidationError("Register work assignment information first")
    else:
        if not goal.exam_subjects:
            raise ExamSubjectRequiredError
        if not goal.materials:
            raise MaterialRequiredError
        if allocation_service.sum_allocated_minutes(session, goal.id) <= 0:
            raise ResourceAllocationRequiredError

    # 読書目標は配分が任意（R-64）のため配分の有無は問わないが、配分を持つ場合は
    # 資格試験と同様にスロットの空きを検証する。仕事目標は配分の対象外（R-74）。
    if goal.category != GoalCategory.WORK:
        _validate_allocation_capacity(session, goal)

    _change_status(session, goal, GoalStatus.ACTIVE)
    goal.activated_at = utcnow()
    session.flush()

    if goal.category == GoalCategory.EXAM:
        today = goal_service.resolve_today(session)
        treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)
        for material in goal.materials:
            if material.is_active:
                goal_service.record_baseline_for_material(
                    session, material, BaselineReason.INITIAL, today, treat_holiday_as_buffer
                )
    return goal


def pause_goal(session: Session, goal: Goal) -> Goal:
    """進行中→一時停止（仕様書7.1）。リソース配分は解放される（合計計算から除外）。"""
    goal_service.ensure_operation_allowed(goal, GoalOperation.PAUSE)
    _change_status(session, goal, GoalStatus.PAUSED)
    session.flush()
    return goal


@dataclass(frozen=True)
class ResumeResult:
    """再開の結果。warnings は警告コードの一覧（資格試験の再計画で学習量が増えた場合など）。"""

    goal: Goal
    warnings: list[str]


def resume_goal(session: Session, goal: Goal) -> ResumeResult:
    """一時停止・中断・完了→進行中（仕様書7.1、開発Todo 1-5）。

    リソースの空きが不足する場合はエラーとする。資格試験目標は「配分が1分以上あること」を
    要求する。読書目標は配分が任意のため（要件定義書R-64）、未設定でも復帰できる。ただし配分を
    持つ場合は、資格試験と同様にスロットの空きが足りるかを検証する（仕様書7.1）。仕事目標は
    配分の対象外（R-74）。

    中断・完了からの再開では、データを引き継ぐ（開始日は変更しない）。終了時刻（closed_at）は
    再開により意味を失うため解除する（終了の履歴は状態遷移履歴に残る）。資格試験は再開日から
    残り期間で計画（基準値）を組み直し、学習量が大きく増える場合は警告を返したうえで再開を許可する。
    """
    goal_service.ensure_operation_allowed(goal, GoalOperation.RESUME)
    if goal.archived_at is not None:
        raise InvalidStateTransitionError("Goal is archived; restore it before resuming")
    if goal.category == GoalCategory.EXAM:
        if allocation_service.sum_allocated_minutes(session, goal.id) <= 0:
            raise ResourceAllocationRequiredError
    if goal.category != GoalCategory.WORK:
        _validate_allocation_capacity(session, goal)
    was_closed = goal.status in goal_service._CLOSED_STATUSES
    _change_status(session, goal, GoalStatus.ACTIVE)
    if was_closed:
        goal.closed_at = None
    goal.resumed_at = utcnow()
    session.flush()

    warnings: list[str] = []
    if goal.category == GoalCategory.EXAM:
        warnings = _replan_on_resume(session, goal)
    session.flush()
    return ResumeResult(goal=goal, warnings=warnings)


def _replan_on_resume(session: Session, goal: Goal) -> list[str]:
    """再開日から残り期間で、教材ごとに計画基準値を組み直す（開発Todo 1-5）。

    停止前の基準値（1日あたりの必要量）より、再計画後の値が設定倍率以上に増えた場合に警告する。
    倍率は app_setting から読む（閾値をソースに書かない）。停止前の基準値が無い教材は
    比較できないため警告しない。
    """
    today = goal_service.resolve_today(session)
    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)
    ratio = setting_reader.get_float(session, RESUME_QUOTA_WARNING_RATIO)
    warnings: set[str] = set()
    for material in goal.materials:
        if not material.is_active:
            continue
        previous = baseline_service.get_current_baseline(session, material.id, today)
        current = goal_service.record_baseline_for_material(
            session, material, BaselineReason.RESUMED, today, treat_holiday_as_buffer
        )
        if (
            previous is not None
            and previous.baseline_daily_quota > 0
            and current.baseline_daily_quota / previous.baseline_daily_quota >= ratio
        ):
            warnings.add(RESUME_WARNING_QUOTA_INCREASED)
    return sorted(warnings)


def abandon_goal(session: Session, goal: Goal) -> Goal:
    """中断する（実行中・一時停止→中断、開発Todo 1-3）。

    中断の表示名は種類ごとに異なる（読書＝中断、資格試験＝中断、仕事＝中止・打ち切り。1-2）。
    内部の状態は CLOSED_WITHOUT_RESULT に統一する。確認は画面で1回行う。
    """
    goal_service.ensure_operation_allowed(goal, GoalOperation.ABANDON)
    _change_status(session, goal, GoalStatus.CLOSED_WITHOUT_RESULT)
    goal.closed_at = utcnow()
    session.flush()
    return goal


def complete_goal(session: Session, goal: Goal) -> Goal:
    """完了する（実行中→完了、開発Todo 1-3）。

    完了の条件は種類ごとに異なる。資格試験は全科目の合否が登録済みであること（揃っていない場合は
    ExamResultsIncompleteErrorで拒否し、画面は完了ボタンを無効化する）。読書は書籍の登録済み
    （読了として記録する操作の後継）。仕事は案件情報の登録済み。完了の内部状態は
    CLOSED_WITH_RESULT（読書では「読了」、資格試験では「完了」、仕事では「完了」と表示する）。
    """
    goal_service.ensure_operation_allowed(goal, GoalOperation.COMPLETE)
    if goal.category == GoalCategory.READING:
        if goal.book is None:
            raise ValidationError("Register a book first")
    elif goal.category == GoalCategory.WORK:
        if goal.work_assignment is None:
            raise ValidationError("Register work assignment information first")
    else:
        has_all_results = bool(goal.exam_subjects) and all(
            subject.exam_result is not None for subject in goal.exam_subjects
        )
        if not has_all_results:
            raise ExamResultsIncompleteError
    _change_status(session, goal, GoalStatus.CLOSED_WITH_RESULT)
    goal.closed_at = utcnow()
    session.flush()
    return goal


def compute_is_achieved(goal: Goal) -> bool:
    """目標が達成済みかどうかを判定する（仕様書v1.1 13.6、S-12の解消）。

    CLOSED_WITH_RESULTは「結果が登録済み」を意味するだけで、資格試験（EXAM）は
    合否（ExamResultType.PASS/FAIL）を区別しない（complete_goalのhas_all_results判定と同じ
    exam_subjects/exam_resultを参照）。そのためEXAMのみ、全科目がPASSであることまで
    確認する。読書（complete_goal）・仕事（完了）は
    CLOSED_WITH_RESULTへの到達自体が達成を意味するため、追加判定を行わない。
    """
    if goal.status != GoalStatus.CLOSED_WITH_RESULT:
        return False
    if goal.category != GoalCategory.EXAM:
        return True
    return bool(goal.exam_subjects) and all(
        subject.exam_result is not None and subject.exam_result.result == ExamResultType.PASS
        for subject in goal.exam_subjects
    )
