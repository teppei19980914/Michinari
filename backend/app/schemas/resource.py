"""リソーススロット・曜日別既定値・配分状況のスキーマ（データ構造編5.2・6.2、仕様書6.3）。

ResourceSlotRead の weekdays・duration_hours は保存しない派生値のため、
MaterialRead と同様にAPI層が明示的に組み立てる（from_attributesは使わない）。
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.constants.enums import Environment


class ResourceSlotCreate(BaseModel):
    name: str = Field(min_length=1)
    start_time: dt.time
    end_time: dt.time
    environment: Environment
    weekdays: list[int] = Field(min_length=1)


class ResourceSlotUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    start_time: dt.time | None = None
    end_time: dt.time | None = None
    environment: Environment | None = None
    weekdays: list[int] | None = Field(default=None, min_length=1)
    is_active: bool | None = None


class ResourceSlotRead(BaseModel):
    id: int
    name: str
    start_time: dt.time
    end_time: dt.time
    environment: Environment
    is_active: bool
    display_order: int
    weekdays: list[int]
    duration_hours: float


class GoalAllocationRead(BaseModel):
    goal_id: int
    goal_name: str
    resource_ratio: float


class AllocationStatusRead(BaseModel):
    total_hours_by_weekday: dict[int, float]
    total_hours_by_environment: dict[str, float]
    goal_allocations: list[GoalAllocationRead]
    unallocated_ratio: float


class DayBoundaryHourRead(BaseModel):
    day_boundary_hour: int


class DayBoundaryHourUpdate(BaseModel):
    day_boundary_hour: int = Field(ge=0, le=11)


class HolidayTreatAsBufferRead(BaseModel):
    treat_as_buffer: bool


class HolidayTreatAsBufferUpdate(BaseModel):
    treat_as_buffer: bool
