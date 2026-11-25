"""AIによるスケジュール修正案のAPI（開発Todo_スケジュール・ガントチャート_v1.1 13.7、単位5）。

API層はドメイン例外をHTTPへ変換するのみ（CODING_RULES.md「サービス層でのHTTP例外の
送出禁止」）。検証・AI呼び出し・保存の実体は`schedule_revision_service`が担う。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schedule import ScheduleItem
from app.models.schedule_revision import ScheduleRevisionProposal
from app.schemas.schedule_revision import (
    ScheduleRevisionDecisionOutcome,
    ScheduleRevisionDecisionsRequest,
    ScheduleRevisionDecisionsResponse,
    ScheduleRevisionGenerateRequest,
    ScheduleRevisionGenerateResult,
    ScheduleRevisionProposalItemRead,
    ScheduleRevisionProposalRead,
)
from app.services import goal_service, schedule_revision_service

router = APIRouter(tags=["schedule-revision"])


def serialize_proposal(
    session: Session, proposal: ScheduleRevisionProposal
) -> ScheduleRevisionProposalRead:
    """修正案1件をレスポンス形式へ変換する（`is_stale`は現在のschedule_itemの値との
    比較で都度算出する、D-59。生成API・判断API・`GET /goals/{goal_id}/schedule`の
    いずれからも呼ぶ、CLAUDE.md DRYの原則）。
    """
    item_ids = [item.schedule_item_id for item in proposal.items]
    current_items = {
        item.id: item
        for item in session.query(ScheduleItem).filter(ScheduleItem.id.in_(item_ids)).all()
    }
    return ScheduleRevisionProposalRead(
        id=proposal.id,
        goal_id=proposal.goal_id,
        trigger=proposal.trigger,
        record_date=proposal.record_date,
        summary=proposal.summary,
        status=proposal.status,
        items=[
            ScheduleRevisionProposalItemRead(
                id=item.id,
                schedule_item_id=item.schedule_item_id,
                kind=item.kind,
                before_planned_start_date=item.before_planned_start_date,
                before_planned_end_date=item.before_planned_end_date,
                before_status=item.before_status,
                proposed_planned_start_date=item.proposed_planned_start_date,
                proposed_planned_end_date=item.proposed_planned_end_date,
                reason=item.reason,
                decision=item.decision,
                applied_planned_start_date=item.applied_planned_start_date,
                applied_planned_end_date=item.applied_planned_end_date,
                reject_reason=item.reject_reason,
                is_stale=_is_stale(item, current_items.get(item.schedule_item_id)),
            )
            for item in proposal.items
        ],
    )


def _is_stale(item, current: ScheduleItem | None) -> bool:
    if current is None:  # pragma: no cover - ON DELETE CASCADEで本行自体も削除されるため到達しない
        return True
    return (
        item.before_planned_start_date != current.planned_start_date
        or item.before_planned_end_date != current.planned_end_date
        or item.before_status != current.status
    )


@router.post(
    "/goals/{goal_id}/schedule/revision-proposals", response_model=ScheduleRevisionGenerateResult
)
def generate_revision_proposal(
    goal_id: int,
    payload: ScheduleRevisionGenerateRequest,
    session: Session = Depends(get_db),
) -> ScheduleRevisionGenerateResult:
    goal = goal_service.get_goal(session, goal_id)
    today = goal_service.resolve_today(session)
    proposal = schedule_revision_service.generate_proposal(
        session, goal, trigger=payload.trigger, record_date=payload.record_date, today=today
    )
    session.commit()
    return ScheduleRevisionGenerateResult(
        proposal=serialize_proposal(session, proposal) if proposal is not None else None
    )


@router.post(
    "/goals/{goal_id}/schedule/revision-proposals/{proposal_id}/decisions",
    response_model=ScheduleRevisionDecisionsResponse,
)
def decide_revision_proposal(
    goal_id: int,
    proposal_id: int,
    payload: ScheduleRevisionDecisionsRequest,
    session: Session = Depends(get_db),
) -> ScheduleRevisionDecisionsResponse:
    goal = goal_service.get_goal(session, goal_id)
    proposal = schedule_revision_service.get_proposal_or_raise(session, proposal_id)
    today = goal_service.resolve_today(session)
    outcomes = schedule_revision_service.decide(session, goal, proposal, payload.decisions, today)
    session.commit()
    return ScheduleRevisionDecisionsResponse(
        proposal=serialize_proposal(session, proposal),
        outcomes=[
            ScheduleRevisionDecisionOutcome(
                proposal_item_id=outcome.proposal_item_id,
                applied=outcome.applied,
                blocked_reason=outcome.blocked_reason,
            )
            for outcome in outcomes
        ],
    )
