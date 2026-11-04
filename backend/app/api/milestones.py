"""節目のお祝いのAPI（開発Todo_節目のお祝い_v1.0）。

到達判定・永続化自体は記録確定（`api/records.py`の`finalize`系POST）の副作用として
行う。ここに置くエンドポイントはいずれもGoalMilestoneAchievementの読み取り・
お祝い済み更新のみで、新たな到達判定は行わない（GETに副作用を持たせないため）。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.base import utcnow
from app.models.milestone import GoalMilestoneAchievement
from app.schemas.milestone import MilestoneAchievementRead
from app.services import goal_service, milestone_service_common

router = APIRouter(tags=["milestones"])


def _serialize(row: GoalMilestoneAchievement) -> MilestoneAchievementRead:
    return MilestoneAchievementRead(
        id=row.id,
        goal_id=row.goal_id,
        milestone_type=row.milestone_type,
        milestone_key=row.milestone_key,
        achieved_at=row.achieved_at,
        celebrated_at=row.celebrated_at,
    )


@router.get("/goals/{goal_id}/milestones", response_model=list[MilestoneAchievementRead])
def list_milestones(
    goal_id: int, session: Session = Depends(get_db)
) -> list[MilestoneAchievementRead]:
    goal_service.get_goal(session, goal_id)
    rows = milestone_service_common.list_achievements(session, goal_id)
    return [_serialize(row) for row in rows]


@router.get(
    "/goals/{goal_id}/milestones/pending-celebrations",
    response_model=list[MilestoneAchievementRead],
)
def list_pending_celebrations(
    goal_id: int, session: Session = Depends(get_db)
) -> list[MilestoneAchievementRead]:
    goal_service.get_goal(session, goal_id)
    rows = milestone_service_common.list_pending_celebrations(session, goal_id)
    return [_serialize(row) for row in rows]


@router.post(
    "/goals/{goal_id}/milestones/{milestone_id}/celebrate",
    response_model=MilestoneAchievementRead,
)
def celebrate_milestone(
    goal_id: int, milestone_id: int, session: Session = Depends(get_db)
) -> MilestoneAchievementRead:
    goal_service.get_goal(session, goal_id)
    row = milestone_service_common.mark_celebrated(session, goal_id, milestone_id, utcnow())
    session.commit()
    return _serialize(row)
