"""案件情報のリクエスト/レスポンススキーマ（データ構造編5.3、仕様書6.2）。

WorkAssignmentRead の elapsed_days・last_work_date・current_streak・
has_recent_monthly_report はDBに保存しない派生値（CLAUDE.md）であるため、ORMからの
自動変換(from_attributes)は使わず、API層がwork_serviceで算出した値を明示的に渡して
構築する（schemas/book.pyのBookReadと同じ方針）。bookと異なりdue_dateに相当する列を
持たないため、remaining_daysではなくelapsed_daysを返す（データ構造編5.3参照）。
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from app.constants.enums import WorkEvaluationRole, WorkMemberGender


class WorkAssignmentCreate(BaseModel):
    client_name: str | None = None
    expected_content: str = Field(min_length=1)
    start_date: dt.date
    role: WorkEvaluationRole | None = None


class WorkAssignmentUpdate(BaseModel):
    client_name: str | None = None
    expected_content: str | None = Field(default=None, min_length=1)
    start_date: dt.date | None = None
    role: WorkEvaluationRole | None = None


class WorkAssignmentRead(BaseModel):
    id: int
    goal_id: int
    client_name: str | None
    expected_content: str
    start_date: dt.date
    role: WorkEvaluationRole | None
    elapsed_days: int
    last_work_date: dt.date | None
    current_streak: int
    has_recent_monthly_report: bool
    members: list[WorkMemberRead]


class WorkMemberCreate(BaseModel):
    name: str = Field(min_length=1)
    gender: WorkMemberGender | None = None
    characteristics: str | None = None
    #: 本人確認済みボタンのクリックを表す（要件定義書6.11）。characteristicsを非空で
    #: 保存する際は必ずTrueでなければならない（サービス層work_member_serviceで強制、
    #: フロントのチェックボックス無効化はUXの補助に過ぎない）。
    consent_confirmed: bool = False


class WorkMemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    gender: WorkMemberGender | None = None
    characteristics: str | None = None
    consent_confirmed: bool = False


class WorkMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_assignment_id: int
    name: str
    gender: WorkMemberGender | None
    characteristics: str | None
    consent_confirmed_at: dt.datetime | None
    is_active: bool


WorkAssignmentRead.model_rebuild()
