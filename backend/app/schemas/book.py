"""書籍のリクエスト/レスポンススキーマ（データ構造編5.3、仕様書6.2）。

BookRead の remaining_days・last_reading_date・current_streak・current_page・
progress_rate はDBに保存しない派生値（CLAUDE.md）であるため、ORMからの自動変換
(from_attributes)は使わず、API層がbook_serviceで算出した値を明示的に渡して構築する
（schemas/material.pyのMaterialReadと同じ方針）。
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


class BookCreate(BaseModel):
    title: str = Field(min_length=1)
    author: str | None = None
    total_pages: int | None = Field(default=None, ge=1)
    start_date: dt.date
    due_date: dt.date


class BookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    author: str | None = None
    total_pages: int | None = Field(default=None, ge=1)
    start_date: dt.date | None = None
    due_date: dt.date | None = None


class BookRead(BaseModel):
    id: int
    goal_id: int
    title: str
    author: str | None
    total_pages: int | None
    start_date: dt.date
    due_date: dt.date
    remaining_days: int
    last_reading_date: dt.date | None
    current_streak: int
    current_page: int | None
    progress_rate: float | None
