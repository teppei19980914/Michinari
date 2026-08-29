"""試験科目のCRUD・受験日の確定処理（設計書データ構造編5.3・6.2、
仕様書6.2・7.3・10章、実装フェーズ分割計画書Phase3）。
"""

import datetime as dt

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.constants.enums import BaselineReason, ExamDateType, ExamResultType, PassingScoreType
from app.models.base import utcnow
from app.models.goal import ExamSubject, Goal
from app.models.record import ExamResult
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


def _validate_passing_score(
    passing_score_type: PassingScoreType,
    passing_score: float | None,
    passing_score_max: float | None,
) -> None:
    """合格点を検証する。百分率(PERCENTAGE)は0〜100、点数(RAW_SCORE)は0〜満点の範囲とする。"""
    if passing_score is None:
        if passing_score_max is not None:
            raise ValidationError("合格点を指定しない場合、満点は指定できません")
        return
    if passing_score_type == PassingScoreType.RAW_SCORE:
        if passing_score_max is None:
            raise ValidationError("点数で入力する場合、満点を指定してください")
        if passing_score_max <= 0:
            raise ValidationError("満点は0より大きい値で入力してください")
        if not (0 <= passing_score <= passing_score_max):
            raise ValidationError("合格点は0〜満点の範囲で入力してください")
    else:
        if passing_score_max is not None:
            raise ValidationError("百分率で入力する場合、満点は指定できません")
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
    passing_score_type: PassingScoreType = PassingScoreType.PERCENTAGE,
    passing_score_max: float | None = None,
) -> ExamSubject:
    goal_service.ensure_goal_editable(goal)
    _validate_exam_dates(exam_date_type, exam_date_from, exam_date_to, exam_date_fixed)
    _validate_passing_score(passing_score_type, passing_score, passing_score_max)

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
        passing_score_type=passing_score_type,
        passing_score_max=passing_score_max,
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
    passing_score_type: PassingScoreType | None = None,
    passing_score_max: float | None = None,
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

    # passing_score_typeが指定された場合はモード切替とみなし、passing_score_maxは
    # 明示的に渡された値（未指定ならNone＝クリア）で置き換える。未指定の場合は既存値を保持する。
    if passing_score_type is not None:
        resolved_passing_score_type = passing_score_type
        resolved_passing_score_max = passing_score_max
    else:
        resolved_passing_score_type = subject.passing_score_type
        resolved_passing_score_max = (
            passing_score_max if passing_score_max is not None else subject.passing_score_max
        )
    resolved_passing_score = passing_score if passing_score is not None else subject.passing_score
    _validate_passing_score(
        resolved_passing_score_type, resolved_passing_score, resolved_passing_score_max
    )

    old_effective_date = material_service.effective_exam_date(subject)

    if name is not None:
        subject.name = name
    if passing_score is not None:
        subject.passing_score = passing_score
    subject.passing_score_type = resolved_passing_score_type
    subject.passing_score_max = resolved_passing_score_max
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


# --- 受験結果（仕様書6.9 SC-10、実装フェーズ分割計画書Phase10） ---


def get_exam_result(session: Session, result_id: int) -> ExamResult:
    result = session.get(ExamResult, result_id)
    if result is None:
        raise NotFoundError("受験結果", result_id)
    return result


def register_exam_result(
    session: Session,
    subject: ExamSubject,
    *,
    taken_date: dt.date,
    result: ExamResultType,
    score: float | None,
    evaluation: str | None,
    note: str | None,
) -> ExamResult:
    """科目に受験結果を登録する（仕様書6.9）。1科目につき1件のみ（更新はPATCH /results/{id}）。"""
    goal_service.ensure_goal_editable(subject.goal)
    if subject.exam_result is not None:
        raise ValidationError(
            f"試験科目(id={subject.id})には既に受験結果が登録されています。更新はPATCHで行ってください"
        )

    exam_result = ExamResult(
        subject_id=subject.id,
        taken_date=taken_date,
        result=result,
        score=score,
        evaluation=evaluation,
        note=note,
        created_at=utcnow(),
    )
    session.add(exam_result)
    session.flush()
    return exam_result


def update_exam_result(
    session: Session,
    exam_result: ExamResult,
    *,
    taken_date: dt.date | None = None,
    result: ExamResultType | None = None,
    score: float | None = None,
    evaluation: str | None = None,
    note: str | None = None,
) -> ExamResult:
    """受験結果を更新する（仕様書6.10 PATCH /results/{id}「クローズ前のみ」）。"""
    goal_service.ensure_goal_editable(exam_result.subject.goal)

    if taken_date is not None:
        exam_result.taken_date = taken_date
    if result is not None:
        exam_result.result = result
    if score is not None:
        exam_result.score = score
    if evaluation is not None:
        exam_result.evaluation = evaluation
    if note is not None:
        exam_result.note = note
    session.flush()
    return exam_result
