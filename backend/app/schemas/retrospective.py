"""総括レポートのリクエスト/レスポンススキーマ（データ構造編5.4、仕様書6.10）。"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class RetrospectiveGenerateRequest(BaseModel):
    anonymize: bool = False


class RetrospectiveRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    goal_id: int
    body: str
    is_anonymized: bool
    generated_at: dt.datetime
