"""全モデルをここでインポートし、Base.metadata と relationship の文字列解決を保証する。"""

from app.models.ai import AiConversation, AiLog
from app.models.base import Base
from app.models.book import Book
from app.models.goal import ExamSubject, Goal, LoadProfile
from app.models.material import Material, MaterialSubject, PlanBaseline
from app.models.record import (
    ChatMessage,
    DailyGoalDiary,
    DailyMessage,
    DailyRecord,
    ExamResult,
    ReadingLog,
    RecordComment,
    StudyLog,
    WeeklySummary,
    WorkLog,
)
from app.models.resource import ResourceSlot, ResourceSlotWeekday
from app.models.retrospective import GoalRetrospective
from app.models.setting import (
    AppSetting,
    CalendarDayOverride,
    DayTypeDefault,
    Holiday,
    PromptTemplate,
)
from app.models.work import WorkAssignment

__all__ = [
    "Base",
    "AppSetting",
    "PromptTemplate",
    "Holiday",
    "DayTypeDefault",
    "CalendarDayOverride",
    "ResourceSlot",
    "ResourceSlotWeekday",
    "Goal",
    "ExamSubject",
    "LoadProfile",
    "Material",
    "MaterialSubject",
    "PlanBaseline",
    "DailyRecord",
    "StudyLog",
    "Book",
    "ReadingLog",
    "WorkAssignment",
    "WorkLog",
    "ChatMessage",
    "RecordComment",
    "DailyGoalDiary",
    "WeeklySummary",
    "DailyMessage",
    "ExamResult",
    "GoalRetrospective",
    "AiConversation",
    "AiLog",
]
