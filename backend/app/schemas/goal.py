"""目標のリクエスト/レスポンススキーマ（データ構造編5.3、仕様書6.2）。"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from app.constants.enums import BaselineReason, GoalCategory, GoalStatus
from app.constants.goal_transitions import GoalOperation
from app.schemas.book import BookRead
from app.schemas.load_profile import LoadProfileRead
from app.schemas.material import MaterialRead
from app.schemas.subject import SubjectRead
from app.schemas.work import WorkAssignmentRead


class GoalCreate(BaseModel):
    category: GoalCategory = GoalCategory.EXAM
    name: str = Field(min_length=1)
    start_date: dt.date
    memo: str | None = None


class GoalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    start_date: dt.date | None = None
    memo: str | None = None


class GoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: GoalCategory
    name: str
    start_date: dt.date
    status: GoalStatus
    memo: str | None
    activated_at: dt.datetime | None
    closed_at: dt.datetime | None
    archived_at: dt.datetime | None
    #: 再開日（開発Todo 1-5）。開始日とは別に、再開のたびに更新する。
    resumed_at: dt.datetime | None
    #: 画面で実行できる操作（遷移表から算出。画面の操作ボタンはこれに従う）。
    available_operations: list[GoalOperation]
    #: UI-11（目標達成アイコン）の判定基準（仕様書v1.1 13.6）。goal_service.compute_is_achievedで
    #: 算出する（都度算出、CLAUDE.md 保存禁止に準拠しDBへは持たない）。
    is_achieved: bool


class GoalResumeRead(GoalRead):
    """再開の応答。warnings は警告コードの一覧（資格試験で学習量が大きく増えた場合など）。"""

    warnings: list[str] = []


class GoalDetailRead(GoalRead):
    exam_subjects: list[SubjectRead]
    materials: list[MaterialRead]
    load_profiles: list[LoadProfileRead]
    book: BookRead | None = None
    work_assignment: WorkAssignmentRead | None = None


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
