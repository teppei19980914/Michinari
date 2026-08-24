"""試験科目のCRUD・受験日の確定処理（設計書データ構造編5.3・6.2、
仕様書6.2・7.3・10章、実装フェーズ分割計画書Phase3）。
"""

import datetime as dt

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.constants.enums import BaselineReason, ExamDateType
from app.models.goal import ExamSubject, Goal
from app.services import goal_service, material_service
from app.services.exceptions import NotFoundError, ValidationError

_PASSING_SCORE_MIN = 0.0
_PASSING_SCORE_MAX = 100.0


def get_subject(session: Session, subject_id: int) -> ExamSubject:
    subject = session.get(ExamSubject, subject_id)
    if subject is None:
        raise NotFoundError("試験科目", subject_id)
    return subject


def _validate_exam_dates(
    exam_date_type: ExamDateType,
    exam_date_from: dt.date | None,
    exam_date_to: dt.date | None,
    exam_date_fixed: dt.date | None,
) -> None:
    if exam_date_type == ExamDateType.RANGE:
        if exam_date_from is None or exam_date_to is None:
            raise ValidationError("受験日タイプが期間の場合、期間開始日・終了日を指定してください")
        if exam_date_from > exam_date_to:
            raise ValidationError("期間開始日は期間終了日以前にしてください")
    elif exam_date_fixed is None:
        raise ValidationError("受験日タイプが確定日の場合、確定日を指定してください")


def _validate_passing_score(passing_score: float | None) -> None:
    if passing_score is None:
        return
    if not (_PASSING_SCORE_MIN <= passing_score <= _PASSING_SCORE_MAX):
        raise ValidationError("合格基準点は0〜100で入力してください")


def create_subject(
    session: Session,
    goal: Goal,
    *,
    name: str,
    exam_date_type: ExamDateType,
    exam_date_from: dt.date | None,
    exam_date_to: dt.date | None,
    exam_date_fixed: dt.date | None,
    passing_score: float | None,
) -> ExamSubject:
    goal_service.ensure_goal_editable(goal)
    _validate_exam_dates(exam_date_type, exam_date_from, exam_date_to, exam_date_fixed)
    _validate_passing_score(passing_score)

    next_order = (
        session.query(func.max(ExamSubject.display_order))
        .filter(ExamSubject.goal_id == goal.id)
        .scalar()
        or 0
    ) + 1
    subject = ExamSubject(
        goal_id=goal.id,
        name=name,
        exam_date_type=exam_date_type,
        exam_date_from=exam_date_from,
        exam_date_to=exam_date_to,
        exam_date_fixed=exam_date_fixed,
        passing_score=passing_score,
        display_order=next_order,
    )
    session.add(subject)
    session.flush()
    return subject


def update_subject(
    session: Session,
    subject: ExamSubject,
    *,
    name: str | None = None,
    exam_date_type: ExamDateType | None = None,
    exam_date_from: dt.date | None = None,
    exam_date_to: dt.date | None = None,
    exam_date_fixed: dt.date | None = None,
    passing_score: float | None = None,
) -> ExamSubject:
    """科目を更新する。有効受験日が変化した場合、締切自動導出の教材へMATERIAL_CHANGEDとして
    再計算を伝播する（データ構造編5.3「紐づく科目の受験日が変更されたとき」）。
    """
    goal_service.ensure_goal_editable(subject.goal)

    resolved_type = exam_date_type if exam_date_type is not None else subject.exam_date_type
    resolved_from = exam_date_from if exam_date_from is not None else subject.exam_date_from
    resolved_to = exam_date_to if exam_date_to is not None else subject.exam_date_to
    resolved_fixed = exam_date_fixed if exam_date_fixed is not None else subject.exam_date_fixed
    _validate_exam_dates(resolved_type, resolved_from, resolved_to, resolved_fixed)
    _validate_passing_score(passing_score)

    old_effective_date = material_service.effective_exam_date(subject)

    if name is not None:
        subject.name = name
    if passing_score is not None:
        subject.passing_score = passing_score
    subject.exam_date_type = resolved_type
    subject.exam_date_from = resolved_from
    subject.exam_date_to = resolved_to
    subject.exam_date_fixed = resolved_fixed
    session.flush()

    new_effective_date = material_service.effective_exam_date(subject)
    if new_effective_date != old_effective_date:
        today = goal_service.resolve_today(session)
        treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)
        material_service.recalculate_due_dates_for_subject(
            session, subject, BaselineReason.MATERIAL_CHANGED, today, treat_holiday_as_buffer
        )
    return subject


def delete_subject(session: Session, subject: ExamSubject) -> None:
    goal_service.ensure_goal_editable(subject.goal)
    session.delete(subject)
    session.flush()


def fix_exam_date(session: Session, subject: ExamSubject, exam_date_fixed: dt.date) -> ExamSubject:
    """受験日を確定日に変更し、締切自動導出の教材の計画を再算出する（仕様書7.3）。

    範囲指定の期間（exam_date_from/to）はデータとして保持する。確定日から期間への
    逆遷移（誤操作の訂正、仕様書7.3）で再利用できるようにするためであり、削除しない。
    """
    goal_service.ensure_goal_editable(subject.goal)
    subject.exam_date_type = ExamDateType.FIXED
    subject.exam_date_fixed = exam_date_fixed
    session.flush()

    today = goal_service.resolve_today(session)
    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)
    material_service.recalculate_due_dates_for_subject(
        session, subject, BaselineReason.EXAM_DATE_FIXED, today, treat_holiday_as_buffer
    )
    return subject
