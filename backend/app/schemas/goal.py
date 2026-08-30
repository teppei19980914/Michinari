"""目標のリクエスト/レスポンススキーマ（データ構造編5.3、仕様書6.2）。"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from app.constants.enums import BaselineReason, GoalStatus
from app.schemas.load_profile import LoadProfileRead
from app.schemas.material import MaterialRead
from app.schemas.subject import SubjectRead


class GoalCreate(BaseModel):
    name: str = Field(min_length=1)
    start_date: dt.date
    memo: str | None = None


class GoalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    start_date: dt.date | None = None
    memo: str | None = None
    resource_ratio: float | None = Field(default=None, ge=0, le=1)


class GoalCloseRequest(BaseModel):
    confirm_without_result: bool = False


class GoalDeleteArchivedRequest(BaseModel):
    """アーカイブ済み目標の完全削除リクエスト（仕様書7.1.1、MD-08）。

    画面上のチェックボックスは既定ONのため、cascade_study_logsの既定値もTrueとする。
    """

    cascade_study_logs: bool = True


class GoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    start_date: dt.date
    status: GoalStatus
    resource_ratio: float
    memo: str | None
    activated_at: dt.datetime | None
    closed_at: dt.datetime | None
    archived_at: dt.datetime | None


class GoalDetailRead(GoalRead):
    exam_subjects: list[SubjectRead]
    materials: list[MaterialRead]
    load_profiles: list[LoadProfileRead]


class PlanBaselineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    material_id: int
    effective_from: dt.date
    baseline_daily_quota: float
    remaining_at_baseline: float
    plan_days_at_baseline: int
    planned_cycles_at_baseline: int
    reason: BaselineReason
