"""app_setting.key の定数化。

複数ファイルでキー文字列を直書きすると片方だけ修正漏れが起きるため、
コード上で参照するキーはここに集約する（値の初期投入は init/seed_data.py）。
"""

SERVER_PORT = "server.port"
THRESHOLD_WARNING_RATIO = "threshold.warning_ratio"
THRESHOLD_REPLAN_OVERRUN_DAYS = "threshold.replan_overrun_days"
CALENDAR_DAY_BOUNDARY_HOUR = "calendar.day_boundary_hour"
HOLIDAY_TREAT_AS_BUFFER = "holiday.treat_as_buffer"

# AI連携（設計書 ロジック・プロンプト編16章、実装フェーズ分割計画書Phase5）。
AI_HOST = "ai.host"
AI_CLIENT_ID = "ai.client_id"
AI_TENANT_ID = "ai.tenant_id"
AI_API_BASE_URL = "ai.api_base_url"
AI_ASSISTANT_UID_DAILY_FEEDBACK = "ai.assistant_uid.daily_feedback"
AI_ASSISTANT_UID_WEEKLY_SUMMARY = "ai.assistant_uid.weekly_summary"
AI_ASSISTANT_UID_DAILY_MESSAGE = "ai.assistant_uid.daily_message"
AI_ASSISTANT_UID_GOAL_RETROSPECTIVE = "ai.assistant_uid.goal_retrospective"
AI_FOLDER_PREFIX = "ai.folder_prefix"
AI_TIMEOUT_SECONDS = "ai.timeout_seconds"
AI_MAX_RETRIES = "ai.max_retries"
AI_MIN_INTERVAL_SECONDS = "ai.min_interval_seconds"
AI_MAX_PROMPT_CHARS = "ai.max_prompt_chars"
LOG_AI_ENABLED = "log.ai_enabled"
LOG_RETENTION_DAYS = "log.retention_days"
SUMMARY_LOOKBACK_WEEKS = "summary.lookback_weeks"
SUMMARY_INJECT_WEEKS = "summary.inject_weeks"

# ダッシュボード（仕様書6.1、実装フェーズ分割計画書Phase6）。
DASHBOARD_REPORT_RATE_WINDOW_DAYS = "dashboard.report_rate_window_days"
