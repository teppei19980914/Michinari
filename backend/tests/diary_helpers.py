"""資格試験の目標・日記を作るテスト用ヘルパー（複数のテストモジュールで共有する）。"""

import datetime as dt

from app.constants.enums import GoalCategory, GoalStatus
from app.models.goal import Goal
from app.services import record_service
from app.services.record_service import DiaryEntryItem


def make_exam_goal(session, name: str = "資格目標", status: GoalStatus = GoalStatus.ACTIVE) -> Goal:
    goal = Goal(
        name=name,
        category=GoalCategory.EXAM,
        start_date=dt.date(2026, 1, 1),
        status=status,
    )
    session.add(goal)
    session.flush()
    return goal


def diary_item(goal_id: int, diary_body: str = "", diary_learned: str = "") -> DiaryEntryItem:
    return DiaryEntryItem(goal_id=goal_id, diary_body=diary_body, diary_learned=diary_learned)


def finalize_diary(
    session, goal: Goal, day: dt.date, *, diary_body: str = "", diary_learned: str = ""
) -> None:
    item = diary_item(goal.id, diary_body, diary_learned)
    record_service.finalize_record(session, day, [], [item], day)
