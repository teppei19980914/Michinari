"""完了処理のAPI：受験結果登録（仕様書6.9 SC-10）・総括レポート（6.10 SC-13の一部）。

データ構造編6.2「完了処理とエクスポート」のエンドポイント一覧に対応する
（実装フェーズ分割計画書Phase10）。目標のクローズ自体は既存の
POST /goals/{id}/close（api/goals.py、Phase3実装）をそのまま使う。
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.constants.enums import RetrospectivePeriodType
from app.database import get_db
from app.schemas.retrospective import (
    MonthlyReportUpdateRequest,
    RetrospectiveGenerateRequest,
    RetrospectiveRead,
    SemiannualReviewUpdateRequest,
    WorkReportGenerateRequest,
    WorkReportRead,
)
from app.schemas.subject import ExamResultCreate, ExamResultRead, ExamResultUpdate
from app.services import goal_service, retrospective_service, subject_service, work_report_service

router = APIRouter(tags=["closure"])


@router.post(
    "/subjects/{subject_id}/result",
    response_model=ExamResultRead,
    status_code=status.HTTP_201_CREATED,
)
def register_exam_result(
    subject_id: int, payload: ExamResultCreate, session: Session = Depends(get_db)
) -> ExamResultRead:
    subject = subject_service.get_subject(session, subject_id)
    exam_result = subject_service.register_exam_result(session, subject, **payload.model_dump())
    session.commit()
    return ExamResultRead.model_validate(exam_result)


@router.patch("/results/{result_id}", response_model=ExamResultRead)
def update_exam_result(
    result_id: int, payload: ExamResultUpdate, session: Session = Depends(get_db)
) -> ExamResultRead:
    exam_result = subject_service.get_exam_result(session, result_id)
    subject_service.update_exam_result(
        session, exam_result, **payload.model_dump(exclude_unset=True)
    )
    session.commit()
    return ExamResultRead.model_validate(exam_result)


@router.get("/goals/{goal_id}/retrospective", response_model=RetrospectiveRead | None)
def get_retrospective(
    goal_id: int, anonymized: bool = False, session: Session = Depends(get_db)
) -> RetrospectiveRead | None:
    goal = goal_service.get_goal(session, goal_id)
    retrospective = retrospective_service.get_latest_retrospective(
        session, goal, anonymized=anonymized
    )
    return RetrospectiveRead.model_validate(retrospective) if retrospective is not None else None


@router.post("/goals/{goal_id}/retrospective", response_model=RetrospectiveRead)
def generate_retrospective(
    goal_id: int, payload: RetrospectiveGenerateRequest, session: Session = Depends(get_db)
) -> RetrospectiveRead:
    goal = goal_service.get_goal(session, goal_id)
    today = goal_service.resolve_today(session)
    retrospective = retrospective_service.generate_retrospective(
        session, goal, today=today, anonymize=payload.anonymize
    )
    session.commit()
    return RetrospectiveRead.model_validate(retrospective)


# --- 月次報告・半期評価（category=WORKの場合のみ、データ構造編6.2、
# --- 実装フェーズ分割計画書Phase22） ---


@router.post("/goals/{goal_id}/monthly-report", response_model=WorkReportRead)
def generate_monthly_report(
    goal_id: int, payload: WorkReportGenerateRequest, session: Session = Depends(get_db)
) -> WorkReportRead:
    goal = goal_service.get_goal(session, goal_id)
    today = goal_service.resolve_today(session)
    retrospective = work_report_service.generate_monthly_report(
        session, goal, period_key=payload.period, today=today, anonymize=payload.anonymize
    )
    session.commit()
    return WorkReportRead.model_validate(retrospective)


@router.get("/goals/{goal_id}/monthly-report", response_model=WorkReportRead | None)
def get_monthly_report(
    goal_id: int,
    period: str | None = None,
    anonymized: bool = False,
    session: Session = Depends(get_db),
) -> WorkReportRead | None:
    goal = goal_service.get_goal(session, goal_id)
    today = goal_service.resolve_today(session)
    resolved_period = period or work_report_service.default_monthly_period_key(today)
    retrospective = work_report_service.get_work_report(
        session,
        goal,
        period_type=RetrospectivePeriodType.MONTHLY,
        period_key=resolved_period,
        anonymized=anonymized,
    )
    return WorkReportRead.model_validate(retrospective) if retrospective is not None else None


@router.patch("/goals/{goal_id}/monthly-report", response_model=WorkReportRead)
def update_monthly_report(
    goal_id: int,
    period: str,
    payload: MonthlyReportUpdateRequest,
    session: Session = Depends(get_db),
) -> WorkReportRead:
    goal = goal_service.get_goal(session, goal_id)
    retrospective = work_report_service.update_monthly_report(
        session, goal, period_key=period, **payload.model_dump(exclude_unset=True)
    )
    session.commit()
    return WorkReportRead.model_validate(retrospective)


@router.post("/goals/{goal_id}/semiannual-review", response_model=WorkReportRead)
def generate_semiannual_review(
    goal_id: int, payload: WorkReportGenerateRequest, session: Session = Depends(get_db)
) -> WorkReportRead:
    goal = goal_service.get_goal(session, goal_id)
    today = goal_service.resolve_today(session)
    retrospective = work_report_service.generate_semiannual_review(
        session, goal, period_key=payload.period, today=today, anonymize=payload.anonymize
    )
    session.commit()
    return WorkReportRead.model_validate(retrospective)


@router.get("/goals/{goal_id}/semiannual-review", response_model=WorkReportRead | None)
def get_semiannual_review(
    goal_id: int,
    period: str | None = None,
    anonymized: bool = False,
    session: Session = Depends(get_db),
) -> WorkReportRead | None:
    goal = goal_service.get_goal(session, goal_id)
    today = goal_service.resolve_today(session)
    resolved_period = period or work_report_service.default_semiannual_period_key(today)
    retrospective = work_report_service.get_work_report(
        session,
        goal,
        period_type=RetrospectivePeriodType.SEMI_ANNUAL,
        period_key=resolved_period,
        anonymized=anonymized,
    )
    return WorkReportRead.model_validate(retrospective) if retrospective is not None else None


@router.patch("/goals/{goal_id}/semiannual-review", response_model=WorkReportRead)
def update_semiannual_review(
    goal_id: int,
    period: str,
    payload: SemiannualReviewUpdateRequest,
    session: Session = Depends(get_db),
) -> WorkReportRead:
    goal = goal_service.get_goal(session, goal_id)
    retrospective = work_report_service.update_semiannual_review(
        session, goal, period_key=period, **payload.model_dump(exclude_unset=True)
    )
    session.commit()
    return WorkReportRead.model_validate(retrospective)
