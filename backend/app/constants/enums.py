"""全Enum定義（設計書 データ構造編 5.1）。DBには文字列として保存する。"""

import enum


class GoalStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CLOSED_WITH_RESULT = "CLOSED_WITH_RESULT"
    CLOSED_WITHOUT_RESULT = "CLOSED_WITHOUT_RESULT"


class ExamDateType(enum.StrEnum):
    RANGE = "RANGE"
    FIXED = "FIXED"


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


class ConversationScope(enum.StrEnum):
    DAILY_FEEDBACK = "DAILY_FEEDBACK"
    WEEKLY_SUMMARY = "WEEKLY_SUMMARY"
    DAILY_MESSAGE = "DAILY_MESSAGE"
    GOAL_RETROSPECTIVE = "GOAL_RETROSPECTIVE"


class ExportFormat(enum.StrEnum):
    MARKDOWN = "MARKDOWN"
    JSON = "JSON"


class AppSettingValueType(enum.StrEnum):
    STRING = "STRING"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    BOOLEAN = "BOOLEAN"
    JSON = "JSON"
