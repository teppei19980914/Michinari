"""分析画面のレスポンススキーマ（仕様書6.8 SC-09、実装フェーズ分割計画書Phase9）。

ここで返す値はいずれもDBに保存しない派生値であり、Phase2〜5で実装・テスト済みの
cycle_service/metrics_service/speed_service/analytics_serviceを組み合わせて都度算出する
（CLAUDE.md「日次ノルマ・残量・現在周回の保存」禁止と同じ原則）。
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from app.constants.enums import Granularity


class QualityTrendPointRead(BaseModel):
    """品質推移グラフの1点（14.2の集約規則で平均化済み）。"""

    period_start: dt.date
    value: float
    sample_count: int


class QualityTrendSeriesRead(BaseModel):
    """周回別に分離された品質指標の系列（14.3）。"""

    cycle_number: int
    points: list[QualityTrendPointRead]


class MaterialQualityTrendRead(BaseModel):
    material_id: int
    material_name: str
    passing_score: float | None
    series: list[QualityTrendSeriesRead]


class QualityAnalyticsRead(BaseModel):
    """GET /analytics/quality（仕様書6.8「品質推移」タブ、ANL-01〜03）。"""

    granularity: Granularity
    materials: list[MaterialQualityTrendRead]


class ProgressPointRead(BaseModel):
    """累積完了量の1点。実績系列・計画線系列の双方で共通の形状を使う。"""

    record_date: dt.date
    cumulative_completed: float


class CycleBoundaryRead(BaseModel):
    cycle_number: int
    record_date: dt.date


class MaterialProgressTrendRead(BaseModel):
    material_id: int
    material_name: str
    unit_label: str
    total_work: float
    actual_points: list[ProgressPointRead]
    plan_points: list[ProgressPointRead]
    cycle_boundaries: list[CycleBoundaryRead]


class ProgressAnalyticsRead(BaseModel):
    """GET /analytics/progress（仕様書6.8「進捗」タブ）。"""

    materials: list[MaterialProgressTrendRead]


class ForecastEntryRead(BaseModel):
    material_id: int
    material_name: str
    unit_label: str
    due_date: dt.date
    forecast_date: dt.date | None
    overrun_days: int | None
    unavailable_reason: str | None


class ForecastAnalyticsRead(BaseModel):
    """GET /analytics/forecast（仕様書6.8「完了予測」タブ、ANL-05）。"""

    materials: list[ForecastEntryRead]


class SpeedTrendPointRead(BaseModel):
    record_date: dt.date
    speed: float


class SpeedTrendSeriesRead(BaseModel):
    cycle_number: int
    points: list[SpeedTrendPointRead]


class MaterialSpeedTrendRead(BaseModel):
    material_id: int
    material_name: str
    unit_label: str
    series: list[SpeedTrendSeriesRead]


class SpeedAnalyticsRead(BaseModel):
    """GET /analytics/speed（仕様書6.8「実効速度」タブ、ANL-06）。"""

    materials: list[MaterialSpeedTrendRead]


class GanttEntryRead(BaseModel):
    material_id: int
    material_name: str
    start_date: dt.date
    due_date: dt.date
    progress_rate: float
    current_cycle: int
    planned_cycles: int


class GanttAnalyticsRead(BaseModel):
    """GET /analytics/gantt（仕様書6.8「ガントチャート」タブ、ANL-04）。"""

    today: dt.date
    materials: list[GanttEntryRead]


class GrowthDescriptionEntryRead(BaseModel):
    """GET /analytics/growth-descriptions（仕様書6.8「成長記述」タブ、ANL-07）。

    データ構造編8章のエンドポイント一覧に明記のないPhase9実装判断による追加。
    根拠はanalytics_service.list_growth_descriptionsのdocstringを参照。

    message_id・goal_id はPhase26で追加。goal_id が null のエントリは目標単位分離より
    前のレガシーメッセージ（未割り当て）であり、PATCH /analytics/growth-descriptions/{id}
    で利用者が目標を割り当てられる。
    """

    message_id: int
    record_date: dt.date
    content: str
    goal_id: int | None


class GrowthDescriptionAssignRequest(BaseModel):
    """PATCH /analytics/growth-descriptions/{message_id}（成長記述への目標の手動割り当て、
    Phase26）。"""

    goal_id: int


class ReadingLogEntryRead(BaseModel):
    """GET /analytics/reading-logs（仕様書6.8「読書記録」タブ、読書目標category=READING向け）。"""

    record_date: dt.date
    recall_body: str
    current_page: int | None


class WorkLogEntryRead(BaseModel):
    """GET /analytics/work-logs（仕様書6.8「業務記録」タブ、仕事目標category=WORK向け）。"""

    record_date: dt.date
    body: str
