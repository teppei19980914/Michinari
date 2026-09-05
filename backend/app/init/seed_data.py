"""起動時の初期データ投入（設計書 データ構造編 5.7）。

マイグレーションではなくアプリケーション起動時に行う。データとスキーマを
分離するためであり、既存レコードは上書きしない（冪等）。
対象: app_setting、prompt_template、day_type_default。
"""

from sqlalchemy.orm import Session

from app.constants.app_setting_keys import (
    AI_API_BASE_URL,
    AI_ASSISTANT_UID_DAILY_FEEDBACK,
    AI_ASSISTANT_UID_DAILY_FEEDBACK_READING,
    AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK,
    AI_ASSISTANT_UID_DAILY_MESSAGE,
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE,
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_READING,
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_MONTHLY,
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_SEMIANNUAL,
    AI_ASSISTANT_UID_WEEKLY_SUMMARY,
    AI_CLIENT_ID,
    AI_FOLDER_PREFIX,
    AI_HOST,
    AI_MAX_PROMPT_CHARS,
    AI_MAX_RETRIES,
    AI_MIN_INTERVAL_SECONDS,
    AI_READING_RECALL_RECENT_DAYS,
    AI_TENANT_ID,
    AI_TIMEOUT_SECONDS,
    AI_WORK_RECENT_LOG_DAYS,
    BACKUP_RETENTION_COUNT,
    CALENDAR_DAY_BOUNDARY_HOUR,
    DASHBOARD_REPORT_RATE_WINDOW_DAYS,
    DISPLAY_DEFAULT_GRANULARITY,
    DISPLAY_LOCALE,
    DISPLAY_THEME,
    HOLIDAY_TREAT_AS_BUFFER,
    LOG_AI_ENABLED,
    LOG_RETENTION_DAYS,
    SERVER_PORT,
    SUMMARY_INJECT_WEEKS,
    SUMMARY_LOOKBACK_WEEKS,
    THRESHOLD_REPLAN_OVERRUN_DAYS,
    THRESHOLD_WARNING_RATIO,
)
from app.constants.enums import AiPurpose, AppSettingValueType, DayType
from app.init import prompt_texts
from app.models.setting import AppSetting, DayTypeDefault, PromptTemplate

# キー: (値, 型)。値は app_setting.value に文字列として保存する（設計書 データ構造編 5.2）。
# ai.assistant_uid.* の値はNewtonX ADK側で発行済みのアシスタント識別子（UUID）であり、
# 実機確認済みの用途別既定値（実装フェーズ分割計画書 Phase 5前提、設計書 データ構造編 5.2）。
INITIAL_APP_SETTINGS: dict[str, tuple[str, AppSettingValueType]] = {
    AI_HOST: ("", AppSettingValueType.STRING),
    AI_CLIENT_ID: ("", AppSettingValueType.STRING),
    AI_TENANT_ID: ("", AppSettingValueType.STRING),
    AI_API_BASE_URL: ("", AppSettingValueType.STRING),
    AI_ASSISTANT_UID_DAILY_FEEDBACK: (
        "d18ad1c0-c7e6-4651-9ff2-4fe86af1a73b",
        AppSettingValueType.STRING,
    ),
    AI_ASSISTANT_UID_WEEKLY_SUMMARY: (
        "849c4042-c6de-404e-a1ce-89812eaf850e",
        AppSettingValueType.STRING,
    ),
    AI_ASSISTANT_UID_DAILY_MESSAGE: (
        "8ed280bb-3040-4ee3-9821-66bb7a4db125",
        AppSettingValueType.STRING,
    ),
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE: (
        "d18ad1c0-c7e6-4651-9ff2-4fe86af1a73b",
        AppSettingValueType.STRING,
    ),
    # 読書用アシスタントは実環境での疎通確認のうえ選定済み（仕様書8.9.1・12章S-07解消）。
    # AI-06は負荷が低くAI-03(今日の一言)と同系統の高速寄りアシスタント、
    # AI-07は低頻度・高品質重視でAI-04(総括レポート)と同一アシスタントを既定値とする。
    AI_ASSISTANT_UID_DAILY_FEEDBACK_READING: (
        "8ed280bb-3040-4ee3-9821-66bb7a4db125",
        AppSettingValueType.STRING,
    ),
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_READING: (
        "d18ad1c0-c7e6-4651-9ff2-4fe86af1a73b",
        AppSettingValueType.STRING,
    ),
    AI_READING_RECALL_RECENT_DAYS: ("14", AppSettingValueType.INTEGER),
    # 仕事用アシスタントも読書と同様に未選定（Phase22で疎通確認のうえ選定）。
    # 空欄のまま初期投入し、設定画面から補う（実装フェーズ分割計画書Phase20）。
    AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK: ("", AppSettingValueType.STRING),
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_MONTHLY: ("", AppSettingValueType.STRING),
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_SEMIANNUAL: ("", AppSettingValueType.STRING),
    AI_WORK_RECENT_LOG_DAYS: ("14", AppSettingValueType.INTEGER),
    AI_FOLDER_PREFIX: ("ミチナリ", AppSettingValueType.STRING),
    AI_TIMEOUT_SECONDS: ("60", AppSettingValueType.INTEGER),
    AI_MAX_RETRIES: ("1", AppSettingValueType.INTEGER),
    AI_MIN_INTERVAL_SECONDS: ("2", AppSettingValueType.INTEGER),
    AI_MAX_PROMPT_CHARS: ("30000", AppSettingValueType.INTEGER),
    THRESHOLD_WARNING_RATIO: ("1.20", AppSettingValueType.FLOAT),
    THRESHOLD_REPLAN_OVERRUN_DAYS: ("3", AppSettingValueType.INTEGER),
    CALENDAR_DAY_BOUNDARY_HOUR: ("0", AppSettingValueType.INTEGER),
    HOLIDAY_TREAT_AS_BUFFER: ("true", AppSettingValueType.BOOLEAN),
    DISPLAY_LOCALE: ("ja", AppSettingValueType.STRING),
    DISPLAY_THEME: ("system", AppSettingValueType.STRING),
    DISPLAY_DEFAULT_GRANULARITY: ("WEEK", AppSettingValueType.STRING),
    LOG_AI_ENABLED: ("true", AppSettingValueType.BOOLEAN),
    LOG_RETENTION_DAYS: ("90", AppSettingValueType.INTEGER),
    SUMMARY_LOOKBACK_WEEKS: ("4", AppSettingValueType.INTEGER),
    SUMMARY_INJECT_WEEKS: ("4", AppSettingValueType.INTEGER),
    SERVER_PORT: ("8100", AppSettingValueType.INTEGER),
    BACKUP_RETENTION_COUNT: ("5", AppSettingValueType.INTEGER),
    DASHBOARD_REPORT_RATE_WINDOW_DAYS: ("30", AppSettingValueType.INTEGER),
}

INITIAL_PROMPT_TEMPLATES: dict[AiPurpose, str] = {
    AiPurpose.DAILY_FEEDBACK: prompt_texts.DAILY_FEEDBACK,
    AiPurpose.WEEKLY_SUMMARY: prompt_texts.WEEKLY_SUMMARY,
    AiPurpose.DAILY_MESSAGE: prompt_texts.DAILY_MESSAGE,
    AiPurpose.GOAL_RETROSPECTIVE: prompt_texts.GOAL_RETROSPECTIVE,
    AiPurpose.DAILY_FEEDBACK_READING: prompt_texts.DAILY_FEEDBACK_READING,
    AiPurpose.GOAL_RETROSPECTIVE_READING: prompt_texts.GOAL_RETROSPECTIVE_READING,
    AiPurpose.DAILY_FEEDBACK_WORK: prompt_texts.DAILY_FEEDBACK_WORK,
    AiPurpose.GOAL_RETROSPECTIVE_WORK_MONTHLY: prompt_texts.GOAL_RETROSPECTIVE_WORK_MONTHLY,
    AiPurpose.GOAL_RETROSPECTIVE_WORK_SEMIANNUAL: prompt_texts.GOAL_RETROSPECTIVE_WORK_SEMIANNUAL,
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


# 読書用アシスタント既定値の一度きりの補正（仕様書8.9.1・12章S-07解消）。
# Phase16時点では実環境での疎通確認前だったため空欄で投入されており、seed_app_settingsの
# 「既存キーは上書きしない」仕組みだけでは既存DBの空欄値が更新されない。ユーザーが設定画面から
# 既に値を入れている場合（空文字以外）は上書きしない。
_READING_ASSISTANT_DEFAULT_KEYS = (
    AI_ASSISTANT_UID_DAILY_FEEDBACK_READING,
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_READING,
)


def backfill_reading_assistant_defaults(session: Session) -> None:
    for key in _READING_ASSISTANT_DEFAULT_KEYS:
        default_value, _ = INITIAL_APP_SETTINGS[key]
        row = (
            session.query(AppSetting)
            .filter(AppSetting.key == key, AppSetting.value == "")
            .first()
        )
        if row is not None:
            row.value = default_value


def run_all(session: Session) -> None:
    seed_app_settings(session)
    seed_prompt_templates(session)
    seed_day_type_defaults(session)
    backfill_reading_assistant_defaults(session)
    session.commit()
