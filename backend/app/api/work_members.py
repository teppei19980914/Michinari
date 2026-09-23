"""チームメンバーのAPI（要件定義書6.11、materials.pyと同型の独立リソースパス）。

作成のみ目標配下のネストパス（POST /goals/{goal_id}/work-assignment/members、
api/goals.py）に置く（materials.pyのPOST /goals/{goal_id}/materialsと同じ方針）。
一覧取得は専用エンドポイントを設けず、GET /goals/{id}のWorkAssignmentRead.membersへの
埋め込みで代替する（目標詳細画面・日次報告画面の双方が同じ取得経路を通ることで、
追加の同期機構なしにメンバー情報を両画面へ伝播できるため、要件定義書6.11「同期」）。
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.work import serialize_work_member
from app.database import get_db
from app.schemas.work import WorkMemberRead, WorkMemberUpdate
from app.services import work_member_service

router = APIRouter(tags=["work-members"])


@router.patch("/work-members/{member_id}", response_model=WorkMemberRead)
def update_work_member(
    member_id: int, payload: WorkMemberUpdate, session: Session = Depends(get_db)
) -> WorkMemberRead:
    member = work_member_service.get_member(session, member_id)
    work_member_service.update_work_member(
        session, member, **payload.model_dump(exclude_unset=True)
    )
    session.commit()
    return serialize_work_member(member)


@router.delete("/work-members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_member(member_id: int, session: Session = Depends(get_db)) -> None:
    member = work_member_service.get_member(session, member_id)
    work_member_service.delete_work_member(session, member)
    session.commit()


@router.post("/work-members/{member_id}/deactivate", response_model=WorkMemberRead)
def deactivate_work_member(member_id: int, session: Session = Depends(get_db)) -> WorkMemberRead:
    member = work_member_service.get_member(session, member_id)
    work_member_service.deactivate_work_member(session, member)
    session.commit()
    return serialize_work_member(member)
