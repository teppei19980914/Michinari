"""リソーススロット・曜日別既定値・配分状況のAPI（データ構造編6.2、実装フェーズ分割計画書Phase3）。"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.constants.enums import DayType
from app.database import get_db
from app.models.resource import ResourceSlot
from app.schemas.resource import (
    AllocationStatusRead,
    DayBoundaryHourRead,
    DayBoundaryHourUpdate,
    GoalAllocationRead,
    ResourceSlotCreate,
    ResourceSlotRead,
    ResourceSlotUpdate,
)
from app.services import resource_service, slot_service

router = APIRouter(tags=["resources"])


def _serialize_slot(slot: ResourceSlot) -> ResourceSlotRead:
    return ResourceSlotRead(
        id=slot.id,
        name=slot.name,
        start_time=slot.start_time,
        end_time=slot.end_time,
        environment=slot.environment,
        is_active=slot.is_active,
        display_order=slot.display_order,
        weekdays=sorted(w.weekday for w in slot.weekdays),
        duration_hours=slot_service.slot_duration_hours(slot),
    )


@router.get("/resources/slots", response_model=list[ResourceSlotRead])
def list_slots(session: Session = Depends(get_db)) -> list[ResourceSlotRead]:
    return [_serialize_slot(s) for s in resource_service.list_slots(session)]


@router.post(
    "/resources/slots", response_model=ResourceSlotRead, status_code=status.HTTP_201_CREATED
)
def create_slot(
    payload: ResourceSlotCreate, session: Session = Depends(get_db)
) -> ResourceSlotRead:
    slot = resource_service.create_slot(session, **payload.model_dump())
    session.commit()
    return _serialize_slot(slot)


@router.patch("/resources/slots/{slot_id}", response_model=ResourceSlotRead)
def update_slot(
    slot_id: int, payload: ResourceSlotUpdate, session: Session = Depends(get_db)
) -> ResourceSlotRead:
    slot = resource_service.get_slot(session, slot_id)
    resource_service.update_slot(session, slot, **payload.model_dump(exclude_unset=True))
    session.commit()
    return _serialize_slot(slot)


@router.delete("/resources/slots/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_slot(slot_id: int, session: Session = Depends(get_db)) -> None:
    slot = resource_service.get_slot(session, slot_id)
    resource_service.delete_slot(session, slot)
    session.commit()


@router.get("/resources/allocation", response_model=AllocationStatusRead)
def get_allocation(session: Session = Depends(get_db)) -> AllocationStatusRead:
    allocation = resource_service.get_allocation_status(session)
    return AllocationStatusRead(
        total_hours_by_weekday=allocation.total_hours_by_weekday,
        total_hours_by_environment=allocation.total_hours_by_environment,
        goal_allocations=[
            GoalAllocationRead(
                goal_id=g.goal_id, goal_name=g.goal_name, resource_ratio=g.resource_ratio
            )
            for g in allocation.goal_allocations
        ],
        unallocated_ratio=allocation.unallocated_ratio,
    )


@router.get("/resources/day-type-defaults", response_model=dict[int, DayType])
def get_day_type_defaults(session: Session = Depends(get_db)) -> dict[int, DayType]:
    return resource_service.get_day_type_defaults(session)


@router.put("/resources/day-type-defaults", response_model=dict[int, DayType])
def update_day_type_defaults(
    payload: dict[int, DayType], session: Session = Depends(get_db)
) -> dict[int, DayType]:
    updated = resource_service.update_day_type_defaults(session, payload)
    session.commit()
    return updated


@router.get("/resources/day-boundary-hour", response_model=DayBoundaryHourRead)
def get_day_boundary_hour(session: Session = Depends(get_db)) -> DayBoundaryHourRead:
    return DayBoundaryHourRead(day_boundary_hour=resource_service.get_day_boundary_hour(session))


@router.put("/resources/day-boundary-hour", response_model=DayBoundaryHourRead)
def update_day_boundary_hour(
    payload: DayBoundaryHourUpdate, session: Session = Depends(get_db)
) -> DayBoundaryHourRead:
    hour = resource_service.update_day_boundary_hour(session, payload.day_boundary_hour)
    session.commit()
    return DayBoundaryHourRead(day_boundary_hour=hour)
