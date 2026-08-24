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
    AI_ASSISTANT_UID_DAILY_MESSAGE,
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE,
    AI_ASSISTANT_UID_WEEKLY_SUMMARY,
    AI_CLIENT_ID,
    AI_FOLDER_PREFIX,
    AI_HOST,
    AI_MAX_PROMPT_CHARS,
    AI_MIN_INTERVAL_SECONDS,
    AI_TENANT_ID,
    AI_TIMEOUT_SECONDS,
    LOG_AI_ENABLED,
    LOG_RETENTION_DAYS,
    SUMMARY_INJECT_WEEKS,
    THRESHOLD_REPLAN_OVERRUN_DAYS,
    THRESHOLD_WARNING_RATIO,
)
from app.constants.app_setting_keys import (
    DISPLAY_DEFAULT_GRANULARITY as _DISPLAY_DEFAULT_GRANULARITY,
)
from app.constants.app_setting_keys import (
    DISPLAY_LOCALE as _DISPLAY_LOCALE,
)
from app.constants.app_setting_keys import (
    DISPLAY_THEME as _DISPLAY_THEME,
)
from app.constants.enums import AiPurpose
from app.init.seed_data import INITIAL_PROMPT_TEMPLATES
from app.models.setting import AppSetting, PromptTemplate
from app.services import setting_reader
from app.services.exceptions import AppSettingNotFoundError, NotFoundError, ValidationError

#: 表示言語は技術選定書の対象が日本語のみのため、現時点ではこの1件のみを許容する。
_ALLOWED_LOCALES = frozenset({"ja"})
_ALLOWED_THEMES = frozenset({"system", "light", "dark"})
#: 分析画面の粒度（仕様書6.8「日別・週別・月別で切替表示」）。
_ALLOWED_GRANULARITIES = frozenset({"DAY", "WEEK", "MONTH"})


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
    summary_inject_weeks: int


@dataclass(frozen=True)
class DisplaySettings:
    locale: str
    theme: str
    default_granularity: str


@dataclass(frozen=True)
class LogSettings:
    ai_enabled: bool
    retention_days: int


@dataclass(frozen=True)
class AppSettings:
    ai_connection: AiConnectionSettings
    threshold: ThresholdSettings
    prompt_degradation: PromptDegradationSettings
    display: DisplaySettings
    log: LogSettings


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
        assistant_uid_daily_message=setting_reader.get_str(
            session, AI_ASSISTANT_UID_DAILY_MESSAGE
        ),
        assistant_uid_goal_retrospective=setting_reader.get_str(
            session, AI_ASSISTANT_UID_GOAL_RETROSPECTIVE
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
        summary_inject_weeks=setting_reader.get_int(session, SUMMARY_INJECT_WEEKS),
    )
    display = DisplaySettings(
        locale=setting_reader.get_str(session, _DISPLAY_LOCALE),
        theme=setting_reader.get_str(session, _DISPLAY_THEME),
        default_granularity=setting_reader.get_str(session, _DISPLAY_DEFAULT_GRANULARITY),
    )
    log = LogSettings(
        ai_enabled=setting_reader.get_bool(session, LOG_AI_ENABLED),
        retention_days=setting_reader.get_int(session, LOG_RETENTION_DAYS),
    )
    return AppSettings(
        ai_connection=ai_connection,
        threshold=threshold,
        prompt_degradation=prompt_degradation,
        display=display,
        log=log,
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
    if fields.get("summary_inject_weeks") is not None:
        _set_number(session, SUMMARY_INJECT_WEEKS, fields["summary_inject_weeks"])


def _update_display(session: Session, **fields: object) -> None:
    locale = fields.get("locale")
    if locale is not None:
        if locale not in _ALLOWED_LOCALES:
            raise ValidationError(
                f"表示言語は次のいずれかで指定してください: {sorted(_ALLOWED_LOCALES)}"
            )
        _set_str(session, _DISPLAY_LOCALE, locale)
    theme = fields.get("theme")
    if theme is not None:
        if theme not in _ALLOWED_THEMES:
            raise ValidationError(
                f"テーマは次のいずれかで指定してください: {sorted(_ALLOWED_THEMES)}"
            )
        _set_str(session, _DISPLAY_THEME, theme)
    granularity = fields.get("default_granularity")
    if granularity is not None:
        if granularity not in _ALLOWED_GRANULARITIES:
            allowed = sorted(_ALLOWED_GRANULARITIES)
            raise ValidationError(f"分析画面の既定粒度は次のいずれかで指定してください: {allowed}")
        _set_str(session, _DISPLAY_DEFAULT_GRANULARITY, granularity)


def _update_log(session: Session, **fields: object) -> None:
    if fields.get("ai_enabled") is not None:
        _set_bool(session, LOG_AI_ENABLED, fields["ai_enabled"])
    if fields.get("retention_days") is not None:
        _set_number(session, LOG_RETENTION_DAYS, fields["retention_days"])


def update_app_settings(
    session: Session,
    *,
    ai_connection: dict | None = None,
    threshold: dict | None = None,
    prompt_degradation: dict | None = None,
    display: dict | None = None,
    log: dict | None = None,
) -> AppSettings:
    if ai_connection:
        _update_ai_connection(session, **ai_connection)
    if threshold:
        _update_threshold(session, **threshold)
    if prompt_degradation:
        _update_prompt_degradation(session, **prompt_degradation)
    if display:
        _update_display(session, **display)
    if log:
        _update_log(session, **log)
    session.flush()
    return get_app_settings(session)


def list_prompt_templates(session: Session) -> list[PromptTemplate]:
    return session.query(PromptTemplate).order_by(PromptTemplate.purpose).all()


def get_prompt_template(session: Session, purpose: AiPurpose) -> PromptTemplate:
    template = (
        session.query(PromptTemplate).filter(PromptTemplate.purpose == purpose.value).first()
    )
    if template is None:
        raise NotFoundError("プロンプトテンプレート", purpose.value)
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
