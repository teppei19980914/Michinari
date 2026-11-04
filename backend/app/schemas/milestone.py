"""節目のお祝い（開発Todo_節目のお祝い_v1.0）のリクエスト/レスポンススキーマ。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.constants.enums import MilestoneType


class MilestoneAchievementRead(BaseModel):
    id: int
    goal_id: int
    milestone_type: MilestoneType
    milestone_key: str
    achieved_at: datetime
    celebrated_at: datetime | None
