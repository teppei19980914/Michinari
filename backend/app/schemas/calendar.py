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


class HolidayRead(BaseModel):
    holiday_date: dt.date
    name: str


class HolidayListRead(BaseModel):
    """`GET /holidays`の応答（第8章、D-46「収録済みの年の範囲」表示）。

    `year_from`・`year_to`は`holiday`テーブル全体の収録範囲であり、`holidays`の
    フィルタ範囲とは独立する（期間を省略した呼び出しでも収録範囲だけ取得できる）。
    """

    holidays: list[HolidayRead]
    year_from: int | None
    year_to: int | None
