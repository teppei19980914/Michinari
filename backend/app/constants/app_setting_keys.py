"""app_setting.key の定数化。

複数ファイルでキー文字列を直書きすると片方だけ修正漏れが起きるため、
コード上で参照するキーはここに集約する（値の初期投入は init/seed_data.py）。
"""

SERVER_PORT = "server.port"
#: 「終了」操作時、処理中のリクエスト（DBへの書き込みを含む）の完了を待つ上限秒数。
#: server.port と同じく画面には出さない基盤値だが、待ち時間をコードへ直書きしないため
#: app_setting へ置く（CLAUDE.md「閾値・パラメータの直接記述」禁止）。
SERVER_GRACEFUL_SHUTDOWN_SECONDS = "server.graceful_shutdown_seconds"
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
AI_ASSISTANT_UID_DAILY_FEEDBACK_READING = "ai.assistant_uid.daily_feedback_reading"
AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_READING = "ai.assistant_uid.goal_retrospective_reading"
#: 読書用の週次要約（AI-06・AI-07と同じく資格試験用（15章）とは別のプロンプト・
#: アシスタント設定を用いる、L-11）。
AI_ASSISTANT_UID_WEEKLY_SUMMARY_READING = "ai.assistant_uid.weekly_summary_reading"
AI_READING_RECALL_RECENT_DAYS = "ai.reading_recall_recent_days"
AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK = "ai.assistant_uid.daily_feedback_work"
AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_MONTHLY = (
    "ai.assistant_uid.goal_retrospective_work_monthly"
)
AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_SEMIANNUAL = (
    "ai.assistant_uid.goal_retrospective_work_semiannual"
)
#: 仕事用の週次要約（読書のAI_ASSISTANT_UID_WEEKLY_SUMMARY_READINGと同じ位置づけ、L-11）。
AI_ASSISTANT_UID_WEEKLY_SUMMARY_WORK = "ai.assistant_uid.weekly_summary_work"
#: AI評価レポート（要件定義書6.11）。月次/半期報告と同様、低頻度・高精度が求められる用途
#: のため高精度アシスタント枠を用いる（実環境での疎通確認・選定はseed_data参照）。
AI_ASSISTANT_UID_EVALUATION_REPORT_WORK = "ai.assistant_uid.evaluation_report_work"
AI_WORK_RECENT_LOG_DAYS = "ai.work_recent_log_days"
AI_FOLDER_PREFIX = "ai.folder_prefix"
AI_TIMEOUT_SECONDS = "ai.timeout_seconds"
AI_MAX_RETRIES = "ai.max_retries"
AI_MIN_INTERVAL_SECONDS = "ai.min_interval_seconds"
AI_MAX_PROMPT_CHARS = "ai.max_prompt_chars"
#: 日次報告フィードバックへ観点提案の追加指示（S-4 4-3）を注入する閾値。この件数未満の
#: 確定済み記録しか無い学習者には、AIが傾向を断定せず複数の観点から問いかけるよう促す。
AI_PERSPECTIVE_SUGGESTION_MIN_RECORDS = "ai.perspective_suggestion_min_records"
LOG_AI_ENABLED = "log.ai_enabled"
LOG_RETENTION_DAYS = "log.retention_days"
SUMMARY_LOOKBACK_WEEKS = "summary.lookback_weeks"
SUMMARY_INJECT_WEEKS = "summary.inject_weeks"

# ダッシュボード（仕様書6.1、実装フェーズ分割計画書Phase6）。
DASHBOARD_REPORT_RATE_WINDOW_DAYS = "dashboard.report_rate_window_days"

# 表示設定（仕様書6.11、実装フェーズ分割計画書Phase7）。
DISPLAY_LOCALE = "display.locale"
DISPLAY_THEME = "display.theme"
DISPLAY_DEFAULT_GRANULARITY = "display.default_granularity"

# データ管理（仕様書6.12、データ構造編9章D-02、実装フェーズ分割計画書Phase10）。
BACKUP_RETENTION_COUNT = "backup.retention_count"

# デスクトップ常駐・記録リマインド通知（Phase37）。
DESKTOP_OPEN_BROWSER_ON_STARTUP = "desktop.open_browser_on_startup"
DESKTOP_LAUNCH_AT_LOGIN = "desktop.launch_at_login"
DESKTOP_NOTIFICATION_ENABLED = "desktop.notification_enabled"
DESKTOP_NOTIFICATION_TIME = "desktop.notification_time"
#: 通知時刻をまたいだかを調べる間隔。設定画面には出さない（利用者が調整する値ではない）が、
#: 秒数をスケジューラへ直書きしないため app_setting へ置く。
DESKTOP_NOTIFICATION_CHECK_INTERVAL_SECONDS = "desktop.notification_check_interval_seconds"
