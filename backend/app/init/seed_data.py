"""起動時の初期データ投入（設計書 データ構造編 5.7）。

マイグレーションではなくアプリケーション起動時に行う。データとスキーマを
分離するためであり、既存レコードは上書きしない（冪等）。
対象: app_setting、prompt_template、day_type_default。
"""

from sqlalchemy.orm import Session

from app.constants.app_setting_keys import SERVER_PORT
from app.constants.enums import AiPurpose, AppSettingValueType, DayType
from app.init import prompt_texts
from app.models.setting import AppSetting, DayTypeDefault, PromptTemplate

# キー: (値, 型)。値は app_setting.value に文字列として保存する（設計書 データ構造編 5.2）。
# ai.assistant_uid.* の値はNewtonX ADK側で発行済みのアシスタント識別子（UUID）であり、
# 実機確認済みの用途別既定値（実装フェーズ分割計画書 Phase 5前提、設計書 データ構造編 5.2）。
INITIAL_APP_SETTINGS: dict[str, tuple[str, AppSettingValueType]] = {
    "ai.host": ("", AppSettingValueType.STRING),
    "ai.client_id": ("", AppSettingValueType.STRING),
    "ai.tenant_id": ("", AppSettingValueType.STRING),
    "ai.api_base_url": ("", AppSettingValueType.STRING),
    "ai.assistant_uid.daily_feedback": (
        "d18ad1c0-c7e6-4651-9ff2-4fe86af1a73b",
        AppSettingValueType.STRING,
    ),
    "ai.assistant_uid.weekly_summary": (
        "849c4042-c6de-404e-a1ce-89812eaf850e",
        AppSettingValueType.STRING,
    ),
    "ai.assistant_uid.daily_message": (
        "8ed280bb-3040-4ee3-9821-66bb7a4db125",
        AppSettingValueType.STRING,
    ),
    "ai.assistant_uid.goal_retrospective": (
        "d18ad1c0-c7e6-4651-9ff2-4fe86af1a73b",
        AppSettingValueType.STRING,
    ),
    "ai.folder_prefix": ("ミチナリ", AppSettingValueType.STRING),
    "ai.timeout_seconds": ("60", AppSettingValueType.INTEGER),
    "ai.max_retries": ("1", AppSettingValueType.INTEGER),
    "ai.min_interval_seconds": ("2", AppSettingValueType.INTEGER),
    "ai.max_prompt_chars": ("30000", AppSettingValueType.INTEGER),
    "threshold.warning_ratio": ("1.20", AppSettingValueType.FLOAT),
    "threshold.replan_overrun_days": ("3", AppSettingValueType.INTEGER),
    "calendar.day_boundary_hour": ("0", AppSettingValueType.INTEGER),
    "holiday.treat_as_buffer": ("true", AppSettingValueType.BOOLEAN),
    "display.locale": ("ja", AppSettingValueType.STRING),
    "display.theme": ("system", AppSettingValueType.STRING),
    "display.default_granularity": ("WEEK", AppSettingValueType.STRING),
    "log.ai_enabled": ("true", AppSettingValueType.BOOLEAN),
    "log.retention_days": ("90", AppSettingValueType.INTEGER),
    "summary.lookback_weeks": ("4", AppSettingValueType.INTEGER),
    "summary.inject_weeks": ("4", AppSettingValueType.INTEGER),
    SERVER_PORT: ("8100", AppSettingValueType.INTEGER),
    "backup.retention_count": ("5", AppSettingValueType.INTEGER),
}

INITIAL_PROMPT_TEMPLATES: dict[AiPurpose, str] = {
    AiPurpose.DAILY_FEEDBACK: prompt_texts.DAILY_FEEDBACK,
    AiPurpose.WEEKLY_SUMMARY: prompt_texts.WEEKLY_SUMMARY,
    AiPurpose.DAILY_MESSAGE: prompt_texts.DAILY_MESSAGE,
    AiPurpose.GOAL_RETROSPECTIVE: prompt_texts.GOAL_RETROSPECTIVE,
}

# 曜日既定値：月〜金=PLAN、土日=BUFFER（設計書 データ構造編 5.2）。OFFは既定値にしない。
INITIAL_DAY_TYPE_DEFAULTS: dict[int, DayType] = {
    0: DayType.PLAN,
    1: DayType.PLAN,
    2: DayType.PLAN,
    3: DayType.PLAN,
    4: DayType.PLAN,
    5: DayType.BUFFER,
    6: DayType.BUFFER,
}


def seed_app_settings(session: Session) -> None:
    existing_keys = {row.key for row in session.query(AppSetting.key).all()}
    for key, (value, value_type) in INITIAL_APP_SETTINGS.items():
        if key in existing_keys:
            continue
        session.add(AppSetting(key=key, value=value, value_type=value_type))


def seed_prompt_templates(session: Session) -> None:
    existing_purposes = {row.purpose for row in session.query(PromptTemplate.purpose).all()}
    for purpose, body in INITIAL_PROMPT_TEMPLATES.items():
        if purpose.value in existing_purposes:
            continue
        session.add(PromptTemplate(purpose=purpose.value, body=body, is_customized=False))


def seed_day_type_defaults(session: Session) -> None:
    existing_weekdays = {row.weekday for row in session.query(DayTypeDefault.weekday).all()}
    for weekday, day_type in INITIAL_DAY_TYPE_DEFAULTS.items():
        if weekday in existing_weekdays:
            continue
        session.add(DayTypeDefault(weekday=weekday, day_type=day_type))


def run_all(session: Session) -> None:
    seed_app_settings(session)
    seed_prompt_templates(session)
    seed_day_type_defaults(session)
    session.commit()
