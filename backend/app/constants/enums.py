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
    DAILY_FEEDBACK_WORK = "DAILY_FEEDBACK_WORK"
    GOAL_RETROSPECTIVE_WORK_MONTHLY = "GOAL_RETROSPECTIVE_WORK_MONTHLY"
    GOAL_RETROSPECTIVE_WORK_SEMIANNUAL = "GOAL_RETROSPECTIVE_WORK_SEMIANNUAL"


class ConversationScope(enum.StrEnum):
    DAILY_FEEDBACK = "DAILY_FEEDBACK"
    WEEKLY_SUMMARY = "WEEKLY_SUMMARY"
    DAILY_MESSAGE = "DAILY_MESSAGE"
    GOAL_RETROSPECTIVE = "GOAL_RETROSPECTIVE"
    DAILY_FEEDBACK_READING = "DAILY_FEEDBACK_READING"
    GOAL_RETROSPECTIVE_READING = "GOAL_RETROSPECTIVE_READING"
    DAILY_FEEDBACK_WORK = "DAILY_FEEDBACK_WORK"
    GOAL_RETROSPECTIVE_WORK_MONTHLY = "GOAL_RETROSPECTIVE_WORK_MONTHLY"
    GOAL_RETROSPECTIVE_WORK_SEMIANNUAL = "GOAL_RETROSPECTIVE_WORK_SEMIANNUAL"


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
