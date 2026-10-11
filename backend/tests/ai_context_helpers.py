"""ai_context_common／ai_context_exam／ai_context_reading／ai_context_workの各テストで
共通して使う生成処理（CLAUDE.md DRYの原則。reading_helpers.pyと同じ位置づけ）。
"""

import datetime as dt

from app.constants.enums import GoalStatus
from app.models.goal import Goal


def make_goal(session, name="目標A", status=GoalStatus.ACTIVE):
    goal = Goal(name=name, start_date=dt.date(2026, 1, 1), status=status)
    session.add(goal)
    session.flush()
    return goal
