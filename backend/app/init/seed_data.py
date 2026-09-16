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
    AI_ASSISTANT_UID_WEEKLY_SUMMARY_READING,
    AI_ASSISTANT_UID_WEEKLY_SUMMARY_WORK,
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
    DESKTOP_LAUNCH_AT_LOGIN,
    DESKTOP_NOTIFICATION_CHECK_INTERVAL_SECONDS,
    DESKTOP_NOTIFICATION_ENABLED,
    DESKTOP_NOTIFICATION_TIME,
    DESKTOP_OPEN_BROWSER_ON_STARTUP,
    DISPLAY_DEFAULT_GRANULARITY,
    DISPLAY_LOCALE,
    DISPLAY_THEME,
    HOLIDAY_TREAT_AS_BUFFER,
    LOG_AI_ENABLED,
    LOG_RETENTION_DAYS,
    SERVER_GRACEFUL_SHUTDOWN_SECONDS,
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
    # 読書用週次要約（AI-11、L-11）は資格試験用週次要約（AI-02、上記）と同じ「要約」という
    # タスクのため、対象がカテゴリを問わず同一アシスタント（Gemini 2.5 Flash・高速。
    # 「日常的な要約や調べものに適しています」）を既定値とする（2026-09-16、S-11解消。
    # 万が一利用者が設定を変更し忘れても動作不良にならないよう、既定値を空文字のままには
    # しない方針。ユーザーが明示的に変更した場合のみ設定APIから上書きする、他の用途と
    # 同じ運用）。
    AI_ASSISTANT_UID_WEEKLY_SUMMARY_READING: (
        "849c4042-c6de-404e-a1ce-89812eaf850e",
        AppSettingValueType.STRING,
    ),
    AI_READING_RECALL_RECENT_DAYS: ("14", AppSettingValueType.INTEGER),
    # 仕事の日次フィードバックは読書の日次フィードバックと同一アシスタント
    # （GPT-5.4-mini・高速）を既定値とする。要件定義時点で「読書機能同様に日々の頑張りを
    # 労うフィードバック」と明示されており、高頻度・低負荷という性質も読書と一致するため
    # （実装フェーズ分割計画書Phase22）。
    AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK: (
        "8ed280bb-3040-4ee3-9821-66bb7a4db125",
        AppSettingValueType.STRING,
    ),
    # 月次報告・半期評価は低頻度・高品質重視のため、総括レポート（AI-04）・読了レポート
    # （AI-07）と同じアシスタント（GPT-5.4・高性能。「複雑なタスクの整理や具体的な提案に
    # 適しています」）を既定値とする（2026-09-16、S-09解消。理由はAI_ASSISTANT_UID_
    # WEEKLY_SUMMARY_READINGと同じ、空文字のまま投入しない方針）。
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_MONTHLY: (
        "d18ad1c0-c7e6-4651-9ff2-4fe86af1a73b",
        AppSettingValueType.STRING,
    ),
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_SEMIANNUAL: (
        "d18ad1c0-c7e6-4651-9ff2-4fe86af1a73b",
        AppSettingValueType.STRING,
    ),
    # 仕事用週次要約（L-11）は読書用（AI_ASSISTANT_UID_WEEKLY_SUMMARY_READING）と同じ理由・
    # 同じアシスタントを既定値とする（2026-09-16、S-11解消）。
    AI_ASSISTANT_UID_WEEKLY_SUMMARY_WORK: (
        "849c4042-c6de-404e-a1ce-89812eaf850e",
        AppSettingValueType.STRING,
    ),
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
    SERVER_GRACEFUL_SHUTDOWN_SECONDS: ("10", AppSettingValueType.INTEGER),
    # デスクトップ常駐・記録リマインド通知（Phase37）。ブラウザの自動起動は従来の
    # 振る舞い（起動するたびに開く）を既定とし、煩わしい利用者が設定で切れるようにする。
    # 自動起動は利用者の端末へ手を入れる設定のため、明示的に有効化されるまで無効とする。
    DESKTOP_OPEN_BROWSER_ON_STARTUP: ("true", AppSettingValueType.BOOLEAN),
    DESKTOP_LAUNCH_AT_LOGIN: ("false", AppSettingValueType.BOOLEAN),
    DESKTOP_NOTIFICATION_ENABLED: ("true", AppSettingValueType.BOOLEAN),
    DESKTOP_NOTIFICATION_TIME: ("21:00", AppSettingValueType.STRING),
    DESKTOP_NOTIFICATION_CHECK_INTERVAL_SECONDS: ("60", AppSettingValueType.INTEGER),
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
    AiPurpose.WEEKLY_SUMMARY_READING: prompt_texts.WEEKLY_SUMMARY_READING,
    AiPurpose.DAILY_FEEDBACK_WORK: prompt_texts.DAILY_FEEDBACK_WORK,
    AiPurpose.GOAL_RETROSPECTIVE_WORK_MONTHLY: prompt_texts.GOAL_RETROSPECTIVE_WORK_MONTHLY,
    AiPurpose.GOAL_RETROSPECTIVE_WORK_SEMIANNUAL: prompt_texts.GOAL_RETROSPECTIVE_WORK_SEMIANNUAL,
    AiPurpose.WEEKLY_SUMMARY_WORK: prompt_texts.WEEKLY_SUMMARY_WORK,
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


# カテゴリ別アシスタント既定値の一度きりの補正（仕様書8.9.1・12章S-07・S-09・S-11解消）。
# 当初は空欄で投入されており、seed_app_settingsの「既存キーは上書きしない」仕組みだけでは
# 既存DBの空欄値が更新されない。ユーザーが設定画面から既に値を入れている場合
# （空文字以外）は上書きしない。2026-09-16、アシスタント一覧（説明付き）の提供を受けて
# 月次報告・半期評価・読書用/仕事用週次要約の既定値も選定し対象に追加した
# （万が一設定を変更し忘れても空文字のままにはしないため、L-09・L-11解消）。
_READING_ASSISTANT_DEFAULT_KEYS = (
    AI_ASSISTANT_UID_DAILY_FEEDBACK_READING,
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_READING,
    AI_ASSISTANT_UID_WEEKLY_SUMMARY_READING,
)

_WORK_ASSISTANT_DEFAULT_KEYS = (
    AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK,
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_MONTHLY,
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_SEMIANNUAL,
    AI_ASSISTANT_UID_WEEKLY_SUMMARY_WORK,
)


def _backfill_assistant_defaults(session: Session, keys: tuple[str, ...]) -> None:
    for key in keys:
        default_value, _ = INITIAL_APP_SETTINGS[key]
        row = (
            session.query(AppSetting).filter(AppSetting.key == key, AppSetting.value == "").first()
        )
        if row is not None:
            row.value = default_value


def backfill_reading_assistant_defaults(session: Session) -> None:
    _backfill_assistant_defaults(session, _READING_ASSISTANT_DEFAULT_KEYS)


def backfill_work_assistant_defaults(session: Session) -> None:
    _backfill_assistant_defaults(session, _WORK_ASSISTANT_DEFAULT_KEYS)


def run_all(session: Session) -> None:
    seed_app_settings(session)
    seed_prompt_templates(session)
    seed_day_type_defaults(session)
    backfill_reading_assistant_defaults(session)
    backfill_work_assistant_defaults(session)
    session.commit()
