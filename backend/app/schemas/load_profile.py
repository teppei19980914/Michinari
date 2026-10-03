"""負荷プロファイルのリクエスト/レスポンススキーマ（データ構造編5.3、仕様書6.2）。"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class LoadProfileCreate(BaseModel):
    date_from: dt.date
    date_to: dt.date
    coefficient: float = Field(gt=0)
    note: str | None = None


class LoadProfileUpdate(BaseModel):
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    coefficient: float | None = Field(default=None, gt=0)
    note: str | None = None


class LoadProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    goal_id: int
    date_from: dt.date
    date_to: dt.date
    coefficient: float
    note: str | None
