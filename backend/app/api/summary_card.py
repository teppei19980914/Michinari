"""ふりかえりまとめ・共有カードのAPI（仕様書6.2 SC-03・6.10 SC-13、データ構造編6.API設計、
開発Todo「まとめと共有カード」v1.0）。"""

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.summary_card import (
    SummaryCardMilestoneRead,
    SummaryCardRead,
    SummaryCardRoadmapRead,
    SummaryCardSentenceRead,
)
from app.services import goal_service, summary_card_service

router = APIRouter(tags=["summary-card"])


def _serialize(aggregate: summary_card_service.SummaryCardAggregate) -> SummaryCardRead:
    return SummaryCardRead(
        record_days=aggregate.record_days,
        longest_consecutive_days=aggregate.longest_consecutive_days,
        top_theme_name=aggregate.top_theme_name,
        milestones=[
            SummaryCardMilestoneRead(
                milestone_type=achievement.milestone_type,
                milestone_key=achievement.milestone_key,
                achieved_at=achievement.achieved_at,
            )
            for achievement in aggregate.milestones
        ],
        roadmap=SummaryCardRoadmapRead(
            progress_ratio=aggregate.roadmap.progress_ratio,
            is_achieved=aggregate.roadmap.is_achieved,
            overrun_days=aggregate.roadmap.overrun_days,
        ),
    )


@router.get("/goals/{goal_id}/summary-card", response_model=SummaryCardRead)
def get_summary_card(
    goal_id: int,
    date_from: dt.date,
    date_to: dt.date,
    session: Session = Depends(get_db),
) -> SummaryCardRead:
    goal = goal_service.get_goal(session, goal_id)
    aggregate = summary_card_service.get_summary(
        session, goal, date_from=date_from, date_to=date_to
    )
    return _serialize(aggregate)


@router.post("/goals/{goal_id}/summary-card/sentence", response_model=SummaryCardSentenceRead)
def generate_summary_card_sentence(
    goal_id: int,
    date_from: dt.date,
    date_to: dt.date,
    session: Session = Depends(get_db),
) -> SummaryCardSentenceRead:
    goal = goal_service.get_goal(session, goal_id)
    sentence = summary_card_service.generate_sentence(
        session, goal, date_from=date_from, date_to=date_to
    )
    session.commit()
    return SummaryCardSentenceRead(sentence=sentence)
