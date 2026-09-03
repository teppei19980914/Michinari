"""アプリ設定・プロンプトテンプレートのリクエスト/レスポンススキーマ（データ構造編5.2、仕様書6.11）。

app_setting は単一のキーバリュー表だが、SC-11の表示分類（AI接続・閾値・プロンプト縮退・
表示・ログ）に合わせてネストしたスキーマへ組み替える。CLAUDE.md「ゼロハードコーディング」に
従い、値そのものはこのファイルへ書かず app_setting から読み書きする（既定値は init/seed_data.py）。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.constants.enums import AiPurpose


class AiConnectionSettingsRead(BaseModel):
    host: str
    client_id: str
    tenant_id: str
    api_base_url: str
    assistant_uid_daily_feedback: str
    assistant_uid_weekly_summary: str
    assistant_uid_daily_message: str
    assistant_uid_goal_retrospective: str
    assistant_uid_daily_feedback_reading: str
    assistant_uid_goal_retrospective_reading: str
    folder_prefix: str
    timeout_seconds: int
    min_interval_seconds: int


class AiConnectionSettingsUpdate(BaseModel):
    host: str | None = None
    client_id: str | None = None
    tenant_id: str | None = None
    api_base_url: str | None = None
    assistant_uid_daily_feedback: str | None = None
    assistant_uid_weekly_summary: str | None = None
    assistant_uid_daily_message: str | None = None
    assistant_uid_goal_retrospective: str | None = None
    assistant_uid_daily_feedback_reading: str | None = None
    assistant_uid_goal_retrospective_reading: str | None = None
    folder_prefix: str | None = Field(default=None, min_length=1)
    timeout_seconds: int | None = Field(default=None, ge=1)
    min_interval_seconds: int | None = Field(default=None, ge=0)


class ThresholdSettingsRead(BaseModel):
    warning_ratio: float
    replan_overrun_days: int


class ThresholdSettingsUpdate(BaseModel):
    warning_ratio: float | None = Field(default=None, gt=1.0)
    replan_overrun_days: int | None = Field(default=None, ge=1)


class PromptDegradationSettingsRead(BaseModel):
    max_prompt_chars: int
    summary_inject_weeks: int
    reading_recall_recent_days: int


class PromptDegradationSettingsUpdate(BaseModel):
    max_prompt_chars: int | None = Field(default=None, ge=1000)
    summary_inject_weeks: int | None = Field(default=None, ge=1)
    reading_recall_recent_days: int | None = Field(default=None, ge=1)


class DisplaySettingsRead(BaseModel):
    locale: str
    theme: str
    default_granularity: str


class DisplaySettingsUpdate(BaseModel):
    locale: str | None = None
    theme: str | None = None
    default_granularity: str | None = None


class LogSettingsRead(BaseModel):
    ai_enabled: bool
    retention_days: int


class LogSettingsUpdate(BaseModel):
    ai_enabled: bool | None = None
    retention_days: int | None = Field(default=None, ge=1)


class AppSettingsRead(BaseModel):
    ai_connection: AiConnectionSettingsRead
    threshold: ThresholdSettingsRead
    prompt_degradation: PromptDegradationSettingsRead
    display: DisplaySettingsRead
    log: LogSettingsRead


class AppSettingsUpdate(BaseModel):
    ai_connection: AiConnectionSettingsUpdate | None = None
    threshold: ThresholdSettingsUpdate | None = None
    prompt_degradation: PromptDegradationSettingsUpdate | None = None
    display: DisplaySettingsUpdate | None = None
    log: LogSettingsUpdate | None = None


class PromptTemplateRead(BaseModel):
    purpose: AiPurpose
    body: str
    is_customized: bool


class PromptTemplateUpdate(BaseModel):
    body: str = Field(min_length=1)
