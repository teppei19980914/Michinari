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
    #: 連続時間。分（整数）が正準の単位で、時間は切り捨て済みの表示用の値（仕様書6.3）。
    duration_minutes: int
    duration_hours: float


class GoalAllocationRead(BaseModel):
    """スロット1件に対する、目標ごとの配分時間（仕様書6.3「各目標への配分状況」）。"""

    goal_id: int
    goal_name: str
    minutes: int


class SlotAllocationStatusRead(BaseModel):
    """スロット1件の配分状況。`unallocated_minutes` は超過時に負値となる（NT-09）。"""

    slot_id: int
    slot_name: str
    duration_minutes: int
    allocated_minutes: int
    unallocated_minutes: int
    is_over_capacity: bool
    goal_allocations: list[GoalAllocationRead]


class AllocationStatusRead(BaseModel):
    total_hours_by_weekday: dict[int, float]
    total_hours_by_environment: dict[str, float]
    slots: list[SlotAllocationStatusRead]


class SlotAllocationRead(BaseModel):
    """リソース配分タブ1行分（データ構造編6.2 GET /goals/{id}/slot-allocations）。"""

    slot_id: int
    slot_name: str
    environment: Environment
    weekdays: list[int]
    duration_minutes: int
    minutes: int
    #: 他のACTIVEな目標の配分合計。空き時間 = duration_minutes - others_minutes。
    others_minutes: int


class SlotAllocationInput(BaseModel):
    slot_id: int
    minutes: int = Field(ge=0)


class SlotAllocationUpdate(BaseModel):
    """スロット別配分の一括更新（PUT /goals/{id}/slot-allocations）。

    送信されなかったスロットは0分（配分なし）として扱う。
    """

    allocations: list[SlotAllocationInput] = Field(default_factory=list)


class DayBoundaryHourRead(BaseModel):
    day_boundary_hour: int


class DayBoundaryHourUpdate(BaseModel):
    day_boundary_hour: int = Field(ge=0, le=11)


class HolidayTreatAsBufferRead(BaseModel):
    treat_as_buffer: bool


class HolidayTreatAsBufferUpdate(BaseModel):
    treat_as_buffer: bool
