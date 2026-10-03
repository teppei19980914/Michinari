"""カレンダーのリクエスト/レスポンススキーマ（データ構造編5.2・6.2、技術選定書6章）。"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from app.constants.enums import DayType, RecordState


class CalendarDayRead(BaseModel):
    target_date: dt.date
    day_type: DayType
    record_state: RecordState | None


class DayTypeOverrideRequest(BaseModel):
    day_type: DayType
    note: str | None = None


class HolidayImportResultRead(BaseModel):
    imported_count: int
    year_from: int
    year_to: int
