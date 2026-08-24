"""教材のリクエスト/レスポンススキーマ（データ構造編5.3、仕様書6.2）。

MaterialRead の total_work・current_cycle・remaining・completed・progress_rate系は
DBに保存しない派生値（CLAUDE.md）であるため、ORMからの自動変換(from_attributes)は使わず、
API層が cycle_service 等で算出した値を明示的に渡して構築する。
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.constants.enums import Environment, QualityMetricType


class MaterialCreate(BaseModel):
    name: str = Field(min_length=1)
    unit_label: str = Field(min_length=1)
    total_amount: float = Field(ge=0)
    planned_cycles: int = Field(default=1, ge=1)
    subject_ids: list[int] = Field(min_length=1)
    start_date: dt.date
    due_date: dt.date | None = None
    due_date_is_manual: bool = False
    required_block_minutes: int | None = Field(default=None, ge=1)
    required_environment: Environment = Environment.ANY
    quality_metric_type: QualityMetricType = QualityMetricType.NONE


class MaterialUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    unit_label: str | None = Field(default=None, min_length=1)
    total_amount: float | None = Field(default=None, ge=0)
    planned_cycles: int | None = Field(default=None, ge=1)
    subject_ids: list[int] | None = Field(default=None, min_length=1)
    start_date: dt.date | None = None
    due_date: dt.date | None = None
    due_date_is_manual: bool | None = None
    required_block_minutes: int | None = Field(default=None, ge=1)
    required_environment: Environment | None = None
    quality_metric_type: QualityMetricType | None = None


class MaterialRead(BaseModel):
    id: int
    goal_id: int
    name: str
    unit_label: str
    total_amount: float
    planned_cycles: int
    subject_ids: list[int]
    start_date: dt.date
    due_date: dt.date
    due_date_is_manual: bool
    required_block_minutes: int | None
    required_environment: Environment
    quality_metric_type: QualityMetricType
    is_active: bool
    display_order: int
    total_work: float
    current_cycle: int
    remaining: float
    completed: float
    progress_rate_in_cycle: float
    progress_rate: float


class MaterialCycleProgressRead(BaseModel):
    cycle_number: int
    completed_amount: float
    speed: float | None
    sample_count: int
    quality_average: float | None


class SlotCheckRead(BaseModel):
    sufficient: bool
