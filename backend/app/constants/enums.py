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
