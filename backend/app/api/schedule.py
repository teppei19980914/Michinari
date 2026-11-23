"""スケジュール・ガントチャート機能のAPI
（開発Todo_スケジュール・ガントチャート_v1.1 第8章、単位2）。

API層はドメイン例外をHTTPへ変換するのみ（CODING_RULES.md「サービス層でのHTTP例外の
送出禁止」）。検証・差分適用の実体は`schedule_service`が担う。
"""

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.schedule import (
    ScheduleCellRead,
    ScheduleColumnRead,
    ScheduleItemRead,
    ScheduleRead,
    ScheduleSaveRequest,
    ScheduleViewSettingRead,
    ScheduleViewSettingUpdate,
)
from app.services import goal_service, schedule_service
from app.services.schedule_service import ScheduleView

router = APIRouter(tags=["schedule"])


def _serialize_view(view: ScheduleView, today: dt.date) -> ScheduleRead:
    return ScheduleRead(
        revision=view.revision,
        frozen_row_count=view.frozen_row_count,
        frozen_column_count=view.frozen_column_count,
        today=today,
        columns=[
            ScheduleColumnRead(id=column.id, name=column.name, display_order=column.display_order)
            for column in view.columns
        ],
        items=[
            ScheduleItemRead(
                id=item.id,
                title=item.title,
                description=item.description,
                planned_start_date=item.planned_start_date,
                planned_end_date=item.planned_end_date,
                status=item.status,
                actual_start_date=item.actual_start_date,
                actual_end_date=item.actual_end_date,
                display_order=item.display_order,
                cells=[
                    ScheduleCellRead(column_id=column_id, value=value)
                    for column_id, value in view.cells_by_item_id[item.id].items()
                ],
            )
            for item in view.items
        ],
    )


@router.get("/goals/{goal_id}/schedule", response_model=ScheduleRead)
def get_schedule(goal_id: int, session: Session = Depends(get_db)) -> ScheduleRead:
    goal = goal_service.get_goal(session, goal_id)
    today = goal_service.resolve_today(session)
    view = schedule_service.get_schedule_view(session, goal)
    return _serialize_view(view, today)


@router.put("/goals/{goal_id}/schedule", response_model=ScheduleRead)
def save_schedule(
    goal_id: int, payload: ScheduleSaveRequest, session: Session = Depends(get_db)
) -> ScheduleRead:
    goal = goal_service.get_goal(session, goal_id)
    today = goal_service.resolve_today(session)
    view = schedule_service.save_schedule(session, goal, payload, today)
    session.commit()
    return _serialize_view(view, today)


@router.put("/goals/{goal_id}/schedule/view-setting", response_model=ScheduleViewSettingRead)
def update_schedule_view_setting(
    goal_id: int, payload: ScheduleViewSettingUpdate, session: Session = Depends(get_db)
) -> ScheduleViewSettingRead:
    goal = goal_service.get_goal(session, goal_id)
    schedule = schedule_service.update_view_setting(
        session, goal, payload.frozen_row_count, payload.frozen_column_count
    )
    session.commit()
    return ScheduleViewSettingRead(
        frozen_row_count=schedule.frozen_row_count,
        frozen_column_count=schedule.frozen_column_count,
    )
