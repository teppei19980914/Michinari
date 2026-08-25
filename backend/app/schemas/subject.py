"""試験科目のリクエスト/レスポンススキーマ（データ構造編5.3、仕様書6.2）。"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from app.constants.enums import ExamDateType, ExamResultType


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1)
    exam_date_type: ExamDateType
    exam_date_from: dt.date | None = None
    exam_date_to: dt.date | None = None
    exam_date_fixed: dt.date | None = None
    passing_score: float | None = Field(default=None, ge=0, le=100)


class SubjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    exam_date_type: ExamDateType | None = None
    exam_date_from: dt.date | None = None
    exam_date_to: dt.date | None = None
    exam_date_fixed: dt.date | None = None
    passing_score: float | None = Field(default=None, ge=0, le=100)


class SubjectFixDateRequest(BaseModel):
    exam_date_fixed: dt.date


class SubjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    goal_id: int
    name: str
    exam_date_type: ExamDateType
    exam_date_from: dt.date | None
    exam_date_to: dt.date | None
    exam_date_fixed: dt.date | None
    passing_score: float | None
    display_order: int
    exam_result: ExamResultRead | None = None


class ExamResultCreate(BaseModel):
    taken_date: dt.date
    result: ExamResultType
    score: float | None = None
    evaluation: str | None = None
    note: str | None = None


class ExamResultUpdate(BaseModel):
    taken_date: dt.date | None = None
    result: ExamResultType | None = None
    score: float | None = None
    evaluation: str | None = None
    note: str | None = None


class ExamResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_id: int
    taken_date: dt.date
    result: ExamResultType
    score: float | None
    evaluation: str | None
    note: str | None
