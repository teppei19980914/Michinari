"""スケジュール・ガントチャート機能のテスト用ヘルパー。"""

import datetime as dt

from sqlalchemy import select

from app.constants.enums import GoalCategory, GoalStatus
from app.models.goal import Goal
from app.models.setting import AppSetting


def make_goal(
    session,
    name: str = "目標A",
    *,
    category: GoalCategory = GoalCategory.EXAM,
    status: GoalStatus = GoalStatus.ACTIVE,
) -> Goal:
    goal = Goal(name=name, category=category, start_date=dt.date(2026, 1, 1), status=status)
    session.add(goal)
    session.flush()
    return goal


def set_setting(session, key: str, value: str) -> None:
    row = session.scalar(select(AppSetting).where(AppSetting.key == key))
    row.value = value
    session.flush()
