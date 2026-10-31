"""道のりマップのレスポンススキーマ（開発Todo_道のりマップ_v1.0.md §3.1 S-02）。

ここで返す値はいずれもDBに保存しない派生値であり、roadmap_serviceが都度算出する
（CLAUDE.md「日次ノルマ・残量・現在周回の保存」禁止と同じ原則）。文言（カテゴリ表示名等）は
返さず、フロント側がja.jsonで解決する（ゼロハードコーディング、CLAUDE.md）。
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from app.constants.enums import GoalCategory


class RoadmapPointRead(BaseModel):
    """道のり上の1点（比率は0.0〜1.0）。"""

    date: dt.date
    ratio: float


class RoadmapFootprintRead(BaseModel):
    """足跡の1件。"""

    date: dt.date
    has_input: bool


class GoalRoadmapRead(BaseModel):
    """目標の道のり（詳細版、資格=山、読書=地図上の道、仕事=足跡の積み上げ）。

    カテゴリにより一部フィールドは常に空配列／nullになる（開発Todo §0 U7・U8・U10・U17）：
    EXAM以外はreplan_marks・overrun_daysが空／null、buffer_datesは仕事目標のみ空
    （予備日は仕様書13.5のとおり資格試験・読書目標が対象）、EXAMはfootprint_datesが
    常に空、WORKはplanned_points・actual_pointsが常に空。
    """

    category: GoalCategory
    start_date: dt.date
    goal_date: dt.date
    today_date: dt.date
    progress_ratio: float
    is_achieved: bool
    planned_points: list[RoadmapPointRead]
    actual_points: list[RoadmapPointRead]
    footprint_dates: list[RoadmapFootprintRead]
    replan_marks: list[RoadmapPointRead]
    feedback_marks: list[dt.date]
    buffer_dates: list[dt.date]
    overrun_days: float | None
