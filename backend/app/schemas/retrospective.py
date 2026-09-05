"""総括レポート・月次報告・半期評価のリクエスト/レスポンススキーマ
（データ構造編5.4、仕様書6.10、実装フェーズ分割計画書Phase22）。"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from app.constants.enums import RetrospectivePeriodType


class RetrospectiveGenerateRequest(BaseModel):
    anonymize: bool = False


class RetrospectiveRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    goal_id: int
    body: str
    is_anonymized: bool
    generated_at: dt.datetime


class WorkReportGenerateRequest(BaseModel):
    period: str | None = None
    anonymize: bool = False


class WorkReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    goal_id: int
    period_type: RetrospectivePeriodType
    period_key: str
    body: str
    target_goal_text: str | None
    business_summary: str | None
    achievement_score: int | None
    achievement_reflection: str | None
    next_goal_text: str | None
    report_notes: str | None
    is_anonymized: bool
    generated_at: dt.datetime
    edited_at: dt.datetime | None


class MonthlyReportUpdateRequest(BaseModel):
    target_goal_text: str | None = None
    business_summary: str | None = None
    achievement_score: int | None = Field(default=None, ge=1, le=5)
    achievement_reflection: str | None = None
    next_goal_text: str | None = None
    report_notes: str | None = None


class SemiannualReviewUpdateRequest(BaseModel):
    target_goal_text: str | None = None
    business_summary: str | None = None
    achievement_score: int | None = Field(default=None, ge=1, le=5)
    achievement_reflection: str | None = None
    next_goal_text: str | None = None
