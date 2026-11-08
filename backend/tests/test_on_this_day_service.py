"""on_this_day_service のテスト（開発Todo_1年前の今日_v1.0 §3.3 B-03〜B-05）。"""

import datetime as dt

from app.constants.app_setting_keys import (
    ON_THIS_DAY_BODY_PREVIEW_CHARS,
    ON_THIS_DAY_CANDIDATE_MONTHS_AGO,
    ON_THIS_DAY_ENABLED,
    ON_THIS_DAY_SHOW_PROBABILITY,
)
from app.constants.enums import GoalCategory, GoalStatus
from app.models.book import Book
from app.models.goal import Goal
from app.models.record import DailyGoalDiary, DailyRecord, ReadingLog, WorkLog
from app.models.setting import AppSetting
from app.models.work import WorkAssignment
from app.services import goal_service, on_this_day_service as svc

TODAY = dt.date(2026, 11, 8)


def _set_setting(session, key, value):
    row = session.get(AppSetting, key)
    row.value = value


def _make_goal(session, *, category, status=GoalStatus.ACTIVE, name="テスト目標", **overrides):
    goal = Goal(
        name=name,
        category=category,
        start_date=dt.date(2025, 1, 1),
        status=status,
        **overrides,
    )
    session.add(goal)
    session.flush()
    return goal


def _make_daily_record(session, record_date):
    record = session.query(DailyRecord).filter(DailyRecord.record_date == record_date).first()
    if record is None:
        record = DailyRecord(record_date=record_date)
        session.add(record)
        session.flush()
    return record


def _make_exam_diary(session, goal_id, record_date, *, diary_learned="学んだこと本文"):
    record = _make_daily_record(session, record_date)
    diary = DailyGoalDiary(
        daily_record_id=record.id, goal_id=goal_id, diary_learned=diary_learned
    )
    session.add(diary)
    session.flush()
    return diary


def _make_reading_candidate(session, goal_id, record_date, *, recall_body="想起本文"):
    book = Book(
        goal_id=goal_id,
        title="書籍A",
        total_pages=300,
        start_date=dt.date(2025, 1, 1),
        due_date=dt.date(2026, 12, 31),
    )
    session.add(book)
    session.flush()
    record = _make_daily_record(session, record_date)
    reading_log = ReadingLog(daily_record_id=record.id, book_id=book.id, recall_body=recall_body)
    session.add(reading_log)
    session.flush()
    return reading_log


def _make_work_candidate(session, goal_id, record_date, *, body="業務内容本文"):
    assignment = WorkAssignment(
        goal_id=goal_id, expected_content="想定業務内容", start_date=dt.date(2025, 1, 1)
    )
    session.add(assignment)
    session.flush()
    record = _make_daily_record(session, record_date)
    work_log = WorkLog(daily_record_id=record.id, work_assignment_id=assignment.id, body=body)
    session.add(work_log)
    session.flush()
    return work_log


def _enable_always_show(session, months_ago="12"):
    _set_setting(session, ON_THIS_DAY_ENABLED, "true")
    _set_setting(session, ON_THIS_DAY_SHOW_PROBABILITY, "1.0")
    _set_setting(session, ON_THIS_DAY_CANDIDATE_MONTHS_AGO, months_ago)


class TestSubtractMonths:
    def test_simple_offset_within_same_year(self):
        assert svc.subtract_months(dt.date(2026, 11, 8), 1) == dt.date(2026, 10, 8)

    def test_wraps_year_boundary(self):
        assert svc.subtract_months(dt.date(2026, 1, 15), 1) == dt.date(2025, 12, 15)

    def test_multi_year_offset(self):
        assert svc.subtract_months(dt.date(2026, 11, 8), 24) == dt.date(2024, 11, 8)

    def test_clamps_to_month_end_when_day_does_not_exist(self):
        # 3/31の1ヶ月前は2/28（2026年は平年）。
        assert svc.subtract_months(dt.date(2026, 3, 31), 1) == dt.date(2026, 2, 28)

    def test_clamps_leap_day_to_non_leap_february(self):
        # 2028/2/29（うるう年）の12ヶ月前は2027/2/28（平年、2/29が存在しない）。
        assert svc.subtract_months(dt.date(2028, 2, 29), 12) == dt.date(2027, 2, 28)

    def test_keeps_leap_day_when_target_year_is_also_leap(self):
        assert svc.subtract_months(dt.date(2028, 2, 29), 48) == dt.date(2024, 2, 29)


class TestResolveShowToday:
    def test_is_deterministic_for_the_same_date(self):
        first = svc.resolve_show_today(TODAY, 0.5)
        second = svc.resolve_show_today(TODAY, 0.5)
        assert first == second

    def test_probability_zero_never_shows(self):
        assert svc.resolve_show_today(TODAY, 0.0) is False

    def test_probability_one_always_shows(self):
        assert svc.resolve_show_today(TODAY, 1.0) is True


class TestBuildOnThisDayEntry:
    def test_returns_none_when_disabled(self, seeded_session):
        _enable_always_show(seeded_session)
        _set_setting(seeded_session, ON_THIS_DAY_ENABLED, "false")
        goal = _make_goal(seeded_session, category=GoalCategory.EXAM)
        _make_exam_diary(seeded_session, goal.id, svc.subtract_months(TODAY, 12))

        assert svc.build_on_this_day_entry(seeded_session, TODAY) is None

    def test_returns_none_when_probability_is_zero(self, seeded_session):
        _enable_always_show(seeded_session)
        _set_setting(seeded_session, ON_THIS_DAY_SHOW_PROBABILITY, "0.0")
        goal = _make_goal(seeded_session, category=GoalCategory.EXAM)
        _make_exam_diary(seeded_session, goal.id, svc.subtract_months(TODAY, 12))

        assert svc.build_on_this_day_entry(seeded_session, TODAY) is None

    def test_returns_none_when_no_candidates_exist(self, seeded_session):
        _enable_always_show(seeded_session)

        assert svc.build_on_this_day_entry(seeded_session, TODAY) is None

    def test_returns_none_when_candidate_months_ago_is_empty(self, seeded_session):
        _enable_always_show(seeded_session, months_ago="")
        goal = _make_goal(seeded_session, category=GoalCategory.EXAM)
        _make_exam_diary(seeded_session, goal.id, svc.subtract_months(TODAY, 12))

        assert svc.build_on_this_day_entry(seeded_session, TODAY) is None

    def test_returns_exam_diary_candidate(self, seeded_session):
        _enable_always_show(seeded_session, months_ago="12")
        goal = _make_goal(seeded_session, category=GoalCategory.EXAM, name="資格目標")
        target_date = svc.subtract_months(TODAY, 12)
        _make_exam_diary(seeded_session, goal.id, target_date, diary_learned="1年前に学んだこと")

        entry = svc.build_on_this_day_entry(seeded_session, TODAY)

        assert entry is not None
        assert entry.record_date == target_date
        assert entry.goal_id == goal.id
        assert entry.goal_name == "資格目標"
        assert entry.category == GoalCategory.EXAM
        assert entry.excerpt == "1年前に学んだこと"
        assert entry.months_ago == 12

    def test_returns_reading_candidate(self, seeded_session):
        _enable_always_show(seeded_session, months_ago="6")
        goal = _make_goal(seeded_session, category=GoalCategory.READING, name="読書目標")
        target_date = svc.subtract_months(TODAY, 6)
        _make_reading_candidate(seeded_session, goal.id, target_date, recall_body="半年前の想起")

        entry = svc.build_on_this_day_entry(seeded_session, TODAY)

        assert entry is not None
        assert entry.category == GoalCategory.READING
        assert entry.excerpt == "半年前の想起"
        assert entry.months_ago == 6

    def test_returns_work_candidate(self, seeded_session):
        _enable_always_show(seeded_session, months_ago="1")
        goal = _make_goal(seeded_session, category=GoalCategory.WORK, name="仕事目標")
        target_date = svc.subtract_months(TODAY, 1)
        _make_work_candidate(seeded_session, goal.id, target_date, body="1ヶ月前の業務内容")

        entry = svc.build_on_this_day_entry(seeded_session, TODAY)

        assert entry is not None
        assert entry.category == GoalCategory.WORK
        assert entry.excerpt == "1ヶ月前の業務内容"
        assert entry.months_ago == 1

    def test_truncates_excerpt_to_configured_length(self, seeded_session):
        _enable_always_show(seeded_session, months_ago="12")
        _set_setting(seeded_session, ON_THIS_DAY_BODY_PREVIEW_CHARS, "5")
        goal = _make_goal(seeded_session, category=GoalCategory.EXAM)
        _make_exam_diary(
            seeded_session, goal.id, svc.subtract_months(TODAY, 12), diary_learned="あいうえおかきくけこ"
        )

        entry = svc.build_on_this_day_entry(seeded_session, TODAY)

        assert entry.excerpt == "あいうえお"

    def test_excludes_deleted_goal(self, seeded_session):
        _enable_always_show(seeded_session, months_ago="12")
        goal = _make_goal(seeded_session, category=GoalCategory.EXAM, status=GoalStatus.PAUSED)
        _make_exam_diary(seeded_session, goal.id, svc.subtract_months(TODAY, 12))
        goal_service.delete_goal(seeded_session, goal)

        assert svc.build_on_this_day_entry(seeded_session, TODAY) is None

    def test_includes_archived_goal(self, seeded_session):
        _enable_always_show(seeded_session, months_ago="12")
        goal = _make_goal(
            seeded_session,
            category=GoalCategory.EXAM,
            status=GoalStatus.PAUSED,
            archived_at=dt.datetime(2026, 10, 1),
        )
        _make_exam_diary(seeded_session, goal.id, svc.subtract_months(TODAY, 12))

        entry = svc.build_on_this_day_entry(seeded_session, TODAY)

        assert entry is not None
        assert entry.goal_id == goal.id

    def test_includes_closed_goal(self, seeded_session):
        _enable_always_show(seeded_session, months_ago="12")
        goal = _make_goal(
            seeded_session, category=GoalCategory.EXAM, status=GoalStatus.CLOSED_WITH_RESULT
        )
        _make_exam_diary(seeded_session, goal.id, svc.subtract_months(TODAY, 12))

        entry = svc.build_on_this_day_entry(seeded_session, TODAY)

        assert entry is not None
        assert entry.goal_id == goal.id

    def test_excludes_entry_with_empty_diary_body(self, seeded_session):
        _enable_always_show(seeded_session, months_ago="12")
        goal = _make_goal(seeded_session, category=GoalCategory.EXAM)
        record = _make_daily_record(seeded_session, svc.subtract_months(TODAY, 12))
        diary = DailyGoalDiary(
            daily_record_id=record.id, goal_id=goal.id, diary_learned="", diary_body=None
        )
        seeded_session.add(diary)
        seeded_session.flush()

        assert svc.build_on_this_day_entry(seeded_session, TODAY) is None

    def test_selection_is_deterministic_across_multiple_candidates(self, seeded_session):
        _enable_always_show(seeded_session, months_ago="1,12")
        exam_goal = _make_goal(seeded_session, category=GoalCategory.EXAM, name="資格")
        reading_goal = _make_goal(seeded_session, category=GoalCategory.READING, name="読書")
        _make_exam_diary(seeded_session, exam_goal.id, svc.subtract_months(TODAY, 12))
        _make_reading_candidate(seeded_session, reading_goal.id, svc.subtract_months(TODAY, 1))

        first = svc.build_on_this_day_entry(seeded_session, TODAY)
        second = svc.build_on_this_day_entry(seeded_session, TODAY)

        assert first == second
