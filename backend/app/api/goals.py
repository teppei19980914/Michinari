"""目標・試験科目・負荷プロファイルのAPI（データ構造編6.2、実装フェーズ分割計画書Phase3）。

教材の新規作成は目標配下のネストパス（POST /goals/{id}/materials）であるため本ファイルに置き、
個別教材の更新・削除等は materials.py に置く（データ構造編6.2のエンドポイント一覧に準拠）。
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.books import serialize_book
from app.api.materials import serialize_material
from app.database import get_db
from app.models.goal import ExamSubject, Goal
from app.schemas.book import BookCreate, BookRead
from app.schemas.goal import (
    GoalCloseRequest,
    GoalCreate,
    GoalDeleteArchivedRequest,
    GoalDetailRead,
    GoalRead,
    GoalUpdate,
    PlanBaselineRead,
)
from app.schemas.load_profile import LoadProfileCreate, LoadProfileRead, LoadProfileUpdate
from app.schemas.material import MaterialCreate, MaterialRead
from app.schemas.subject import (
    ExamResultRead,
    SubjectCreate,
    SubjectFixDateRequest,
    SubjectRead,
    SubjectUpdate,
)
from app.services import book_service, goal_service, material_service, subject_service

router = APIRouter(tags=["goals"])


def serialize_subject(subject: ExamSubject) -> SubjectRead:
    """受験結果（1:1、任意）を明示的に付与する（materials.serialize_materialと同じ理由で
    自動のネストfrom_attributes変換に頼らない、CLAUDE.md DRYの原則で共通化）。"""
    return SubjectRead(
        id=subject.id,
        goal_id=subject.goal_id,
        name=subject.name,
        exam_date_type=subject.exam_date_type,
        exam_date_from=subject.exam_date_from,
        exam_date_to=subject.exam_date_to,
        exam_date_fixed=subject.exam_date_fixed,
        passing_score=subject.passing_score,
        passing_score_type=subject.passing_score_type,
        passing_score_max=subject.passing_score_max,
        display_order=subject.display_order,
        exam_result=ExamResultRead.model_validate(subject.exam_result)
        if subject.exam_result is not None
        else None,
    )


def _serialize_goal_detail(session: Session, goal: Goal) -> GoalDetailRead:
    return GoalDetailRead(
        **GoalRead.model_validate(goal).model_dump(),
        exam_subjects=[serialize_subject(s) for s in goal.exam_subjects],
        materials=[serialize_material(session, m) for m in goal.materials],
        load_profiles=[LoadProfileRead.model_validate(p) for p in goal.load_profiles],
        book=serialize_book(session, goal.book) if goal.book is not None else None,
    )


@router.get("/goals", response_model=list[GoalRead])
def list_goals(session: Session = Depends(get_db)) -> list[GoalRead]:
    return [GoalRead.model_validate(g) for g in goal_service.list_goals(session)]


@router.post("/goals", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
def create_goal(payload: GoalCreate, session: Session = Depends(get_db)) -> GoalRead:
    goal = goal_service.create_goal(session, **payload.model_dump())
    session.commit()
    return GoalRead.model_validate(goal)


@router.get("/goals/{goal_id}", response_model=GoalDetailRead)
def get_goal(goal_id: int, session: Session = Depends(get_db)) -> GoalDetailRead:
    goal = goal_service.get_goal(session, goal_id)
    return _serialize_goal_detail(session, goal)


@router.patch("/goals/{goal_id}", response_model=GoalRead)
def update_goal(goal_id: int, payload: GoalUpdate, session: Session = Depends(get_db)) -> GoalRead:
    goal = goal_service.get_goal(session, goal_id)
    goal_service.update_goal(session, goal, **payload.model_dump(exclude_unset=True))
    session.commit()
    return GoalRead.model_validate(goal)


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: int, session: Session = Depends(get_db)) -> None:
    goal = goal_service.get_goal(session, goal_id)
    goal_service.delete_goal(session, goal)
    session.commit()


@router.patch("/goals/{goal_id}/archive", response_model=GoalRead)
def archive_goal(goal_id: int, session: Session = Depends(get_db)) -> GoalRead:
    goal = goal_service.get_goal(session, goal_id)
    goal_service.archive_goal(session, goal)
    session.commit()
    return GoalRead.model_validate(goal)


@router.patch("/goals/{goal_id}/unarchive", response_model=GoalRead)
def unarchive_goal(goal_id: int, session: Session = Depends(get_db)) -> GoalRead:
    goal = goal_service.get_goal(session, goal_id)
    goal_service.unarchive_goal(session, goal)
    session.commit()
    return GoalRead.model_validate(goal)


@router.delete("/goals/{goal_id}/archived", status_code=status.HTTP_204_NO_CONTENT)
def delete_archived_goal(
    goal_id: int, payload: GoalDeleteArchivedRequest, session: Session = Depends(get_db)
) -> None:
    goal = goal_service.get_goal(session, goal_id)
    goal_service.delete_archived_goal(
        session, goal, cascade_study_logs=payload.cascade_study_logs
    )
    session.commit()


@router.post("/goals/{goal_id}/activate", response_model=GoalRead)
def activate_goal(goal_id: int, session: Session = Depends(get_db)) -> GoalRead:
    goal = goal_service.get_goal(session, goal_id)
    goal_service.activate_goal(session, goal)
    session.commit()
    return GoalRead.model_validate(goal)


@router.post("/goals/{goal_id}/pause", response_model=GoalRead)
def pause_goal(goal_id: int, session: Session = Depends(get_db)) -> GoalRead:
    goal = goal_service.get_goal(session, goal_id)
    goal_service.pause_goal(session, goal)
    session.commit()
    return GoalRead.model_validate(goal)


@router.post("/goals/{goal_id}/resume", response_model=GoalRead)
def resume_goal(goal_id: int, session: Session = Depends(get_db)) -> GoalRead:
    goal = goal_service.get_goal(session, goal_id)
    goal_service.resume_goal(session, goal)
    session.commit()
    return GoalRead.model_validate(goal)


@router.post("/goals/{goal_id}/close", response_model=GoalRead)
def close_goal(
    goal_id: int, payload: GoalCloseRequest, session: Session = Depends(get_db)
) -> GoalRead:
    goal = goal_service.get_goal(session, goal_id)
    goal_service.close_goal(session, goal, confirm_without_result=payload.confirm_without_result)
    session.commit()
    return GoalRead.model_validate(goal)


@router.get("/goals/{goal_id}/baselines", response_model=list[PlanBaselineRead])
def get_baselines(goal_id: int, session: Session = Depends(get_db)) -> list[PlanBaselineRead]:
    goal = goal_service.get_goal(session, goal_id)
    baselines = goal_service.get_baselines(session, goal)
    return [PlanBaselineRead.model_validate(b) for b in baselines]


# --- 試験科目 ---


@router.post(
    "/goals/{goal_id}/subjects", response_model=SubjectRead, status_code=status.HTTP_201_CREATED
)
def create_subject(
    goal_id: int, payload: SubjectCreate, session: Session = Depends(get_db)
) -> SubjectRead:
    goal = goal_service.get_goal(session, goal_id)
    subject = subject_service.create_subject(session, goal, **payload.model_dump())
    session.commit()
    return serialize_subject(subject)


@router.patch("/subjects/{subject_id}", response_model=SubjectRead)
def update_subject(
    subject_id: int, payload: SubjectUpdate, session: Session = Depends(get_db)
) -> SubjectRead:
    subject = subject_service.get_subject(session, subject_id)
    subject_service.update_subject(session, subject, **payload.model_dump(exclude_unset=True))
    session.commit()
    return serialize_subject(subject)


@router.delete("/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(subject_id: int, session: Session = Depends(get_db)) -> None:
    subject = subject_service.get_subject(session, subject_id)
    subject_service.delete_subject(session, subject)
    session.commit()


@router.post("/subjects/{subject_id}/fix-date", response_model=SubjectRead)
def fix_subject_date(
    subject_id: int, payload: SubjectFixDateRequest, session: Session = Depends(get_db)
) -> SubjectRead:
    subject = subject_service.get_subject(session, subject_id)
    subject_service.fix_exam_date(session, subject, payload.exam_date_fixed)
    session.commit()
    return serialize_subject(subject)


# --- 教材（新規作成のみ。個別操作は materials.py） ---


@router.post(
    "/goals/{goal_id}/materials", response_model=MaterialRead, status_code=status.HTTP_201_CREATED
)
def create_material(
    goal_id: int, payload: MaterialCreate, session: Session = Depends(get_db)
) -> MaterialRead:
    goal = goal_service.get_goal(session, goal_id)
    material = material_service.create_material(session, goal, **payload.model_dump())
    session.commit()
    return serialize_material(session, material)


# --- 書籍（新規作成のみ。個別操作は books.py） ---


@router.post(
    "/goals/{goal_id}/book", response_model=BookRead, status_code=status.HTTP_201_CREATED
)
def create_book(goal_id: int, payload: BookCreate, session: Session = Depends(get_db)) -> BookRead:
    goal = goal_service.get_goal(session, goal_id)
    book = book_service.create_book(session, goal, **payload.model_dump())
    session.commit()
    return serialize_book(session, book)


# --- 負荷プロファイル ---


@router.get("/goals/{goal_id}/load-profiles", response_model=list[LoadProfileRead])
def list_load_profiles(goal_id: int, session: Session = Depends(get_db)) -> list[LoadProfileRead]:
    goal = goal_service.get_goal(session, goal_id)
    profiles = goal_service.list_load_profiles(session, goal)
    return [LoadProfileRead.model_validate(p) for p in profiles]


@router.post(
    "/goals/{goal_id}/load-profiles",
    response_model=LoadProfileRead,
    status_code=status.HTTP_201_CREATED,
)
def create_load_profile(
    goal_id: int, payload: LoadProfileCreate, session: Session = Depends(get_db)
) -> LoadProfileRead:
    goal = goal_service.get_goal(session, goal_id)
    profile = goal_service.create_load_profile(session, goal, **payload.model_dump())
    session.commit()
    return LoadProfileRead.model_validate(profile)


@router.patch("/load-profiles/{load_profile_id}", response_model=LoadProfileRead)
def update_load_profile(
    load_profile_id: int, payload: LoadProfileUpdate, session: Session = Depends(get_db)
) -> LoadProfileRead:
    profile = goal_service.get_load_profile(session, load_profile_id)
    goal_service.update_load_profile(session, profile, **payload.model_dump(exclude_unset=True))
    session.commit()
    return LoadProfileRead.model_validate(profile)


@router.delete("/load-profiles/{load_profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_load_profile(load_profile_id: int, session: Session = Depends(get_db)) -> None:
    profile = goal_service.get_load_profile(session, load_profile_id)
    goal_service.delete_load_profile(session, profile)
    session.commit()
