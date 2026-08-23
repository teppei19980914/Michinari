"""教材のCRUD・締切自動導出・周回別進捗の取得（設計書データ構造編5.3・6.2、
仕様書6.2・10章、ロジック・プロンプト編12.1、実装フェーズ分割計画書Phase3）。

due_date の自動導出（有効受験日の導出を含む）は本ファイルが唯一の実装箇所とする
（CLAUDE.md DRYの原則）。subject_service はここから effective_exam_date /
recalculate_due_dates_for_subject を呼び出す一方向依存とし、循環importを避ける。
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.constants.enums import BaselineReason, Environment, ExamDateType, QualityMetricType
from app.models.goal import ExamSubject, Goal
from app.models.material import Material, MaterialSubject
from app.models.record import StudyLog
from app.services import cycle_service, goal_service, metrics_service, slot_service, speed_service
from app.services.exceptions import MaterialHasStudyLogsError, NotFoundError, ValidationError

#: 作成・更新の両方で使う検証メッセージ（CLAUDE.md DRYの原則: 値の重複を避ける）。
_MSG_TOTAL_AMOUNT_NEGATIVE = "総量は0以上で入力してください"
_MSG_PLANNED_CYCLES_BELOW_ONE = "予定周回数は1以上の整数で入力してください"
_MSG_START_DATE_AFTER_DUE_DATE = "開始日は締切より前の日付にしてください"


def get_material(session: Session, material_id: int) -> Material:
    material = session.get(Material, material_id)
    if material is None:
        raise NotFoundError("教材", material_id)
    return material


def effective_exam_date(subject: ExamSubject) -> dt.date:
    """科目の有効受験日を導出する（データ構造編5.3）。RANGEは期間開始日（最も早い日）を採用する。"""
    if subject.exam_date_type == ExamDateType.FIXED:
        return subject.exam_date_fixed
    return subject.exam_date_from


def compute_due_date(subjects: list[ExamSubject]) -> dt.date:
    """紐づく科目の最も早い有効受験日の前日を締切として算出する（データ構造編5.3）。"""
    earliest = min(effective_exam_date(subject) for subject in subjects)
    return earliest - dt.timedelta(days=1)


def _resolve_subjects(session: Session, goal: Goal, subject_ids: list[int]) -> list[ExamSubject]:
    if not subject_ids:
        raise ValidationError("対策する科目を1件以上指定してください")
    unique_ids = set(subject_ids)
    subjects = session.query(ExamSubject).filter(ExamSubject.id.in_(unique_ids)).all()
    if len(subjects) != len(unique_ids):
        found_ids = {subject.id for subject in subjects}
        raise NotFoundError("試験科目", sorted(unique_ids - found_ids))
    for subject in subjects:
        if subject.goal_id != goal.id:
            raise ValidationError("教材と異なる目標の科目は紐付けられません")
    return subjects


def _replace_subject_links(session: Session, material: Material, subject_ids: list[int]) -> None:
    subjects = _resolve_subjects(session, material.goal, subject_ids)
    session.query(MaterialSubject).filter(MaterialSubject.material_id == material.id).delete()
    session.flush()
    for subject in subjects:
        session.add(MaterialSubject(material_id=material.id, subject_id=subject.id))
    session.flush()


def create_material(
    session: Session,
    goal: Goal,
    *,
    name: str,
    unit_label: str,
    total_amount: float,
    planned_cycles: int,
    subject_ids: list[int],
    start_date: dt.date,
    due_date: dt.date | None,
    due_date_is_manual: bool,
    required_block_minutes: int | None,
    required_environment: Environment,
    quality_metric_type: QualityMetricType,
) -> Material:
    goal_service.ensure_goal_editable(goal)
    if total_amount < 0:
        raise ValidationError(_MSG_TOTAL_AMOUNT_NEGATIVE)
    if planned_cycles < 1:
        raise ValidationError(_MSG_PLANNED_CYCLES_BELOW_ONE)

    subjects = _resolve_subjects(session, goal, subject_ids)
    if due_date_is_manual:
        if due_date is None:
            raise ValidationError("締切を手動設定する場合は締切日を指定してください")
        resolved_due_date = due_date
    else:
        resolved_due_date = compute_due_date(subjects)
    if start_date > resolved_due_date:
        raise ValidationError(_MSG_START_DATE_AFTER_DUE_DATE)

    next_order = (
        session.query(func.max(Material.display_order)).filter(Material.goal_id == goal.id).scalar()
        or 0
    ) + 1
    material = Material(
        goal_id=goal.id,
        name=name,
        unit_label=unit_label,
        total_amount=total_amount,
        planned_cycles=planned_cycles,
        start_date=start_date,
        due_date=resolved_due_date,
        due_date_is_manual=due_date_is_manual,
        required_block_minutes=required_block_minutes,
        required_environment=required_environment,
        quality_metric_type=quality_metric_type,
        display_order=next_order,
    )
    session.add(material)
    session.flush()
    for subject in subjects:
        session.add(MaterialSubject(material_id=material.id, subject_id=subject.id))
    session.flush()

    today = goal_service.resolve_today(session)
    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)
    goal_service.record_baseline_for_material(
        session, material, BaselineReason.MATERIAL_CHANGED, today, treat_holiday_as_buffer
    )
    return material


def update_material(
    session: Session,
    material: Material,
    *,
    name: str | None = None,
    unit_label: str | None = None,
    total_amount: float | None = None,
    planned_cycles: int | None = None,
    subject_ids: list[int] | None = None,
    start_date: dt.date | None = None,
    due_date: dt.date | None = None,
    due_date_is_manual: bool | None = None,
    required_block_minutes: int | None = None,
    required_environment: Environment | None = None,
    quality_metric_type: QualityMetricType | None = None,
) -> Material:
    """教材を更新する。予定周回数の変更はCYCLE_CHANGED、総量・締切の変更はMATERIAL_CHANGED
    として基準値を再設定する（ロジック・プロンプト編12.1）。両方に該当する場合は、より契機が
    限定的なCYCLE_CHANGEDを優先し、1回の更新につき基準値レコードは1件とする。
    """
    goal_service.ensure_goal_editable(material.goal)

    old_total_amount = material.total_amount
    old_due_date = material.due_date
    cycle_changed = _apply_planned_cycles_change(session, material, planned_cycles)
    _apply_simple_fields(
        material,
        name=name,
        unit_label=unit_label,
        total_amount=total_amount,
        required_block_minutes=required_block_minutes,
        required_environment=required_environment,
        quality_metric_type=quality_metric_type,
    )
    if due_date_is_manual is not None:
        material.due_date_is_manual = due_date_is_manual
    if subject_ids is not None:
        _replace_subject_links(session, material, subject_ids)
    _apply_due_date(material, due_date)

    if start_date is not None:
        material.start_date = start_date
    if material.start_date > material.due_date:
        raise ValidationError(_MSG_START_DATE_AFTER_DUE_DATE)
    session.flush()

    _maybe_record_baseline(session, material, cycle_changed, old_total_amount, old_due_date)
    return material


def _apply_planned_cycles_change(
    session: Session, material: Material, planned_cycles: int | None
) -> bool:
    if planned_cycles is None or planned_cycles == material.planned_cycles:
        return False
    if planned_cycles < 1:
        raise ValidationError(_MSG_PLANNED_CYCLES_BELOW_ONE)
    progress = cycle_service.get_material_progress(session, material)
    cycle_service.validate_planned_cycles_change(progress.current_cycle, planned_cycles)
    material.planned_cycles = planned_cycles
    return True


def _apply_simple_fields(
    material: Material,
    *,
    name: str | None,
    unit_label: str | None,
    total_amount: float | None,
    required_block_minutes: int | None,
    required_environment: Environment | None,
    quality_metric_type: QualityMetricType | None,
) -> None:
    if name is not None:
        material.name = name
    if unit_label is not None:
        material.unit_label = unit_label
    if total_amount is not None:
        if total_amount < 0:
            raise ValidationError(_MSG_TOTAL_AMOUNT_NEGATIVE)
        material.total_amount = total_amount
    if required_block_minutes is not None:
        material.required_block_minutes = required_block_minutes
    if required_environment is not None:
        material.required_environment = required_environment
    if quality_metric_type is not None:
        material.quality_metric_type = quality_metric_type


def _apply_due_date(material: Material, due_date: dt.date | None) -> None:
    if material.due_date_is_manual:
        if due_date is not None:
            material.due_date = due_date
        return
    subjects = [link.subject for link in material.subject_links]
    # subjectsが空になるのは教材が科目に1件も紐付いていない状態だが、作成時・更新時とも
    # 空リストを許容しないため到達し得ない防御的分岐（異常系、CODING_RULES.md）。
    if subjects:  # pragma: no branch
        material.due_date = compute_due_date(subjects)


def _maybe_record_baseline(
    session: Session,
    material: Material,
    cycle_changed: bool,
    old_total_amount: float,
    old_due_date: dt.date,
) -> None:
    today = goal_service.resolve_today(session)
    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)
    if cycle_changed:
        goal_service.record_baseline_for_material(
            session, material, BaselineReason.CYCLE_CHANGED, today, treat_holiday_as_buffer
        )
    elif material.total_amount != old_total_amount or material.due_date != old_due_date:
        goal_service.record_baseline_for_material(
            session, material, BaselineReason.MATERIAL_CHANGED, today, treat_holiday_as_buffer
        )


def recalculate_due_dates_for_subject(
    session: Session,
    subject: ExamSubject,
    reason: BaselineReason,
    today: dt.date,
    treat_holiday_as_buffer: bool,
) -> None:
    """科目の受験日変更を受けて、締切自動導出の教材の締切を再計算する（データ構造編5.3）。"""
    for link in subject.material_links:
        material = link.material
        if material.due_date_is_manual:
            continue
        subjects = [ml.subject for ml in material.subject_links]
        new_due_date = compute_due_date(subjects)
        if new_due_date == material.due_date:
            continue
        material.due_date = new_due_date
        session.flush()
        goal_service.record_baseline_for_material(
            session, material, reason, today, treat_holiday_as_buffer
        )


def delete_material(session: Session, material: Material) -> None:
    """実績（study_log）が存在する教材の削除は拒否する（データ構造編6.2）。"""
    goal_service.ensure_goal_editable(material.goal)
    has_logs = (
        session.query(StudyLog.id).filter(StudyLog.material_id == material.id).first() is not None
    )
    if has_logs:
        raise MaterialHasStudyLogsError(material.id)
    session.delete(material)
    session.flush()


def deactivate_material(session: Session, material: Material) -> Material:
    goal_service.ensure_goal_editable(material.goal)
    material.is_active = False
    session.flush()
    return material


def get_slot_sufficiency(session: Session, material: Material) -> bool:
    """教材の必要条件を満たすスロットが存在するかを検証する（仕様書6.2、ロジック・プロンプト編9.4）。"""
    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)
    return slot_service.validate_slot_sufficiency(session, material, treat_holiday_as_buffer)


@dataclass(frozen=True)
class CycleProgress:
    """周回ごとの進捗・速度・品質（データ構造編6.2 GET /materials/{id}/cycles）。"""

    cycle_number: int
    completed_amount: float
    speed: float | None
    sample_count: int
    quality_average: float | None


def get_cycle_progress(session: Session, material: Material) -> list[CycleProgress]:
    progress = cycle_service.get_material_progress(session, material)
    amounts_by_cycle = dict(
        session.query(StudyLog.cycle_number, func.sum(StudyLog.amount_completed))
        .filter(StudyLog.material_id == material.id)
        .group_by(StudyLog.cycle_number)
        .all()
    )
    quality_by_cycle = metrics_service.group_quality_by_cycle(session, material.id)

    cycle_numbers = sorted(set(amounts_by_cycle) | {progress.current_cycle})
    # 周回ごとに compute_cycle_speed を呼ぶとN+1になるため、一括版で1クエリにまとめる
    # （CLAUDE.md パフォーマンスチェック: N+1禁止）。
    speeds_by_cycle = speed_service.compute_cycle_speeds(session, material.id, cycle_numbers)
    results = []
    for cycle_number in cycle_numbers:
        speed_result = speeds_by_cycle.get(cycle_number)
        qualities = quality_by_cycle.get(cycle_number, [])
        results.append(
            CycleProgress(
                cycle_number=cycle_number,
                completed_amount=float(amounts_by_cycle.get(cycle_number, 0.0)),
                speed=speed_result.speed if speed_result else None,
                sample_count=speed_result.sample_count if speed_result else 0,
                quality_average=(sum(qualities) / len(qualities)) if qualities else None,
            )
        )
    return results
