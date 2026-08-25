"""完了処理のAPI：受験結果登録（仕様書6.9 SC-10）・総括レポート（6.10 SC-13の一部）。

データ構造編6.2「完了処理とエクスポート」のエンドポイント一覧に対応する
（実装フェーズ分割計画書Phase10）。目標のクローズ自体は既存の
POST /goals/{id}/close（api/goals.py、Phase3実装）をそのまま使う。
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.retrospective import RetrospectiveGenerateRequest, RetrospectiveRead
from app.schemas.subject import ExamResultCreate, ExamResultRead, ExamResultUpdate
from app.services import goal_service, retrospective_service, subject_service

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
