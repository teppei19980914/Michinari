"""AI評価レポートのリクエスト/レスポンススキーマ（要件定義書6.11）。

WorkEvaluationReportRead の member_name はDBに保存しない派生値（結合先メンバーの
現在の名前）であるため、schemas/work.pyのWorkAssignmentReadと同じ方針でORMの
自動変換(from_attributes)は使わず、API層が明示的に組み立てる。
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


class WorkEvaluationReportGenerateRequest(BaseModel):
    member_id: int
    considerations: str = Field(min_length=1)


class WorkEvaluationReportUpdate(BaseModel):
    body: str = Field(min_length=1)


class WorkEvaluationReportRead(BaseModel):
    id: int
    work_assignment_id: int
    member_id: int
    member_name: str
    considerations: str
    body: str
    generated_at: dt.datetime
    edited_at: dt.datetime | None
