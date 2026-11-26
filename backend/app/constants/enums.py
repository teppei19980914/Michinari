"""全Enum定義（設計書 データ構造編 5.1）。DBには文字列として保存する。"""

import enum


class GoalStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CLOSED_WITH_RESULT = "CLOSED_WITH_RESULT"
    CLOSED_WITHOUT_RESULT = "CLOSED_WITHOUT_RESULT"


class GoalCategory(enum.StrEnum):
    """目標種別（要件定義書6.10）。EXAMは管理型、READINGは記録・活用型、WORKは定期報告型。"""

    EXAM = "EXAM"
    READING = "READING"
    WORK = "WORK"


class ExamDateType(enum.StrEnum):
    RANGE = "RANGE"
    FIXED = "FIXED"


class PassingScoreType(enum.StrEnum):
    """合格点の入力方式（百分率／点数。設計書 データ構造編 5.3）。"""

    PERCENTAGE = "PERCENTAGE"
    RAW_SCORE = "RAW_SCORE"


class DayType(enum.StrEnum):
    PLAN = "PLAN"
    BUFFER = "BUFFER"
    OFF = "OFF"


class Environment(enum.StrEnum):
    ANY = "ANY"
    PC = "PC"
    MOBILE = "MOBILE"


class QualityMetricType(enum.StrEnum):
    NONE = "NONE"
    OBJECTIVE = "OBJECTIVE"
    SELF_SCORED = "SELF_SCORED"
    SUBJECTIVE = "SUBJECTIVE"


class RecordState(enum.StrEnum):
    PROGRESS_ONLY = "PROGRESS_ONLY"
    REPORTED = "REPORTED"


class RecordInputMode(enum.StrEnum):
    """日次報告の入力方式（開発Todo「ひとこと記録」v1.0）。カテゴリ別に「最後に使った
    モード」をapp_settingへ記憶し、次回表示時の既定モードに使う（Q3）。
    """

    NORMAL = "NORMAL"
    QUICK = "QUICK"


class ChatRole(enum.StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class BaselineReason(enum.StrEnum):
    """計画基準値の再設定契機（ロジック・プロンプト編12.1）。

    REPLANは予約値であり、現時点でこの値が記録される経路は存在しない。仕様書は
    「リプラン」を独立した操作として定義しておらず（警告バナー・MD-01からは目標編集画面へ
    誘導する）、実際の再設定はMATERIAL_CHANGED・CYCLE_CHANGED・EXAM_DATE_FIXEDの
    いずれかとして記録されるため（12.1「REPLANが予約値である理由」）。
    """

    INITIAL = "INITIAL"
    REPLAN = "REPLAN"
    EXAM_DATE_FIXED = "EXAM_DATE_FIXED"
    MATERIAL_CHANGED = "MATERIAL_CHANGED"
    CYCLE_CHANGED = "CYCLE_CHANGED"
    #: 中断・完了・一時停止からの再開時の再計画（開発Todo 1-5。再開日から残り期間で組み直す）。
    RESUMED = "RESUMED"


class ExamResultType(enum.StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    PENDING = "PENDING"


class AiPurpose(enum.StrEnum):
    DAILY_FEEDBACK = "DAILY_FEEDBACK"
    WEEKLY_SUMMARY = "WEEKLY_SUMMARY"
    DAILY_MESSAGE = "DAILY_MESSAGE"
    GOAL_RETROSPECTIVE = "GOAL_RETROSPECTIVE"
    DAILY_FEEDBACK_READING = "DAILY_FEEDBACK_READING"
    GOAL_RETROSPECTIVE_READING = "GOAL_RETROSPECTIVE_READING"
    WEEKLY_SUMMARY_READING = "WEEKLY_SUMMARY_READING"
    DAILY_FEEDBACK_WORK = "DAILY_FEEDBACK_WORK"
    GOAL_RETROSPECTIVE_WORK_MONTHLY = "GOAL_RETROSPECTIVE_WORK_MONTHLY"
    GOAL_RETROSPECTIVE_WORK_SEMIANNUAL = "GOAL_RETROSPECTIVE_WORK_SEMIANNUAL"
    WEEKLY_SUMMARY_WORK = "WEEKLY_SUMMARY_WORK"
    EVALUATION_REPORT_WORK = "EVALUATION_REPORT_WORK"
    RECAP_CLASSIFY = "RECAP_CLASSIFY"
    RECAP_THEME_BODY = "RECAP_THEME_BODY"
    HELP_ASSISTANT = "HELP_ASSISTANT"
    GOAL_CONSULTATION = "GOAL_CONSULTATION"
    GOAL_CONSULTATION_READING = "GOAL_CONSULTATION_READING"
    GOAL_CONSULTATION_WORK = "GOAL_CONSULTATION_WORK"
    QUIZ_GENERATE = "QUIZ_GENERATE"
    #: 単語帳のカードから今日の復習の問題を作る（開発Todo_単語帳_v1.0 要件B）。
    VOCAB_QUIZ_GENERATE = "VOCAB_QUIZ_GENERATE"
    #: シチュエーションカードから今日の復習の問題を作る（開発Todo_単語帳_v1.0 要件F）。
    #: 問題文・正解は登録済みの状況・問い・最善の対応をそのまま使い、AIには誤答3つだけを
    #: 作らせる点がVOCAB_QUIZ_GENERATE（4択すべてをAIが作る）と異なるため別の用途とする。
    VOCAB_SITUATION_QUIZ_GENERATE = "VOCAB_SITUATION_QUIZ_GENERATE"
    #: 日次報告の日記（学んだこと）から、単語帳へ追加する用語の候補を抜き出す
    #: （開発Todo_単語帳_v1.0 要件D）。
    VOCAB_TERM_EXTRACT = "VOCAB_TERM_EXTRACT"
    #: ひとこと記録モード（開発Todo「ひとこと記録」v1.0 Q2）で確定した日の日次報告
    #: フィードバック。注入変数・コンテキスト構築は各カテゴリの非BRIEF版と同じ
    #: （prompt_builder.build_daily_feedback／build_with_degradable_entriesをそのまま再利用し、
    #: prompt_templateの本文のみ差し替える）。会話・assistant_uidは非BRIEF版と分離する。
    DAILY_FEEDBACK_BRIEF = "DAILY_FEEDBACK_BRIEF"
    DAILY_FEEDBACK_READING_BRIEF = "DAILY_FEEDBACK_READING_BRIEF"
    DAILY_FEEDBACK_WORK_BRIEF = "DAILY_FEEDBACK_WORK_BRIEF"
    #: ふりかえりまとめ・共有カード（開発Todo「まとめと共有カード」v1.0）のAI一文生成。
    #: 利用者が「AIに一文を選んでもらう」操作をしたときのみ呼ぶ（自動生成しない）。
    SUMMARY_CARD_SENTENCE = "SUMMARY_CARD_SENTENCE"
    SUMMARY_CARD_SENTENCE_READING = "SUMMARY_CARD_SENTENCE_READING"
    SUMMARY_CARD_SENTENCE_WORK = "SUMMARY_CARD_SENTENCE_WORK"
    #: AIによるスケジュール修正案の生成（開発Todo_スケジュール・ガントチャート_v1.1
    #: 第13章、単位5）。1回ごとに完結する呼び出しで会話は継続しない（13.3）。
    #: 3カテゴリ共通の1用途（D-52、日次フィードバックのプロンプト・品質には影響させない）。
    SCHEDULE_REVISION = "SCHEDULE_REVISION"


class ConversationScope(enum.StrEnum):
    DAILY_FEEDBACK = "DAILY_FEEDBACK"
    WEEKLY_SUMMARY = "WEEKLY_SUMMARY"
    DAILY_MESSAGE = "DAILY_MESSAGE"
    GOAL_RETROSPECTIVE = "GOAL_RETROSPECTIVE"
    DAILY_FEEDBACK_READING = "DAILY_FEEDBACK_READING"
    GOAL_RETROSPECTIVE_READING = "GOAL_RETROSPECTIVE_READING"
    WEEKLY_SUMMARY_READING = "WEEKLY_SUMMARY_READING"
    DAILY_FEEDBACK_WORK = "DAILY_FEEDBACK_WORK"
    GOAL_RETROSPECTIVE_WORK_MONTHLY = "GOAL_RETROSPECTIVE_WORK_MONTHLY"
    GOAL_RETROSPECTIVE_WORK_SEMIANNUAL = "GOAL_RETROSPECTIVE_WORK_SEMIANNUAL"
    WEEKLY_SUMMARY_WORK = "WEEKLY_SUMMARY_WORK"
    EVALUATION_REPORT_WORK = "EVALUATION_REPORT_WORK"
    RECAP = "RECAP"
    HELP_ASSISTANT = "HELP_ASSISTANT"
    GOAL_CONSULTATION = "GOAL_CONSULTATION"
    GOAL_CONSULTATION_READING = "GOAL_CONSULTATION_READING"
    GOAL_CONSULTATION_WORK = "GOAL_CONSULTATION_WORK"
    QUIZ_GENERATE = "QUIZ_GENERATE"
    #: AiPurposeの同名定数と対になる単語帳由来のクイズ生成用の会話スコープ。
    VOCAB_QUIZ_GENERATE = "VOCAB_QUIZ_GENERATE"
    #: AiPurposeの同名定数と対になるシチュエーションカード由来のクイズ生成用の会話スコープ。
    VOCAB_SITUATION_QUIZ_GENERATE = "VOCAB_SITUATION_QUIZ_GENERATE"
    #: AiPurposeの同名定数と対になる用語提案（日記からの抜き出し）用の会話スコープ。
    VOCAB_TERM_EXTRACT = "VOCAB_TERM_EXTRACT"
    #: AiPurposeの同名定数と対になるひとこと記録モード用の会話スコープ（17.2.1/17.6.1/17.8.1）。
    DAILY_FEEDBACK_BRIEF = "DAILY_FEEDBACK_BRIEF"
    DAILY_FEEDBACK_READING_BRIEF = "DAILY_FEEDBACK_READING_BRIEF"
    DAILY_FEEDBACK_WORK_BRIEF = "DAILY_FEEDBACK_WORK_BRIEF"
    #: AiPurposeの同名定数と対になるふりかえりまとめ・共有カード用の会話スコープ。
    SUMMARY_CARD_SENTENCE = "SUMMARY_CARD_SENTENCE"
    SUMMARY_CARD_SENTENCE_READING = "SUMMARY_CARD_SENTENCE_READING"
    SUMMARY_CARD_SENTENCE_WORK = "SUMMARY_CARD_SENTENCE_WORK"
    #: AiPurposeの同名定数と対になるスケジュール修正案生成用の会話スコープ。
    SCHEDULE_REVISION = "SCHEDULE_REVISION"


class WorkMemberGender(enum.StrEnum):
    """チームメンバーの性別（任意入力、要件定義書6.11「チームメンバー管理」）。"""

    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class WorkEvaluationRole(enum.StrEnum):
    """仕事目標における利用者自身の自己申告ロール（要件定義書6.11）。マルチユーザー機能
    ではなく、単独利用の利用者がその目標に対しどちらの立場かを自己申告する1フィールド
    （EVALUATOR時のみ評価レポート出力UIを表示する判定に使う）。
    """

    EVALUATOR = "EVALUATOR"
    EVALUATEE = "EVALUATEE"


class RetrospectivePeriodType(enum.StrEnum):
    """goal_retrospective.period_type（WORKの月次報告・半期評価のみ使用。設計書
    データ構造編5.4「goal_retrospective（総括レポート／読了レポート／定期報告）」）。
    """

    MONTHLY = "MONTHLY"
    SEMI_ANNUAL = "SEMI_ANNUAL"


class ExportFormat(enum.StrEnum):
    MARKDOWN = "MARKDOWN"
    JSON = "JSON"


class Granularity(enum.StrEnum):
    """分析画面の粒度（仕様書6.8「日別・週別・月別で切替表示」）。

    settings_service._ALLOWED_GRANULARITIES（display.default_granularityの許容値）と
    同じ値を用いる（CLAUDE.md DRYの原則）。
    """

    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"


class AppSettingValueType(enum.StrEnum):
    STRING = "STRING"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    BOOLEAN = "BOOLEAN"
    JSON = "JSON"


class RecapSourceKind(enum.StrEnum):
    """振り返り（テーマ累積）の元になる報告の種類（資格試験の日記・読書の想起記録）。"""

    DIARY = "DIARY"
    READING = "READING"


class HelpAnswerStatus(enum.StrEnum):
    """ヘルプAIアシスタントの回答の状態（仕様書6.18、開発Todo §2）。

    文言は画面側（`ja.json` の `help.assistant.*`）で解決する。バックエンドは状態だけを返す。
    """

    #: ヘルプ本文に基づく回答（出典つき）。
    ANSWERED = "ANSWERED"
    #: ヘルプに記載が見当たらない（出典が実在しない・該当セクションが無い）。
    NOT_FOUND = "NOT_FOUND"
    #: 禁止語・長すぎる回答など、回答を表示できない。
    UNAVAILABLE = "UNAVAILABLE"


class MilestoneType(enum.StrEnum):
    """節目のお祝い（開発Todo_節目のお祝い_v1.0）の節目種別。

    `CONSECUTIVE_DAYS`・`TOTAL_RECORD_DAYS`は3種別共通。他は種別固有
    （`GoalCategory`との対応は`milestone_service_<category>.py`側が持つ）。
    """

    #: 連続記録日数（3種別共通。既存の統計サマリの定義をそのまま使う＝種別ごとに
    #: 「何もしていない」記録・予備日の扱いが異なる非対称性を統一しない）。
    CONSECUTIVE_DAYS = "CONSECUTIVE_DAYS"
    #: 累計記録日数（3種別共通）。
    TOTAL_RECORD_DAYS = "TOTAL_RECORD_DAYS"
    #: 読書：累計ページ数。
    READING_TOTAL_PAGES = "READING_TOTAL_PAGES"
    #: 読書：読了した冊数。
    READING_COMPLETED_BOOKS = "READING_COMPLETED_BOOKS"
    #: 資格試験：教材1周完了（閾値を持たないイベント型。周回ごとに1件）。
    EXAM_MATERIAL_CYCLE_COMPLETED = "EXAM_MATERIAL_CYCLE_COMPLETED"
    #: 資格試験：目標全体の進捗率(%)。
    EXAM_OVERALL_PROGRESS = "EXAM_OVERALL_PROGRESS"
    #: 資格試験：単語帳の習得用語数（その目標の全単語帳の合計、開発Todo_単語帳_v1.0 要件E）。
    VOCAB_MASTERED_TERMS = "VOCAB_MASTERED_TERMS"
    #: 仕事：記録件数。
    WORK_RECORD_COUNT = "WORK_RECORD_COUNT"
    #: 仕事：評価期間を通して記録し続けたこと（閾値を持たないイベント型）。
    WORK_EVALUATION_PERIOD_COMPLETED = "WORK_EVALUATION_PERIOD_COMPLETED"


class GoalConsultationAnswerStatus(enum.StrEnum):
    """目標相談チャット（S09で資格目標向けに導入、S10で読書・仕事へ展開）の回答の状態
    （開発Todo U17）。

    `HelpAnswerStatus`と異なり`NOT_FOUND`は持たない。回答は「記録から言えること」と
    「一般的な助言」を併記する構成（開発Todo U12）のため、記録に根拠が無い場合でも
    一般的な助言は有用な回答になる。根拠が無いことの説明は、AIへの指示文で
    「記録からはまだ判断できません」という固定フレーズを使わせる形でプロンプト側に
    埋め込み（`prompt_texts_exam.GOAL_CONSULTATION`・`prompt_texts_reading.
    GOAL_CONSULTATION_READING`・`prompt_texts_work.GOAL_CONSULTATION_WORK`）、
    API層の状態としては扱わない。文言は画面側（`ja.json` の `goalConsultation.*`）で
    解決する。バックエンドは状態だけを返す。
    """

    #: 回答（出典の有無を問わない。出典が無い場合は本文内に理由が書かれる）。
    ANSWERED = "ANSWERED"
    #: 禁止語・長すぎる回答・出力形式の解釈失敗など、回答を表示できない。
    UNAVAILABLE = "UNAVAILABLE"


class VocabQuizMode(enum.StrEnum):
    """単語帳の問題集（開発Todo_単語帳_v1.0 要件A）の出題形式。AIは使わない。

    `FLASH_*`はカードをめくる形式（答えを見た後に自分で判定）、`TYPED_*`は入力式
    （サーバー側で判定）、`CHOICE_*`は4択（誤答選択肢は同じ単語帳の他カードから生成）。
    """

    FLASH_TERM_TO_MEANING = "FLASH_TERM_TO_MEANING"
    FLASH_MEANING_TO_TERM = "FLASH_MEANING_TO_TERM"
    TYPED_MEANING_TO_TERM = "TYPED_MEANING_TO_TERM"
    CHOICE_TERM_TO_MEANING = "CHOICE_TERM_TO_MEANING"
    CHOICE_MEANING_TO_TERM = "CHOICE_MEANING_TO_TERM"
    #: シチュエーションカード専用（開発Todo_単語帳_v1.0 要件F F-U4）。状況・問いを表示し、
    #: めくると最善の対応・解説を表示して自己採点する（FLASH_*と同じ自己判定方式）。
    FLASH_SITUATION = "FLASH_SITUATION"
    #: 方向（用語→意味／意味→用語）を1問ごとにランダムに決める（開発Todo_単語帳_出題導線改修
    #: _v1.0 U5・D4）。TERMカード専用。SITUATIONカードに当たった場合は他のモードと同じく
    #: FLASH_SITUATIONへ差し替わる（`_effective_mode`）。
    FLASH_RANDOM = "FLASH_RANDOM"
    CHOICE_RANDOM = "CHOICE_RANDOM"


class VocabCardType(enum.StrEnum):
    """単語帳カードの種類（開発Todo_単語帳_v1.0 要件F）。作成後は変更できない（F-D2）。

    TERM: 用語カード（既存、要件A〜E）。SITUATION: シチュエーションカード
    （見出し・状況・問い・最善の対応・解説の5項目、要件F）。
    """

    TERM = "TERM"
    SITUATION = "SITUATION"


class ScheduleItemStatus(enum.StrEnum):
    """スケジュール作業項目の状況（開発Todo_スケジュール・ガントチャート_v1.1 D-10）。

    実績日の入力可否は状況に応じた条件付き必須（本書6.2）。
    """

    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class ScheduleUpdateSource(enum.StrEnum):
    """schedule_item_historyの更新元（開発Todo_スケジュール・ガントチャート_v1.1 D-39）。

    DAILY_REPORT・PROGRESS_ONLYは単位4の`schedule_service.apply_report_schedule_item_updates`
    が使う（確定API3本・progress APIからの更新、本書4章）。
    """

    SCHEDULE_SCREEN = "SCHEDULE_SCREEN"
    DAILY_REPORT = "DAILY_REPORT"
    PROGRESS_ONLY = "PROGRESS_ONLY"


class ScheduleColumnType(enum.StrEnum):
    """スケジュールの追加列の型（開発Todo_スケジュール・ガントチャート_v1.1 D-12）。

    MVPはTEXTのみ。
    """

    TEXT = "TEXT"


class ScheduleRevisionTrigger(enum.StrEnum):
    """AIによるスケジュール修正案の生成きっかけ（開発Todo_スケジュール・ガントチャート_v1.1
    13.1・13.7、単位5）。AUTOは日次報告の確定後の自動生成、MANUALはスケジュールタブの
    「AIに修正案を依頼」ボタン。
    """

    AUTO = "AUTO"
    MANUAL = "MANUAL"


class ScheduleRevisionProposalStatus(enum.StrEnum):
    """修正案（schedule_revision_proposal）の状態（本書13.6）。

    PENDINGは未判断の行が残っている、RESOLVEDは全行判断済み、SUPERSEDEDは新しい修正案に
    置き換えられて終了（D-65、目標ごとに未判断の修正案は常に1つ）。
    """

    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    SUPERSEDED = "SUPERSEDED"


class ScheduleRevisionItemKind(enum.StrEnum):
    """修正案の行の種類（本書13.6）。CHANGEは予定日の変更案、WARNINGは期限内に収まらない等の注意。"""

    CHANGE = "CHANGE"
    WARNING = "WARNING"


class ScheduleRevisionDecision(enum.StrEnum):
    """修正案の行に対する利用者の判断（本書13.6・13.7）。

    ACKNOWLEDGEDはWARNING行の「確認しました」。SUPERSEDEDはD-65で古い修正案の未判断行が
    置き換えられた場合。
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    SUPERSEDED = "SUPERSEDED"


class VocabTermSuggestionStatus(enum.StrEnum):
    """日次報告の日記から抜き出した単語帳の用語候補の状態（開発Todo_単語帳_v1.0 要件D）。

    `PENDING`は未対応、`ADDED`は単語帳へ追加済み、`DISMISSED`は見送り済み。いずれも
    同じ目標・同じ用語（term_key）では再提案しない（開発Todo §0.8 D-U5）。
    """

    PENDING = "PENDING"
    ADDED = "ADDED"
    DISMISSED = "DISMISSED"
