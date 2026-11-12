"""ふりかえりまとめ・共有カードのレスポンススキーマ（データ構造編6.API設計、
開発Todo「まとめと共有カード」v1.0、ロジック・プロンプト編28章）。

集計・AI一文のいずれも永続化しないため、永続モデルに対応するテーブルは無い
（§0 U4）。本文系フィールド（日記本文・AI対話履歴）は構造的に持たせない
（要件定義書R-157、匿名化対象情報を含めない要件への対応）。
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from app.constants.enums import MilestoneType


class SummaryCardMilestoneRead(BaseModel):
    milestone_type: MilestoneType
    milestone_key: str
    achieved_at: dt.datetime


class SummaryCardRoadmapRead(BaseModel):
    progress_ratio: float
    is_achieved: bool
    overrun_days: float | None


class SummaryCardRead(BaseModel):
    record_days: int
    longest_consecutive_days: int
    #: いちばん多く書いたテーマ（EXAM/READINGのみ。WORKは常にnull、§0 U7）。
    top_theme_name: str | None
    milestones: list[SummaryCardMilestoneRead]
    roadmap: SummaryCardRoadmapRead


class SummaryCardSentenceRead(BaseModel):
    sentence: str
