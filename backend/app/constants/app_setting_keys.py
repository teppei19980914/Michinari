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
#: 再開時の再計画で、教材の基準値（1日あたりの必要量）が停止前のこの倍率以上に増えたら警告する。
RESUME_QUOTA_WARNING_RATIO = "resume.quota_warning_ratio"
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
AI_FOLDER_PREFIX = "ai.folder_prefix"
AI_TIMEOUT_SECONDS = "ai.timeout_seconds"
AI_MAX_RETRIES = "ai.max_retries"
AI_MIN_INTERVAL_SECONDS = "ai.min_interval_seconds"
AI_MAX_PROMPT_CHARS = "ai.max_prompt_chars"
#: ヘルプAIアシスタント（Phase43、仕様書8.1 AI-14）。用途専用の設定値は app_setting に置く。
AI_ASSISTANT_UID_HELP = "ai.assistant_uid.help"
AI_HELP_FOLDER_NAME = "ai.help_folder_name"
AI_HELP_QUESTION_MAX_CHARS = "ai.help_question_max_chars"
AI_HELP_ANSWER_MAX_CHARS = "ai.help_answer_max_chars"
#: 目標相談チャット（S09、資格目標専用）。ヘルプAIアシスタントと同じ位置づけの用途専用設定。
AI_ASSISTANT_UID_GOAL_CONSULTATION = "ai.assistant_uid.goal_consultation"
AI_GOAL_CONSULTATION_FOLDER_NAME = "ai.goal_consultation_folder_name"
AI_GOAL_CONSULTATION_QUESTION_MAX_CHARS = "ai.goal_consultation_question_max_chars"
AI_GOAL_CONSULTATION_ANSWER_MAX_CHARS = "ai.goal_consultation_answer_max_chars"
#: 会話継続（S11）でプロンプトに含める直近往復数の既定値（開発Todo v1.2 W9、確認事項②）。
AI_GOAL_CONSULTATION_HISTORY_TURNS = "ai.goal_consultation_history_turns"
#: 日次報告フィードバックへ観点提案の追加指示（S-4 4-3）を注入する閾値。この件数未満の
#: 確定済み記録しか無い学習者には、AIが傾向を断定せず複数の観点から問いかけるよう促す。
AI_PERSPECTIVE_SUGGESTION_MIN_RECORDS = "ai.perspective_suggestion_min_records"
#: ひとこと記録モード（開発Todo「ひとこと記録」v1.0 Q2）用の短文プロンプト専用アシスタント。
#: 既存のDAILY_FEEDBACK系とは別のNewtonXアシスタントUID（会話・文脈を分離するため）。
AI_ASSISTANT_UID_DAILY_FEEDBACK_BRIEF = "ai.assistant_uid.daily_feedback_brief"
AI_ASSISTANT_UID_DAILY_FEEDBACK_READING_BRIEF = "ai.assistant_uid.daily_feedback_reading_brief"
AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK_BRIEF = "ai.assistant_uid.daily_feedback_work_brief"
#: NewtonXへ送るプロンプト末尾に追記する応答言語の指示文（日英i18n対応、2026-10）。
#: `display.locale`に応じてどちらを使うかを`orchestration.send_and_log`が選ぶ。
#: `prompt_template`には置かない（設定画面のテンプレート編集一覧に無条件で表示されて
#: しまうため、2026-10-09の設計検討で確認済み）。
AI_LANGUAGE_DIRECTIVE_JA = "ai.language_directive.ja"
AI_LANGUAGE_DIRECTIVE_EN = "ai.language_directive.en"
LOG_AI_ENABLED = "log.ai_enabled"
LOG_RETENTION_DAYS = "log.retention_days"
#: 週次要約の起動時遡及生成（15.2）で、1回の起動あたり生成する(goal, week)件数の上限。
#: 遡及対象の週は目標開始日（読書はbook.start_date）まで遡るため上限が無いと起動が長引く
#: （G3、旧summary.lookback_weeksは検索窓自体を打ち切る方式だったため廃止し、本キーへ置換）。
SUMMARY_RETROACTIVE_MAX_PER_RUN = "summary.retroactive_max_per_run"

# ダッシュボード（仕様書6.1、実装フェーズ分割計画書Phase6）。
DASHBOARD_REPORT_RATE_WINDOW_DAYS = "dashboard.report_rate_window_days"

# 表示設定（仕様書6.11、実装フェーズ分割計画書Phase7）。
DISPLAY_LOCALE = "display.locale"
DISPLAY_THEME = "display.theme"
DISPLAY_DEFAULT_GRANULARITY = "display.default_granularity"
#: 装飾的な配色バリエーション（UIリッチ化）。目標種別バッジ等の意味を持つ固定色とは別軸で、
#: ボタン・リンク等の強調色のみに作用する（2026-10 利用者方針）。
DISPLAY_ACCENT_COLOR = "display.accent_color"
#: 画面全体のフォントサイズ倍率（UIリッチ化）。
DISPLAY_FONT_SCALE = "display.font_scale"

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
#: 新規利用者向け「記録リマインドを受け取りますか」の1問案内を表示済みか（開発Todo
#: リマインド導線 D3）。一度表示（回答済み）したら二度と出さない。既存DBへの初期値は
#: 単純な固定値ではなく、起動時点で目標が既にあるかで分岐させる必要があるため
#: `init/seed_data.py`の`INITIAL_APP_SETTINGS`ではなく専用関数で投入する（D4）。
DESKTOP_REMINDER_ONBOARDING_SHOWN = "desktop.reminder_onboarding_shown"
#: 既存利用者向け「自動起動が無効」ダッシュボード案内を閉じたか（開発Todo リマインド導線 D5）。
#: 閉じた後は二度と出さない。
DESKTOP_AUTOSTART_BANNER_DISMISSED = "desktop.autostart_banner_dismissed"

#: 振り返り（テーマ累積）の分類バッチ1回分の報告本文の上限文字数（プロンプト上限の内側に収める）。
RECAP_CLASSIFY_CHUNK_CHARS = "recap.classify_chunk_chars"
#: テーマ本文の上限文字数。超えた場合はサブテーマへの分割を指示する（削って収めない）。
RECAP_BODY_MAX_CHARS = "recap.body_max_chars"
#: テーマ本文の更新で、更新前の文字数に対して下回ってはならない比率（下回る応答は採用しない）。
RECAP_MIN_RETENTION_RATIO = "recap.min_retention_ratio"

# 添付ファイル機能（開発Todo_添付ファイル機能_v1.0）。goal非依存の共通プール。
#: 1ファイルあたりの抽出テキスト文字数上限（登録時バリデーション、A7）。
AI_ATTACHMENT_MAX_FILE_CHARS = "ai.attachment_max_file_chars"
#: 保持できる添付ファイルの件数上限（A10）。
AI_ATTACHMENT_MAX_COUNT = "ai.attachment_max_count"
#: アップロード時のPDFファイルサイズ上限（MB、P1）。
AI_ATTACHMENT_MAX_UPLOAD_SIZE_MB = "ai.attachment_max_upload_size_mb"

# 節目のお祝い（開発Todo_節目のお祝い_v1.0）。値はカンマ区切りの整数文字列
# （`AppSettingValueType.STRING`。`setting_reader.get_int_list`で読む）。
#: 3種別共通：連続記録日数の節目。
MILESTONE_CONSECUTIVE_DAYS_THRESHOLDS = "milestone.consecutive_days_thresholds"
#: 3種別共通：累計記録日数の節目。
MILESTONE_TOTAL_RECORD_DAYS_THRESHOLDS = "milestone.total_record_days_thresholds"
#: 読書：累計ページ数の節目。
MILESTONE_READING_TOTAL_PAGES_THRESHOLDS = "milestone.reading_total_pages_thresholds"
#: 読書：読了冊数の節目。
MILESTONE_READING_COMPLETED_BOOKS_THRESHOLDS = "milestone.reading_completed_books_thresholds"
#: 資格試験：目標全体の進捗率(%)の節目。
MILESTONE_EXAM_OVERALL_PROGRESS_THRESHOLDS = "milestone.exam_overall_progress_thresholds"
#: 仕事：記録件数の節目。
MILESTONE_WORK_RECORD_COUNT_THRESHOLDS = "milestone.work_record_count_thresholds"
#: 起動時バックフィル（既存利用者の更新直後に節目のお祝いが大量表示されるのを防ぐ、M9）が
#: 完了済みかどうか。`true`になった後は二度と実行しない。
MILESTONE_BACKFILL_COMPLETED = "milestone.backfill_completed"

# 復習クイズ（開発Todo_復習クイズ_v1.0）。テーマ累積（資格試験・読書）からAIが生成するクイズ。
#: 1テーマから生成するクイズの問題数。
QUIZ_QUESTIONS_PER_THEME = "quiz.questions_per_theme"
#: 間隔を空けた出題の間隔日数（カンマ区切りの整数文字列。`setting_reader.get_int_list`で読む）。
#: 正解で次の間隔へ進め、不正解で最初（先頭）の間隔へ戻す。
QUIZ_INTERVAL_DAYS = "quiz.interval_days"
#: 1日に出題するクイズの件数の上限。
QUIZ_DAILY_LIMIT = "quiz.daily_limit"

# 1年前の今日（開発Todo_1年前の今日_v1.0）。ダッシュボードに過去の同じ日の記録をときどき表示する。
#: 表示するかどうかの大本の切替。falseの間は常に非表示。
ON_THIS_DAY_ENABLED = "on_this_day.enabled"
#: 候補とする「何か月前」のリスト（カンマ区切りの整数文字列、昇順。
#: `setting_reader.get_int_list`で読む）。
ON_THIS_DAY_CANDIDATE_MONTHS_AGO = "on_this_day.candidate_months_ago"
#: 1日あたりの表示確率（0.0〜1.0）。日付から決定的に算出するため、同日は常に同じ結果になる。
ON_THIS_DAY_SHOW_PROBABILITY = "on_this_day.show_probability"
#: 記録本文の抜粋の文字数上限。
ON_THIS_DAY_BODY_PREVIEW_CHARS = "on_this_day.body_preview_chars"

# ひとこと記録モード（開発Todo「ひとこと記録」v1.0）。気分スタンプ＋1行メモだけで
# 日次報告を確定できるモード。
#: 1行メモの最大文字数（サーバ側バリデーション、D3）。
QUICK_RECORD_NOTE_MAX_CHARS = "quick_record.note_max_chars"
#: カテゴリ別「最後に使ったモード」（Q3）。値は`RecordInputMode`の文字列（NORMAL/QUICK）。
QUICK_RECORD_LAST_MODE_EXAM = "quick_record.last_mode.exam"
QUICK_RECORD_LAST_MODE_READING = "quick_record.last_mode.reading"
QUICK_RECORD_LAST_MODE_WORK = "quick_record.last_mode.work"
#: 音声入力ヒント（Win+H案内）を閉じたか（Q5、日記欄・想起欄・業務内容欄・ひとこと欄の
#: 4箇所共通）。閉じた後は二度と出さない。
QUICK_RECORD_VOICE_HINT_DISMISSED = "quick_record.voice_hint_dismissed"
