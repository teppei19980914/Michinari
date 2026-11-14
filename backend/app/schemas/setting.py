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
    assistant_uid_weekly_summary_reading: str
    assistant_uid_daily_feedback_work: str
    assistant_uid_goal_retrospective_work_monthly: str
    assistant_uid_goal_retrospective_work_semiannual: str
    assistant_uid_weekly_summary_work: str
    assistant_uid_evaluation_report_work: str
    assistant_uid_help: str
    assistant_uid_goal_consultation: str
    #: ひとこと記録モード（開発Todo「ひとこと記録」v1.0 Q2）用の短文プロンプト専用アシスタント。
    assistant_uid_daily_feedback_brief: str
    assistant_uid_daily_feedback_reading_brief: str
    assistant_uid_daily_feedback_work_brief: str
    assistant_uid_summary_card: str
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
    assistant_uid_weekly_summary_reading: str | None = None
    assistant_uid_daily_feedback_work: str | None = None
    assistant_uid_goal_retrospective_work_monthly: str | None = None
    assistant_uid_goal_retrospective_work_semiannual: str | None = None
    assistant_uid_weekly_summary_work: str | None = None
    assistant_uid_evaluation_report_work: str | None = None
    assistant_uid_help: str | None = None
    assistant_uid_goal_consultation: str | None = None
    assistant_uid_daily_feedback_brief: str | None = None
    assistant_uid_daily_feedback_reading_brief: str | None = None
    assistant_uid_daily_feedback_work_brief: str | None = None
    assistant_uid_summary_card: str | None = None
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
    #: 観点提案の追加指示（S-4 4-3）を注入する確定済み記録件数の閾値。
    perspective_suggestion_min_records: int


class PromptDegradationSettingsUpdate(BaseModel):
    max_prompt_chars: int | None = Field(default=None, ge=1000)
    perspective_suggestion_min_records: int | None = Field(default=None, ge=0)


class DisplaySettingsRead(BaseModel):
    locale: str
    theme: str
    default_granularity: str
    accent_color: str
    font_scale: str


class DisplaySettingsUpdate(BaseModel):
    locale: str | None = None
    theme: str | None = None
    default_granularity: str | None = None
    accent_color: str | None = None
    font_scale: str | None = None


class DesktopSettingsRead(BaseModel):
    open_browser_on_startup: bool
    launch_at_login: bool
    notification_enabled: bool
    notification_time: str
    #: 設定画面には出さない内部状態（開発Todo リマインド導線 D3・D5）。
    reminder_onboarding_shown: bool
    autostart_banner_dismissed: bool


class DesktopSettingsUpdate(BaseModel):
    open_browser_on_startup: bool | None = None
    launch_at_login: bool | None = None
    notification_enabled: bool | None = None
    #: `HH:MM`（24時間表記）。形式の検証はサービス層
    #: （notification_service.parse_notification_time）が行い、ここでは長さだけを見る。
    #: 判定に使う正規表現を2箇所へ書かないため（CODING_RULES.md DRYの原則）。
    notification_time: str | None = Field(default=None, min_length=1)
    #: 設定画面には出さない内部状態（開発Todo リマインド導線 D3・D5）。
    reminder_onboarding_shown: bool | None = None
    autostart_banner_dismissed: bool | None = None


class LogSettingsRead(BaseModel):
    ai_enabled: bool
    retention_days: int


class LogSettingsUpdate(BaseModel):
    ai_enabled: bool | None = None
    retention_days: int | None = Field(default=None, ge=1)


#: 節目のお祝い（開発Todo_節目のお祝い_v1.0）の閾値一覧（カンマ区切りの正の整数）。
#: 構造的な検証（数字とカンマのみ）はここで行い、重複除去・昇順への正規化は
#: `settings_service._parse_threshold_list`が担う（CODING_RULES.md DRYの原則）。
_THRESHOLD_LIST_PATTERN = r"^\d+(,\d+)*$"


class MilestoneThresholdSettingsRead(BaseModel):
    consecutive_days_thresholds: str
    total_record_days_thresholds: str
    reading_total_pages_thresholds: str
    reading_completed_books_thresholds: str
    exam_overall_progress_thresholds: str
    work_record_count_thresholds: str


class MilestoneThresholdSettingsUpdate(BaseModel):
    consecutive_days_thresholds: str | None = Field(default=None, pattern=_THRESHOLD_LIST_PATTERN)
    total_record_days_thresholds: str | None = Field(default=None, pattern=_THRESHOLD_LIST_PATTERN)
    reading_total_pages_thresholds: str | None = Field(
        default=None, pattern=_THRESHOLD_LIST_PATTERN
    )
    reading_completed_books_thresholds: str | None = Field(
        default=None, pattern=_THRESHOLD_LIST_PATTERN
    )
    exam_overall_progress_thresholds: str | None = Field(
        default=None, pattern=_THRESHOLD_LIST_PATTERN
    )
    work_record_count_thresholds: str | None = Field(default=None, pattern=_THRESHOLD_LIST_PATTERN)


#: 1年前の今日（開発Todo_1年前の今日_v1.0）の候補（カンマ区切りの正の整数、何か月前か）。
#: 検証方針はmilestone threshold（直上）と同じ：構造的な検証（数字とカンマのみ）はここで
#: 行い、重複除去・昇順への正規化は`settings_service._parse_threshold_list`が担う。
class OnThisDaySettingsRead(BaseModel):
    enabled: bool
    candidate_months_ago: str
    show_probability: float
    body_preview_chars: int


class OnThisDaySettingsUpdate(BaseModel):
    enabled: bool | None = None
    candidate_months_ago: str | None = Field(default=None, pattern=_THRESHOLD_LIST_PATTERN)
    show_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    body_preview_chars: int | None = Field(default=None, ge=1)


class QuickRecordSettingsRead(BaseModel):
    """ひとこと記録モード（開発Todo「ひとこと記録」v1.0）の設定。

    `last_mode_*`・`voice_hint_dismissed`は設定画面には出さない内部状態（desktopの
    `reminder_onboarding_shown`等と同じ位置づけ）だが、同じ`PATCH /settings`経路で
    読み書きできるようにし、新規の保存APIを増やさない（CLAUDE.md DRYの原則）。
    """

    note_max_chars: int
    last_mode_exam: str
    last_mode_reading: str
    last_mode_work: str
    voice_hint_dismissed: bool


class QuickRecordSettingsUpdate(BaseModel):
    note_max_chars: int | None = Field(default=None, ge=1)
    last_mode_exam: str | None = None
    last_mode_reading: str | None = None
    last_mode_work: str | None = None
    voice_hint_dismissed: bool | None = None


class AppSettingsRead(BaseModel):
    ai_connection: AiConnectionSettingsRead
    threshold: ThresholdSettingsRead
    prompt_degradation: PromptDegradationSettingsRead
    display: DisplaySettingsRead
    desktop: DesktopSettingsRead
    log: LogSettingsRead
    milestone_threshold: MilestoneThresholdSettingsRead
    on_this_day: OnThisDaySettingsRead
    quick_record: QuickRecordSettingsRead


class AppSettingsUpdate(BaseModel):
    ai_connection: AiConnectionSettingsUpdate | None = None
    threshold: ThresholdSettingsUpdate | None = None
    prompt_degradation: PromptDegradationSettingsUpdate | None = None
    display: DisplaySettingsUpdate | None = None
    desktop: DesktopSettingsUpdate | None = None
    log: LogSettingsUpdate | None = None
    milestone_threshold: MilestoneThresholdSettingsUpdate | None = None
    on_this_day: OnThisDaySettingsUpdate | None = None
    quick_record: QuickRecordSettingsUpdate | None = None


class PromptTemplateRead(BaseModel):
    purpose: AiPurpose
    body: str
    is_customized: bool


class PromptTemplateUpdate(BaseModel):
    body: str = Field(min_length=1)
