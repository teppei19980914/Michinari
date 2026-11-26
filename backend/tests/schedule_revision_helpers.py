"""AIによるスケジュール修正案（単位5）のテスト用ヘルパー。"""

import datetime as dt

from app.constants.enums import ExamDateType, GoalCategory, GoalStatus, ScheduleItemStatus
from app.models.book import Book
from app.models.goal import ExamSubject, Goal
from app.models.schedule import ScheduleItem
from app.models.work import WorkAssignment

TODAY = dt.date(2026, 11, 25)


def make_exam_goal(
    session, name: str = "資格目標A", *, start_date: dt.date = dt.date(2026, 1, 1)
) -> Goal:
    goal = Goal(
        name=name, category=GoalCategory.EXAM, start_date=start_date, status=GoalStatus.ACTIVE
    )
    session.add(goal)
    session.flush()
    return goal


def make_reading_goal(
    session,
    name: str = "読書目標A",
    *,
    start_date: dt.date = dt.date(2026, 1, 1),
    due_date: dt.date = dt.date(2026, 12, 31),
) -> Goal:
    goal = Goal(
        name=name, category=GoalCategory.READING, start_date=start_date, status=GoalStatus.ACTIVE
    )
    session.add(goal)
    session.flush()
    session.add(
        Book(
            goal_id=goal.id,
            title="テスト書籍",
            total_pages=200,
            start_date=start_date,
            due_date=due_date,
        )
    )
    session.flush()
    session.refresh(goal)
    return goal


def make_work_goal(
    session, name: str = "仕事目標A", *, start_date: dt.date = dt.date(2026, 1, 1)
) -> Goal:
    goal = Goal(
        name=name, category=GoalCategory.WORK, start_date=start_date, status=GoalStatus.ACTIVE
    )
    session.add(goal)
    session.flush()
    session.add(
        WorkAssignment(goal_id=goal.id, expected_content="想定業務内容", start_date=start_date)
    )
    session.flush()
    session.refresh(goal)
    return goal


def add_fixed_exam_subject(
    session, goal: Goal, *, exam_date_fixed: dt.date, name: str = "科目A"
) -> ExamSubject:
    subject = ExamSubject(
        goal_id=goal.id,
        name=name,
        exam_date_type=ExamDateType.FIXED,
        exam_date_fixed=exam_date_fixed,
        display_order=0,
    )
    session.add(subject)
    session.flush()
    session.refresh(goal)
    return subject


def add_range_exam_subject(
    session, goal: Goal, *, exam_date_from: dt.date, exam_date_to: dt.date, name: str = "科目B"
) -> ExamSubject:
    subject = ExamSubject(
        goal_id=goal.id,
        name=name,
        exam_date_type=ExamDateType.RANGE,
        exam_date_from=exam_date_from,
        exam_date_to=exam_date_to,
        display_order=1,
    )
    session.add(subject)
    session.flush()
    session.refresh(goal)
    return subject


def make_item(
    session,
    goal: Goal,
    *,
    title: str = "作業項目A",
    description: str | None = None,
    planned_start_date: dt.date,
    planned_end_date: dt.date,
    status: ScheduleItemStatus = ScheduleItemStatus.NOT_STARTED,
    actual_start_date: dt.date | None = None,
    actual_end_date: dt.date | None = None,
    display_order: int = 0,
) -> ScheduleItem:
    item = ScheduleItem(
        goal_id=goal.id,
        title=title,
        description=description,
        planned_start_date=planned_start_date,
        planned_end_date=planned_end_date,
        status=status,
        actual_start_date=actual_start_date,
        actual_end_date=actual_end_date,
        display_order=display_order,
    )
    session.add(item)
    session.flush()
    return item
