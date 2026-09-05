"""ダッシュボードのレスポンススキーマ（仕様書6.1 SC-01、実装フェーズ分割計画書Phase6）。

ここで返す値はいずれもDBに保存しない派生値であり、Phase2で実装・テスト済みの
metrics_service/threshold_service/speed_service等を組み合わせて都度算出する
（CLAUDE.md「日次ノルマ・残量・現在周回の保存」禁止と同じ原則）。
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from app.constants.enums import DayType, GoalCategory, RecordState
from app.schemas.book import BookRead
from app.schemas.work import WorkAssignmentRead


class MaterialSpeedRead(BaseModel):
    material_id: int
    material_name: str
    unit_label: str
    speed: float | None


class GoalCardRead(BaseModel):
    """目標カード（仕様書6.1「進行中の各目標について、全体進捗率、残日数、
    完了予測日との乖離を表示」）。

    category=READINGの場合、progress_rate・remaining_daysは書籍の派生値（ページ進捗・
    読了目標日までの残日数）で上書きし、forecast_deviation_days・has_warning・
    has_forced_replanは対象外（常にNone/false）とする（要件定義書R-71、Phase17）。
    bookには読書進捗の全体（直近記録日・連続記録日数を含む）を格納する。

    category=WORKの場合、progress_rate・remaining_days・forecast_deviation_days・
    has_warning・has_forced_replanはいずれも対象外（materials・exam_subjectsを
    持たないため元々Noneのまま。要件定義書R-74）。work_assignmentに仕事進捗の全体
    （経過日数・直近記録日・連続記録日数・直近の月次報告有無を含む）を格納する
    （実装フェーズ分割計画書Phase23、読書のDSH-06相当のDSH-07）。
    """

    goal_id: int
    goal_name: str
    category: GoalCategory
    progress_rate: float | None
    remaining_days: int | None
    forecast_deviation_days: float | None
    has_warning: bool
    has_forced_replan: bool
    book: BookRead | None = None
    work_assignment: WorkAssignmentRead | None = None


class GoalStatsRead(BaseModel):
    """統計サマリ（仕様書6.1「連続報告日数、直近30日の報告率、バッファ消費率、実効速度」）。

    連続報告日数・報告率・バッファ消費率はgoal.start_dateを起点に算出するため、
    ACTIVEな目標ごとに1件を返す。
    """

    goal_id: int
    goal_name: str
    consecutive_report_days: int
    recent_report_rate: float
    buffer_usage_rate: float | None
    material_speeds: list[MaterialSpeedRead]


class TodayQuotaEntryRead(BaseModel):
    """本日のノルマ（仕様書6.1「進行中の全教材について、目標分量・目標時間・
    使用予定スロット・現在周回を一覧」）。使用予定スロットはavailable_slot_namesを参照する。"""

    material_id: int
    material_name: str
    current_cycle: int
    planned_cycles: int
    daily_quota: float
    unit_label: str
    target_minutes: float | None
    goal_id: int
    goal_name: str


class DashboardRead(BaseModel):
    """データ構造編6.2「GET /dashboard: ダッシュボードに必要な全情報を一括取得」。

    初期表示2秒以内の性能要件のため、複数エンドポイントへ個別に取得しに行かず本レスポンス
    1回で完結させる（今日の一言のみ例外で GET /daily-message へ分離、同6.2に明記）。
    論理的な本日・記録状態は GET /records/today と同じ値だが、ダッシュボード画面が
    往復を増やさず取得できるようここにも含める（/records/todayは他画面からも汎用的に
    参照されるため存続する）。
    """

    logical_date: dt.date
    record_state: RecordState | None
    today_day_type: DayType
    report_rate_window_days: int
    goal_cards: list[GoalCardRead]
    goal_stats: list[GoalStatsRead]
    today_quota: list[TodayQuotaEntryRead]
    available_slot_names: list[str]
