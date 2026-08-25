"""ナレッジエクスポートのリクエスト/レスポンススキーマ（データ構造編7章、仕様書6.10 SC-13）。"""

from __future__ import annotations

from pydantic import BaseModel


class KnowledgeExportSelection(BaseModel):
    """出力項目選択（仕様書6.10の表と同じ既定値）。"""

    goal_overview: bool = True
    materials: bool = True
    summary: bool = True
    daily_records: bool = True
    quality_trend: bool = True
    replan_history: bool = True
    weekly_summaries: bool = True
    diary: bool = False
    ai_dialogue: bool = False
    exam_results: bool = True
    retrospective: bool = True


class KnowledgeExportRequest(KnowledgeExportSelection):
    anonymize: bool = False


class KnowledgeExportContentRead(BaseModel):
    """プレビュー・実行結果に共通の出力内容（Markdown・JSON両形式を同時に出力する、7.2）。"""

    data: dict
    markdown: str


class KnowledgeExportResultRead(KnowledgeExportContentRead):
    markdown_path: str
    json_path: str
