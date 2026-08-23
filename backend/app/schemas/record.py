"""日次記録のリクエスト/レスポンススキーマ（データ構造編5.4・6.2、仕様書6.4〜6.7・14章）。

品質指標（quality_value）は教材の quality_metric_type に応じて入力形式が異なる
（SUBJECTIVEは1〜5、それ以外は0〜100）ため、正規化はサービス層（record_service）で行う。
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from app.constants.enums import RecordState


class StudyLogInput(BaseModel):
    material_id: int
    minutes_spent: int | None = Field(default=None, ge=0)
    amount_completed: float = Field(ge=0)
    cycle_number: int | None = Field(default=None, ge=1)
    quality_value: float | None = None


class StudyLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    material_id: int
    minutes_spent: int | None
    amount_completed: float
    cycle_number: int
    quality_value: float | None


class CommentCreate(BaseModel):
    body: str = Field(min_length=1)


class CommentUpdate(BaseModel):
    body: str = Field(min_length=1)


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    body: str
    created_at: dt.datetime
    updated_at: dt.datetime


class DailyRecordRead(BaseModel):
    record_date: dt.date
    record_state: RecordState | None
    diary_body: str | None
    diary_learned: str | None
    reported_at: dt.datetime | None
    study_logs: list[StudyLogRead]
    comments: list[CommentRead]


class ProgressRegisterRequest(BaseModel):
    study_logs: list[StudyLogInput] = Field(min_length=1)


class FinalizeRequest(BaseModel):
    study_logs: list[StudyLogInput] = Field(default_factory=list)
    diary_body: str = ""
    diary_learned: str = ""


class TodayRead(BaseModel):
    logical_date: dt.date
    record_state: RecordState | None


class QuotaItemRead(BaseModel):
    material_id: int
    material_name: str
    current_cycle: int
    planned_cycles: int
    daily_quota: float
