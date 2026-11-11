"""アプリ設定・プロンプトテンプレートの取得/更新（設計書データ構造編5.2、仕様書6.11、
実装フェーズ分割計画書Phase7）。

「全ての設定項目は画面上から変更可能とする。設定ファイルの直接編集を必要としない」（仕様書6.11）
を満たすため、app_setting・prompt_template への読み書きをここへ集約する。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.constants.app_setting_keys import (
    AI_API_BASE_URL,
    AI_ASSISTANT_UID_DAILY_FEEDBACK,
    AI_ASSISTANT_UID_DAILY_FEEDBACK_BRIEF,
    AI_ASSISTANT_UID_DAILY_FEEDBACK_READING,
    AI_ASSISTANT_UID_DAILY_FEEDBACK_READING_BRIEF,
    AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK,
    AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK_BRIEF,
    AI_ASSISTANT_UID_DAILY_MESSAGE,
    AI_ASSISTANT_UID_EVALUATION_REPORT_WORK,
    AI_ASSISTANT_UID_GOAL_CONSULTATION,
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE,
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_READING,
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_MONTHLY,
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_SEMIANNUAL,
    AI_ASSISTANT_UID_HELP,
    AI_ASSISTANT_UID_WEEKLY_SUMMARY,
    AI_ASSISTANT_UID_WEEKLY_SUMMARY_READING,
    AI_ASSISTANT_UID_WEEKLY_SUMMARY_WORK,
    AI_CLIENT_ID,
    AI_FOLDER_PREFIX,
    AI_HOST,
    AI_MAX_PROMPT_CHARS,
    AI_MIN_INTERVAL_SECONDS,
    AI_PERSPECTIVE_SUGGESTION_MIN_RECORDS,
    AI_TENANT_ID,
    AI_TIMEOUT_SECONDS,
    DESKTOP_AUTOSTART_BANNER_DISMISSED,
    DESKTOP_LAUNCH_AT_LOGIN,
    DESKTOP_NOTIFICATION_ENABLED,
    DESKTOP_NOTIFICATION_TIME,
    DESKTOP_OPEN_BROWSER_ON_STARTUP,
    DESKTOP_REMINDER_ONBOARDING_SHOWN,
    LOG_AI_ENABLED,
    LOG_RETENTION_DAYS,
    MILESTONE_CONSECUTIVE_DAYS_THRESHOLDS,
    MILESTONE_EXAM_OVERALL_PROGRESS_THRESHOLDS,
    MILESTONE_READING_COMPLETED_BOOKS_THRESHOLDS,
    MILESTONE_READING_TOTAL_PAGES_THRESHOLDS,
    MILESTONE_TOTAL_RECORD_DAYS_THRESHOLDS,
    MILESTONE_WORK_RECORD_COUNT_THRESHOLDS,
    ON_THIS_DAY_BODY_PREVIEW_CHARS,
    ON_THIS_DAY_CANDIDATE_MONTHS_AGO,
    ON_THIS_DAY_ENABLED,
    ON_THIS_DAY_SHOW_PROBABILITY,
    QUICK_RECORD_LAST_MODE_EXAM,
    QUICK_RECORD_LAST_MODE_READING,
    QUICK_RECORD_LAST_MODE_WORK,
    QUICK_RECORD_NOTE_MAX_CHARS,
    QUICK_RECORD_VOICE_HINT_DISMISSED,
    THRESHOLD_REPLAN_OVERRUN_DAYS,
    THRESHOLD_WARNING_RATIO,
)
from app.constants.app_setting_keys import (
    DISPLAY_ACCENT_COLOR as _DISPLAY_ACCENT_COLOR,
)
from app.constants.app_setting_keys import (
    DISPLAY_DEFAULT_GRANULARITY as _DISPLAY_DEFAULT_GRANULARITY,
)
from app.constants.app_setting_keys import (
    DISPLAY_FONT_SCALE as _DISPLAY_FONT_SCALE,
)
from app.constants.app_setting_keys import (
    DISPLAY_LOCALE as _DISPLAY_LOCALE,
)
from app.constants.app_setting_keys import (
    DISPLAY_THEME as _DISPLAY_THEME,
)
from app.constants.enums import AiPurpose, Granularity, RecordInputMode
from app.init.seed_data import INITIAL_PROMPT_TEMPLATES
from app.models.setting import AppSetting, PromptTemplate
from app.services import notification_service, setting_reader
from app.services.exceptions import AppSettingNotFoundError, NotFoundError, ValidationError

#: 表示言語（日英対応、2026-10利用者方針）。画面文言・NewtonXフィードバック・
#: デスクトップ通知の全てがこの値を参照する（`frontend/src/locales/{locale}.json`、
#: `backend/app/locales.py`、`backend/app/ai/orchestration.py`）。
_ALLOWED_LOCALES = frozenset({"ja", "en"})
_ALLOWED_THEMES = frozenset({"system", "light", "dark"})
#: 装飾的な配色バリエーション（UIリッチ化、2026-10利用者方針）。目標種別バッジ等の
#: 意味を持つ固定色とは独立した強調色のみに作用するため、値追加は配色の見た目のみに影響する。
_ALLOWED_ACCENT_COLORS = frozenset({"blue", "green", "purple", "orange"})
_ALLOWED_FONT_SCALES = frozenset({"small", "standard", "large"})
#: 分析画面の粒度（仕様書6.8「日別・週別・月別で切替表示」）。Phase9のGranularity Enumと
#: 同じ値を許容する（CLAUDE.md DRYの原則、値の重複を避けるためEnumの値をそのまま使う）。
_ALLOWED_GRANULARITIES = frozenset(g.value for g in Granularity)
#: ひとこと記録モード（開発Todo「ひとこと記録」v1.0 Q3）の「最後に使ったモード」の許容値。
_ALLOWED_RECORD_INPUT_MODES = frozenset(m.value for m in RecordInputMode)


def _set_str(session: Session, key: str, value: str) -> None:
    row = session.get(AppSetting, key)
    if row is None:
        raise AppSettingNotFoundError(key)
    row.value = value


def _set_number(session: Session, key: str, value: float | int) -> None:
    _set_str(session, key, str(value))


def _set_bool(session: Session, key: str, value: bool) -> None:
    _set_str(session, key, "true" if value else "false")


@dataclass(frozen=True)
class AiConnectionSettings:
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
    assistant_uid_daily_feedback_brief: str
    assistant_uid_daily_feedback_reading_brief: str
    assistant_uid_daily_feedback_work_brief: str
    folder_prefix: str
    timeout_seconds: int
    min_interval_seconds: int


@dataclass(frozen=True)
class ThresholdSettings:
    warning_ratio: float
    replan_overrun_days: int


@dataclass(frozen=True)
class PromptDegradationSettings:
    max_prompt_chars: int
    perspective_suggestion_min_records: int


@dataclass(frozen=True)
class DisplaySettings:
    locale: str
    theme: str
    default_granularity: str
    accent_color: str
    font_scale: str


@dataclass(frozen=True)
class DesktopSettings:
    """デスクトップ常駐・記録リマインドの設定（実装スコープA〜C、Phase37）。

    `reminder_onboarding_shown`・`autostart_banner_dismissed`は設定画面には出さない
    内部状態（開発Todo リマインド導線 D3・D5）だが、他の`desktop.*`設定と同じ
    `PATCH /settings`経路で読み書きできるようにし、新規の保存APIを増やさない
    （CLAUDE.md DRYの原則）。
    """

    open_browser_on_startup: bool
    launch_at_login: bool
    notification_enabled: bool
    notification_time: str
    reminder_onboarding_shown: bool
    autostart_banner_dismissed: bool


@dataclass(frozen=True)
class LogSettings:
    ai_enabled: bool
    retention_days: int


@dataclass(frozen=True)
class MilestoneThresholdSettings:
    """節目のお祝い（開発Todo_節目のお祝い_v1.0）の閾値。値はカンマ区切りの文字列
    （`setting_reader.get_int_list`が整数リストへ変換する側で使う。設定画面は
    文字列のまま編集する）。
    """

    consecutive_days_thresholds: str
    total_record_days_thresholds: str
    reading_total_pages_thresholds: str
    reading_completed_books_thresholds: str
    exam_overall_progress_thresholds: str
    work_record_count_thresholds: str


@dataclass(frozen=True)
class OnThisDaySettings:
    """1年前の今日（開発Todo_1年前の今日_v1.0）のダッシュボード表示に関する設定。

    candidate_months_agoはカンマ区切りの文字列（`setting_reader.get_int_list`が
    整数リストへ変換する側で使う。設定画面は文字列のまま編集する、milestone_thresholdと
    同じ方式）。
    """

    enabled: bool
    candidate_months_ago: str
    show_probability: float
    body_preview_chars: int


@dataclass(frozen=True)
class QuickRecordSettings:
    """ひとこと記録モード（開発Todo「ひとこと記録」v1.0）の設定。DesktopSettingsと同じく、
    内部状態（`last_mode_*`・`voice_hint_dismissed`）も同じ`PATCH /settings`経路で扱う。
    """

    note_max_chars: int
    last_mode_exam: str
    last_mode_reading: str
    last_mode_work: str
    voice_hint_dismissed: bool


@dataclass(frozen=True)
class AppSettings:
    ai_connection: AiConnectionSettings
    threshold: ThresholdSettings
    prompt_degradation: PromptDegradationSettings
    display: DisplaySettings
    desktop: DesktopSettings
    log: LogSettings
    milestone_threshold: MilestoneThresholdSettings
    on_this_day: OnThisDaySettings
    quick_record: QuickRecordSettings


def get_app_settings(session: Session) -> AppSettings:
    ai_connection = AiConnectionSettings(
        host=setting_reader.get_str(session, AI_HOST),
        client_id=setting_reader.get_str(session, AI_CLIENT_ID),
        tenant_id=setting_reader.get_str(session, AI_TENANT_ID),
        api_base_url=setting_reader.get_str(session, AI_API_BASE_URL),
        assistant_uid_daily_feedback=setting_reader.get_str(
            session, AI_ASSISTANT_UID_DAILY_FEEDBACK
        ),
        assistant_uid_weekly_summary=setting_reader.get_str(
            session, AI_ASSISTANT_UID_WEEKLY_SUMMARY
        ),
        assistant_uid_daily_message=setting_reader.get_str(session, AI_ASSISTANT_UID_DAILY_MESSAGE),
        assistant_uid_goal_retrospective=setting_reader.get_str(
            session, AI_ASSISTANT_UID_GOAL_RETROSPECTIVE
        ),
        assistant_uid_daily_feedback_reading=setting_reader.get_str(
            session, AI_ASSISTANT_UID_DAILY_FEEDBACK_READING
        ),
        assistant_uid_goal_retrospective_reading=setting_reader.get_str(
            session, AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_READING
        ),
        assistant_uid_weekly_summary_reading=setting_reader.get_str(
            session, AI_ASSISTANT_UID_WEEKLY_SUMMARY_READING
        ),
        assistant_uid_daily_feedback_work=setting_reader.get_str(
            session, AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK
        ),
        assistant_uid_goal_retrospective_work_monthly=setting_reader.get_str(
            session, AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_MONTHLY
        ),
        assistant_uid_goal_retrospective_work_semiannual=setting_reader.get_str(
            session, AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_SEMIANNUAL
        ),
        assistant_uid_weekly_summary_work=setting_reader.get_str(
            session, AI_ASSISTANT_UID_WEEKLY_SUMMARY_WORK
        ),
        assistant_uid_evaluation_report_work=setting_reader.get_str(
            session, AI_ASSISTANT_UID_EVALUATION_REPORT_WORK
        ),
        assistant_uid_help=setting_reader.get_str(session, AI_ASSISTANT_UID_HELP),
        assistant_uid_goal_consultation=setting_reader.get_str(
            session, AI_ASSISTANT_UID_GOAL_CONSULTATION
        ),
        assistant_uid_daily_feedback_brief=setting_reader.get_str(
            session, AI_ASSISTANT_UID_DAILY_FEEDBACK_BRIEF
        ),
        assistant_uid_daily_feedback_reading_brief=setting_reader.get_str(
            session, AI_ASSISTANT_UID_DAILY_FEEDBACK_READING_BRIEF
        ),
        assistant_uid_daily_feedback_work_brief=setting_reader.get_str(
            session, AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK_BRIEF
        ),
        folder_prefix=setting_reader.get_str(session, AI_FOLDER_PREFIX),
        timeout_seconds=setting_reader.get_int(session, AI_TIMEOUT_SECONDS),
        min_interval_seconds=setting_reader.get_int(session, AI_MIN_INTERVAL_SECONDS),
    )
    threshold = ThresholdSettings(
        warning_ratio=setting_reader.get_float(session, THRESHOLD_WARNING_RATIO),
        replan_overrun_days=setting_reader.get_int(session, THRESHOLD_REPLAN_OVERRUN_DAYS),
    )
    prompt_degradation = PromptDegradationSettings(
        max_prompt_chars=setting_reader.get_int(session, AI_MAX_PROMPT_CHARS),
        perspective_suggestion_min_records=setting_reader.get_int(
            session, AI_PERSPECTIVE_SUGGESTION_MIN_RECORDS
        ),
    )
    display = DisplaySettings(
        locale=setting_reader.get_str(session, _DISPLAY_LOCALE),
        theme=setting_reader.get_str(session, _DISPLAY_THEME),
        default_granularity=setting_reader.get_str(session, _DISPLAY_DEFAULT_GRANULARITY),
        accent_color=setting_reader.get_str(session, _DISPLAY_ACCENT_COLOR),
        font_scale=setting_reader.get_str(session, _DISPLAY_FONT_SCALE),
    )
    desktop = DesktopSettings(
        open_browser_on_startup=setting_reader.get_bool(session, DESKTOP_OPEN_BROWSER_ON_STARTUP),
        launch_at_login=setting_reader.get_bool(session, DESKTOP_LAUNCH_AT_LOGIN),
        notification_enabled=setting_reader.get_bool(session, DESKTOP_NOTIFICATION_ENABLED),
        notification_time=setting_reader.get_str(session, DESKTOP_NOTIFICATION_TIME),
        reminder_onboarding_shown=setting_reader.get_bool(
            session, DESKTOP_REMINDER_ONBOARDING_SHOWN
        ),
        autostart_banner_dismissed=setting_reader.get_bool(
            session, DESKTOP_AUTOSTART_BANNER_DISMISSED
        ),
    )
    log = LogSettings(
        ai_enabled=setting_reader.get_bool(session, LOG_AI_ENABLED),
        retention_days=setting_reader.get_int(session, LOG_RETENTION_DAYS),
    )
    milestone_threshold = MilestoneThresholdSettings(
        consecutive_days_thresholds=setting_reader.get_str(
            session, MILESTONE_CONSECUTIVE_DAYS_THRESHOLDS
        ),
        total_record_days_thresholds=setting_reader.get_str(
            session, MILESTONE_TOTAL_RECORD_DAYS_THRESHOLDS
        ),
        reading_total_pages_thresholds=setting_reader.get_str(
            session, MILESTONE_READING_TOTAL_PAGES_THRESHOLDS
        ),
        reading_completed_books_thresholds=setting_reader.get_str(
            session, MILESTONE_READING_COMPLETED_BOOKS_THRESHOLDS
        ),
        exam_overall_progress_thresholds=setting_reader.get_str(
            session, MILESTONE_EXAM_OVERALL_PROGRESS_THRESHOLDS
        ),
        work_record_count_thresholds=setting_reader.get_str(
            session, MILESTONE_WORK_RECORD_COUNT_THRESHOLDS
        ),
    )
    on_this_day = OnThisDaySettings(
        enabled=setting_reader.get_bool(session, ON_THIS_DAY_ENABLED),
        candidate_months_ago=setting_reader.get_str(session, ON_THIS_DAY_CANDIDATE_MONTHS_AGO),
        show_probability=setting_reader.get_float(session, ON_THIS_DAY_SHOW_PROBABILITY),
        body_preview_chars=setting_reader.get_int(session, ON_THIS_DAY_BODY_PREVIEW_CHARS),
    )
    quick_record = QuickRecordSettings(
        note_max_chars=setting_reader.get_int(session, QUICK_RECORD_NOTE_MAX_CHARS),
        last_mode_exam=setting_reader.get_str(session, QUICK_RECORD_LAST_MODE_EXAM),
        last_mode_reading=setting_reader.get_str(session, QUICK_RECORD_LAST_MODE_READING),
        last_mode_work=setting_reader.get_str(session, QUICK_RECORD_LAST_MODE_WORK),
        voice_hint_dismissed=setting_reader.get_bool(session, QUICK_RECORD_VOICE_HINT_DISMISSED),
    )
    return AppSettings(
        ai_connection=ai_connection,
        threshold=threshold,
        prompt_degradation=prompt_degradation,
        display=display,
        desktop=desktop,
        log=log,
        milestone_threshold=milestone_threshold,
        on_this_day=on_this_day,
        quick_record=quick_record,
    )


@dataclass(frozen=True)
class ReminderOnboardingFlags:
    """ダッシュボード（`GET /dashboard`）が表示する2つの案内の表示条件（開発Todo
    リマインド導線 D2・D5）。都度算出し、保存はしない（CLAUDE.md「日次ノルマ・残量・
    現在周回の保存」禁止と同じ考え方）。
    """

    show_reminder_onboarding_prompt: bool
    show_reminder_autostart_banner: bool


def resolve_reminder_onboarding_flags(session: Session) -> ReminderOnboardingFlags:
    """記録リマインドの案内2件（新規利用者向け・既存利用者向け）を表示すべきかを返す。

    `GET /dashboard`（初期表示2秒以内の性能要件）から呼ばれるため、必要な4キーだけを
    読む。`get_app_settings`は無関係な設定（AI接続・プロンプト縮退等、約25キー）も
    まとめて読み出すため、ここでは使わない。
    """
    reminder_onboarding_shown = setting_reader.get_bool(session, DESKTOP_REMINDER_ONBOARDING_SHOWN)
    notification_enabled = setting_reader.get_bool(session, DESKTOP_NOTIFICATION_ENABLED)
    launch_at_login = setting_reader.get_bool(session, DESKTOP_LAUNCH_AT_LOGIN)
    autostart_banner_dismissed = setting_reader.get_bool(
        session, DESKTOP_AUTOSTART_BANNER_DISMISSED
    )
    return ReminderOnboardingFlags(
        show_reminder_onboarding_prompt=not reminder_onboarding_shown,
        show_reminder_autostart_banner=(
            notification_enabled and not launch_at_login and not autostart_banner_dismissed
        ),
    )


def _update_ai_connection(session: Session, **fields: object) -> None:
    key_by_field = {
        "host": AI_HOST,
        "client_id": AI_CLIENT_ID,
        "tenant_id": AI_TENANT_ID,
        "api_base_url": AI_API_BASE_URL,
        "assistant_uid_daily_feedback": AI_ASSISTANT_UID_DAILY_FEEDBACK,
        "assistant_uid_weekly_summary": AI_ASSISTANT_UID_WEEKLY_SUMMARY,
        "assistant_uid_daily_message": AI_ASSISTANT_UID_DAILY_MESSAGE,
        "assistant_uid_goal_retrospective": AI_ASSISTANT_UID_GOAL_RETROSPECTIVE,
        "assistant_uid_daily_feedback_reading": AI_ASSISTANT_UID_DAILY_FEEDBACK_READING,
        "assistant_uid_goal_retrospective_reading": AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_READING,
        "assistant_uid_weekly_summary_reading": AI_ASSISTANT_UID_WEEKLY_SUMMARY_READING,
        "assistant_uid_daily_feedback_work": AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK,
        "assistant_uid_goal_retrospective_work_monthly": (
            AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_MONTHLY
        ),
        "assistant_uid_goal_retrospective_work_semiannual": (
            AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_SEMIANNUAL
        ),
        "assistant_uid_weekly_summary_work": AI_ASSISTANT_UID_WEEKLY_SUMMARY_WORK,
        "assistant_uid_evaluation_report_work": AI_ASSISTANT_UID_EVALUATION_REPORT_WORK,
        "assistant_uid_help": AI_ASSISTANT_UID_HELP,
        "assistant_uid_goal_consultation": AI_ASSISTANT_UID_GOAL_CONSULTATION,
        "assistant_uid_daily_feedback_brief": AI_ASSISTANT_UID_DAILY_FEEDBACK_BRIEF,
        "assistant_uid_daily_feedback_reading_brief": AI_ASSISTANT_UID_DAILY_FEEDBACK_READING_BRIEF,
        "assistant_uid_daily_feedback_work_brief": AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK_BRIEF,
        "folder_prefix": AI_FOLDER_PREFIX,
    }
    number_key_by_field = {
        "timeout_seconds": AI_TIMEOUT_SECONDS,
        "min_interval_seconds": AI_MIN_INTERVAL_SECONDS,
    }
    for field, value in fields.items():
        if value is None:
            continue
        if field in number_key_by_field:
            _set_number(session, number_key_by_field[field], value)
        else:
            _set_str(session, key_by_field[field], value)


def _update_threshold(session: Session, **fields: object) -> None:
    if fields.get("warning_ratio") is not None:
        _set_number(session, THRESHOLD_WARNING_RATIO, fields["warning_ratio"])
    if fields.get("replan_overrun_days") is not None:
        _set_number(session, THRESHOLD_REPLAN_OVERRUN_DAYS, fields["replan_overrun_days"])


def _update_prompt_degradation(session: Session, **fields: object) -> None:
    if fields.get("max_prompt_chars") is not None:
        _set_number(session, AI_MAX_PROMPT_CHARS, fields["max_prompt_chars"])
    if fields.get("perspective_suggestion_min_records") is not None:
        _set_number(
            session,
            AI_PERSPECTIVE_SUGGESTION_MIN_RECORDS,
            fields["perspective_suggestion_min_records"],
        )


def _update_display(session: Session, **fields: object) -> None:
    locale = fields.get("locale")
    if locale is not None:
        if locale not in _ALLOWED_LOCALES:
            raise ValidationError(f"Locale must be one of: {sorted(_ALLOWED_LOCALES)}")
        _set_str(session, _DISPLAY_LOCALE, locale)
    theme = fields.get("theme")
    if theme is not None:
        if theme not in _ALLOWED_THEMES:
            raise ValidationError(f"Theme must be one of: {sorted(_ALLOWED_THEMES)}")
        _set_str(session, _DISPLAY_THEME, theme)
    granularity = fields.get("default_granularity")
    if granularity is not None:
        if granularity not in _ALLOWED_GRANULARITIES:
            allowed = sorted(_ALLOWED_GRANULARITIES)
            raise ValidationError(f"Default analytics granularity must be one of: {allowed}")
        _set_str(session, _DISPLAY_DEFAULT_GRANULARITY, granularity)
    accent_color = fields.get("accent_color")
    if accent_color is not None:
        if accent_color not in _ALLOWED_ACCENT_COLORS:
            raise ValidationError(f"Accent color must be one of: {sorted(_ALLOWED_ACCENT_COLORS)}")
        _set_str(session, _DISPLAY_ACCENT_COLOR, accent_color)
    font_scale = fields.get("font_scale")
    if font_scale is not None:
        if font_scale not in _ALLOWED_FONT_SCALES:
            raise ValidationError(f"Font scale must be one of: {sorted(_ALLOWED_FONT_SCALES)}")
        _set_str(session, _DISPLAY_FONT_SCALE, font_scale)


def _update_desktop(session: Session, **fields: object) -> None:
    """デスクトップ常駐・通知の設定を更新する。

    自動起動（`launch_at_login`）のWindowsへの反映は**ここでは行わない**。サービス層は
    実行環境を知らない責務であり、レジストリへの反映は`app/desktop/autostart.py`が
    起動時に設定値を読んで行う（CLAUDE.md「サービス層でのHTTP例外の送出」禁止と同じ整理）。
    """
    boolean_key_by_field = {
        "open_browser_on_startup": DESKTOP_OPEN_BROWSER_ON_STARTUP,
        "launch_at_login": DESKTOP_LAUNCH_AT_LOGIN,
        "notification_enabled": DESKTOP_NOTIFICATION_ENABLED,
        "reminder_onboarding_shown": DESKTOP_REMINDER_ONBOARDING_SHOWN,
        "autostart_banner_dismissed": DESKTOP_AUTOSTART_BANNER_DISMISSED,
    }
    for field, key in boolean_key_by_field.items():
        value = fields.get(field)
        if value is not None:
            _set_bool(session, key, value)
    notification_time = fields.get("notification_time")
    if notification_time is not None:
        # 形式の検証はnotification_serviceが持つ（判定と同じ規則を使うため。DRYの原則）。
        notification_service.parse_notification_time(notification_time)
        _set_str(session, DESKTOP_NOTIFICATION_TIME, notification_time)


def _update_log(session: Session, **fields: object) -> None:
    if fields.get("ai_enabled") is not None:
        _set_bool(session, LOG_AI_ENABLED, fields["ai_enabled"])
    if fields.get("retention_days") is not None:
        _set_number(session, LOG_RETENTION_DAYS, fields["retention_days"])


def _parse_threshold_list(raw: str) -> str:
    """節目のお祝い（開発Todo_節目のお祝い_v1.0 M3）の閾値設定を検証し、正規化した
    カンマ区切り文字列（昇順・重複除去）で返す。設定画面からの編集を想定し、
    空白混入や順序違いは許容するが、整数以外・空は拒否する。
    """
    parts = [part.strip() for part in raw.split(",")]
    if any(not part for part in parts):
        raise ValidationError("Milestone thresholds must be a comma-separated list of integers")
    try:
        values = {int(part) for part in parts}
    except ValueError as exc:
        raise ValidationError(
            "Milestone thresholds must be a comma-separated list of integers"
        ) from exc
    if any(value <= 0 for value in values):
        raise ValidationError("Milestone thresholds must be positive integers")
    return ",".join(str(value) for value in sorted(values))


def _update_milestone_threshold(session: Session, **fields: object) -> None:
    key_by_field = {
        "consecutive_days_thresholds": MILESTONE_CONSECUTIVE_DAYS_THRESHOLDS,
        "total_record_days_thresholds": MILESTONE_TOTAL_RECORD_DAYS_THRESHOLDS,
        "reading_total_pages_thresholds": MILESTONE_READING_TOTAL_PAGES_THRESHOLDS,
        "reading_completed_books_thresholds": MILESTONE_READING_COMPLETED_BOOKS_THRESHOLDS,
        "exam_overall_progress_thresholds": MILESTONE_EXAM_OVERALL_PROGRESS_THRESHOLDS,
        "work_record_count_thresholds": MILESTONE_WORK_RECORD_COUNT_THRESHOLDS,
    }
    for field, key in key_by_field.items():
        value = fields.get(field)
        if value is not None:
            _set_str(session, key, _parse_threshold_list(value))


def _update_on_this_day(session: Session, **fields: object) -> None:
    if fields.get("enabled") is not None:
        _set_bool(session, ON_THIS_DAY_ENABLED, fields["enabled"])
    if fields.get("candidate_months_ago") is not None:
        _set_str(
            session,
            ON_THIS_DAY_CANDIDATE_MONTHS_AGO,
            _parse_threshold_list(fields["candidate_months_ago"]),
        )
    if fields.get("show_probability") is not None:
        _set_number(session, ON_THIS_DAY_SHOW_PROBABILITY, fields["show_probability"])
    if fields.get("body_preview_chars") is not None:
        _set_number(session, ON_THIS_DAY_BODY_PREVIEW_CHARS, fields["body_preview_chars"])


def _update_quick_record(session: Session, **fields: object) -> None:
    if fields.get("note_max_chars") is not None:
        _set_number(session, QUICK_RECORD_NOTE_MAX_CHARS, fields["note_max_chars"])
    mode_key_by_field = {
        "last_mode_exam": QUICK_RECORD_LAST_MODE_EXAM,
        "last_mode_reading": QUICK_RECORD_LAST_MODE_READING,
        "last_mode_work": QUICK_RECORD_LAST_MODE_WORK,
    }
    for field, key in mode_key_by_field.items():
        value = fields.get(field)
        if value is not None:
            if value not in _ALLOWED_RECORD_INPUT_MODES:
                allowed = sorted(_ALLOWED_RECORD_INPUT_MODES)
                raise ValidationError(f"Record input mode must be one of: {allowed}")
            _set_str(session, key, value)
    if fields.get("voice_hint_dismissed") is not None:
        _set_bool(session, QUICK_RECORD_VOICE_HINT_DISMISSED, fields["voice_hint_dismissed"])


def update_app_settings(
    session: Session,
    *,
    ai_connection: dict | None = None,
    threshold: dict | None = None,
    prompt_degradation: dict | None = None,
    display: dict | None = None,
    desktop: dict | None = None,
    log: dict | None = None,
    milestone_threshold: dict | None = None,
    on_this_day: dict | None = None,
    quick_record: dict | None = None,
) -> AppSettings:
    if ai_connection:
        _update_ai_connection(session, **ai_connection)
    if threshold:
        _update_threshold(session, **threshold)
    if prompt_degradation:
        _update_prompt_degradation(session, **prompt_degradation)
    if display:
        _update_display(session, **display)
    if desktop:
        _update_desktop(session, **desktop)
    if log:
        _update_log(session, **log)
    if milestone_threshold:
        _update_milestone_threshold(session, **milestone_threshold)
    if on_this_day:
        _update_on_this_day(session, **on_this_day)
    if quick_record:
        _update_quick_record(session, **quick_record)
    session.flush()
    return get_app_settings(session)


def list_prompt_templates(session: Session) -> list[PromptTemplate]:
    return session.query(PromptTemplate).order_by(PromptTemplate.purpose).all()


def get_prompt_template(session: Session, purpose: AiPurpose) -> PromptTemplate:
    template = session.query(PromptTemplate).filter(PromptTemplate.purpose == purpose.value).first()
    if template is None:
        raise NotFoundError("PromptTemplate", purpose.value)
    return template


def update_prompt_template(session: Session, purpose: AiPurpose, body: str) -> PromptTemplate:
    """プロンプトテンプレートを編集する（仕様書6.11「プロンプトテンプレートが編集でき、
    初期値に戻せる」）。CLAUDE.md「プロンプト文面の直接記述」禁止のため、文面はDBのみに存在させる。
    """
    template = get_prompt_template(session, purpose)
    template.body = body
    template.is_customized = True
    session.flush()
    return template


def reset_prompt_template(session: Session, purpose: AiPurpose) -> PromptTemplate:
    """プロンプトテンプレートを初期値へ戻す（仕様書6.11、init/seed_data.INITIAL_PROMPT_TEMPLATES）。"""
    template = get_prompt_template(session, purpose)
    template.body = INITIAL_PROMPT_TEMPLATES[purpose]
    template.is_customized = False
    session.flush()
    return template
