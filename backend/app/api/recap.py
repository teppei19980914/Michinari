"""振り返り（テーマ累積）のAPI（仕様書6.1.3）。

テーマ一覧は目標配下、テーマの詳細・改名・統合はテーマ単位のパスに置く。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.goal import Goal
from app.schemas.recap import (
    RecapThemeDetailRead,
    RecapThemeEntryRead,
    RecapThemeMerge,
    RecapThemeRename,
    RecapThemeSummaryRead,
)
from app.services import goal_service, recap_generation_service, recap_service

router = APIRouter(tags=["recap"])


def _detail(session: Session, theme) -> RecapThemeDetailRead:
    return RecapThemeDetailRead(
        id=theme.id,
        name=theme.name,
        body=theme.body,
        updated_at=theme.updated_at,
        entries=[
            RecapThemeEntryRead(source_kind=e.source_kind, record_date=e.record_date, text=e.text)
            for e in recap_service.theme_entries(session, theme)
        ],
    )


@router.get("/goals/{goal_id}/recap-themes", response_model=list[RecapThemeSummaryRead])
def list_recap_themes(goal_id: int, session: Session = Depends(get_db)):
    goal = goal_service.get_goal(session, goal_id)
    return [
        RecapThemeSummaryRead(
            id=t.id, name=t.name, entry_count=t.entry_count, updated_at=t.updated_at
        )
        for t in recap_service.list_themes(session, goal)
    ]


@router.get("/recap-themes/{theme_id}", response_model=RecapThemeDetailRead)
def get_recap_theme(theme_id: int, session: Session = Depends(get_db)):
    theme = recap_service.get_theme(session, theme_id)
    return _detail(session, theme)


@router.patch("/recap-themes/{theme_id}", response_model=RecapThemeDetailRead)
def rename_recap_theme(
    theme_id: int, payload: RecapThemeRename, session: Session = Depends(get_db)
):
    theme = recap_service.get_theme(session, theme_id)
    recap_service.rename_theme(session, theme, payload.name)
    session.commit()
    return _detail(session, theme)


@router.post("/recap-themes/{theme_id}/merge", response_model=RecapThemeDetailRead)
def merge_recap_theme(theme_id: int, payload: RecapThemeMerge, session: Session = Depends(get_db)):
    source = recap_service.get_theme(session, theme_id)
    target = recap_service.get_theme(session, payload.target_theme_id)
    merged = recap_service.merge_themes(session, source, target)
    session.commit()
    return _detail(session, merged)


@router.post("/recap-themes/{theme_id}/rebuild", response_model=RecapThemeDetailRead)
def rebuild_recap_theme(theme_id: int, session: Session = Depends(get_db)):
    theme = recap_service.get_theme(session, theme_id)
    goal = session.get(Goal, theme.goal_id)
    recap_generation_service.rebuild_theme(session, goal, theme)
    session.commit()
    return _detail(session, theme)
