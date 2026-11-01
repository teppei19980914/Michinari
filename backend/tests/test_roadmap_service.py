"""roadmap_service のテスト（開発Todo_道のりマップ_v1.0.md §3.3 B-02〜B-04・B-06）。

境界ケース（記録0件・ゴール当日・ゴール超過・進捗100%・各goal.status・archived_at設定済み）を
中心に検証する。算出式の根拠は§0の決定事項（U4〜U10・U16・U17）・roadmap_service.pyの
docstringを参照。
"""

import datetime as dt

from app.constants.enums import (
    AiPurpose,
    BaselineReason,
    ChatRole,
    DayType,
    ExamDateType,
    GoalCategory,
    GoalStatus,
)
from app.models.book import Book
from app.models.goal import ExamSubject, Goal
from app.models.material import Material, PlanBaseline
from app.models.record import ChatMessage, DailyRecord, ReadingLog, StudyLog, WorkLog
from app.models.setting import CalendarDayOverride
from app.models.work import WorkAssignment
from app.services import roadmap_service


def _make_goal(
    db_session,
    category=GoalCategory.EXAM,
    name="道のり検証",
    start_date=dt.date(2026, 1, 1),
    status=GoalStatus.ACTIVE,
    **overrides,
) -> Goal:
    goal = Goal(name=name, category=category, start_date=start_date, status=status, **overrides)
    db_session.add(goal)
    db_session.flush()
    return goal


def _make_subject(db_session, goal_id, exam_date, name="科目A", display_order=1) -> ExamSubject:
    subject = ExamSubject(
        goal_id=goal_id,
        name=name,
        exam_date_type=ExamDateType.FIXED,
        exam_date_fixed=exam_date,
        display_order=display_order,
    )
    db_session.add(subject)
    db_session.flush()
    return subject


def _make_material(
    db_session,
    goal_id,
    start_date,
    due_date,
    total_amount=100.0,
    planned_cycles=1,
    name="教材A",
) -> Material:
    material = Material(
        goal_id=goal_id,
        name=name,
        unit_label="問",
        total_amount=total_amount,
        planned_cycles=planned_cycles,
        start_date=start_date,
        due_date=due_date,
        display_order=1,
    )
    db_session.add(material)
    db_session.flush()
    return material


def _add_baseline(
    db_session,
    material_id,
    effective_from,
    quota,
    remaining_at_baseline=100.0,
    reason=BaselineReason.INITIAL,
) -> PlanBaseline:
    baseline = PlanBaseline(
        material_id=material_id,
        effective_from=effective_from,
        baseline_daily_quota=quota,
        remaining_at_baseline=remaining_at_baseline,
        plan_days_at_baseline=10,
        planned_cycles_at_baseline=1,
        reason=reason,
    )
    db_session.add(baseline)
    db_session.flush()
    return baseline


def _get_or_create_record(db_session, record_date) -> DailyRecord:
    record = db_session.query(DailyRecord).filter(DailyRecord.record_date == record_date).first()
    if record is None:
        record = DailyRecord(record_date=record_date)
        db_session.add(record)
        db_session.flush()
    return record


def _add_study_log(db_session, material_id, record_date, amount) -> None:
    record = _get_or_create_record(db_session, record_date)
    db_session.add(
        StudyLog(
            daily_record_id=record.id,
            material_id=material_id,
            amount_completed=amount,
            cycle_number=1,
        )
    )
    db_session.flush()


def _add_feedback_message(
    db_session, goal_id, record_date, purpose=AiPurpose.DAILY_FEEDBACK
) -> None:
    record = _get_or_create_record(db_session, record_date)
    db_session.add(
        ChatMessage(
            daily_record_id=record.id,
            goal_id=goal_id,
            purpose=purpose,
            role=ChatRole.ASSISTANT,
            content="フィードバック本文",
            sequence=1,
        )
    )
    db_session.flush()


# --- EXAM ---


def test_exam_roadmap_with_no_subjects_or_materials_does_not_crash(db_session):
    """境界ケース：記録0件（科目・教材とも未登録の下書き中の目標）。"""
    goal = _make_goal(db_session, status=GoalStatus.DRAFT)

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 1, 10), True)

    assert roadmap.category == GoalCategory.EXAM
    assert roadmap.goal_date == goal.start_date
    assert roadmap.progress_ratio == 0.0
    assert roadmap.is_achieved is False
    assert roadmap.planned_points == []
    assert roadmap.actual_points == []
    assert roadmap.footprint_dates == []
    assert roadmap.replan_marks == []
    assert roadmap.buffer_dates == []
    assert roadmap.overrun_days is None


def test_exam_roadmap_summit_date_is_latest_exam_date_across_subjects(db_session):
    """§0 U4：山頂の日付は全科目中の最も遅い有効受験日。"""
    goal = _make_goal(db_session)
    _make_subject(db_session, goal.id, dt.date(2026, 6, 1), name="科目A", display_order=1)
    _make_subject(db_session, goal.id, dt.date(2026, 8, 1), name="科目B", display_order=2)

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 1, 10), True)

    assert roadmap.goal_date == dt.date(2026, 8, 1)


def test_exam_roadmap_progress_ratio_reaches_100_percent_and_is_achieved(db_session):
    """境界ケース：進捗100%（全周回完了）。"""
    goal = _make_goal(db_session)
    _make_subject(db_session, goal.id, dt.date(2026, 6, 1))
    material = _make_material(db_session, goal.id, dt.date(2026, 1, 1), dt.date(2026, 5, 31))
    _add_study_log(db_session, material.id, dt.date(2026, 1, 5), 100.0)

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 1, 10), True)

    assert roadmap.progress_ratio == 1.0
    assert roadmap.is_achieved is True


def test_exam_roadmap_replan_marks_exclude_initial_and_include_later_reasons(db_session):
    """§0 U10：INITIALは「引き直し」ではないため除外。MATERIAL_CHANGED等は目印として含む。"""
    goal = _make_goal(db_session)
    _make_subject(db_session, goal.id, dt.date(2026, 6, 1))
    material = _make_material(db_session, goal.id, dt.date(2026, 1, 1), dt.date(2026, 5, 31))
    _add_baseline(
        db_session, material.id, dt.date(2026, 1, 1), quota=10, remaining_at_baseline=100.0
    )
    _add_baseline(
        db_session,
        material.id,
        dt.date(2026, 2, 1),
        quota=15,
        remaining_at_baseline=80.0,
        reason=BaselineReason.MATERIAL_CHANGED,
    )

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 3, 1), True)

    assert [m.date for m in roadmap.replan_marks] == [dt.date(2026, 2, 1)]
    assert roadmap.replan_marks[0].ratio == 0.2


def test_exam_roadmap_buffer_dates_only_include_buffer_day_type(db_session):
    """§0 U8：予備日（UI-07）は資格試験目標が対象（仕様書13.5、読書も対象）。"""
    goal = _make_goal(db_session)
    _make_subject(db_session, goal.id, dt.date(2026, 1, 5))
    db_session.add(CalendarDayOverride(target_date=dt.date(2026, 1, 3), day_type=DayType.BUFFER))
    db_session.commit()

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 1, 1), True)

    assert dt.date(2026, 1, 3) in roadmap.buffer_dates


def test_exam_roadmap_feedback_marks_from_assistant_messages(db_session):
    """§4共通：AIフィードバックを受けた日が道標として含まれる。"""
    goal = _make_goal(db_session)
    _add_feedback_message(db_session, goal.id, dt.date(2026, 1, 5))

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 1, 10), True)

    assert roadmap.feedback_marks == [dt.date(2026, 1, 5)]


def test_exam_roadmap_has_no_feedback_marks_when_no_history(db_session):
    """§0 要件6：AI未設定・フィードバック履歴が無い場合は道標なしで成立する。"""
    goal = _make_goal(db_session)

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 1, 10), True)

    assert roadmap.feedback_marks == []


def test_exam_roadmap_extends_past_due_date_when_overdue(db_session):
    """境界ケース：ゴール超過（教材の締切・受験日を過ぎてもクラッシュせず延長する）。"""
    goal = _make_goal(db_session)
    _make_subject(db_session, goal.id, dt.date(2026, 1, 10))
    material = _make_material(db_session, goal.id, dt.date(2026, 1, 1), dt.date(2026, 1, 9))
    _add_study_log(db_session, material.id, dt.date(2026, 1, 15), 50.0)

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 1, 20), True)

    assert roadmap.actual_points[-1].date == dt.date(2026, 1, 20)
    assert roadmap.actual_points[-1].ratio == 0.5


def test_exam_roadmap_replan_marks_skip_material_with_zero_total_work(db_session):
    """_replan_marksの防御分岐：total_work<=0の教材（量未設定）は目印から除外する。"""
    goal = _make_goal(db_session)
    _make_subject(db_session, goal.id, dt.date(2026, 6, 1))
    material = _make_material(
        db_session, goal.id, dt.date(2026, 1, 1), dt.date(2026, 5, 31), total_amount=0.0
    )
    _add_baseline(
        db_session,
        material.id,
        dt.date(2026, 2, 1),
        quota=0,
        remaining_at_baseline=0.0,
        reason=BaselineReason.MATERIAL_CHANGED,
    )

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 3, 1), True)

    assert roadmap.replan_marks == []


def test_exam_roadmap_handles_archived_goal_status_without_crashing(db_session):
    """状態の一貫性：archived_at設定済み・CLOSED_WITH_RESULTでもクラッシュしない。"""
    goal = _make_goal(
        db_session,
        status=GoalStatus.CLOSED_WITH_RESULT,
        archived_at=dt.datetime(2026, 2, 1, 0, 0, 0),
    )
    _make_subject(db_session, goal.id, dt.date(2026, 1, 5))

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 2, 10), True)

    assert roadmap.category == GoalCategory.EXAM


# --- READING ---


def test_reading_roadmap_with_no_book_does_not_crash(db_session):
    """境界ケース：記録0件（書籍未登録の下書き中の目標）。"""
    goal = _make_goal(db_session, category=GoalCategory.READING, status=GoalStatus.DRAFT)

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 1, 10), True)

    assert roadmap.category == GoalCategory.READING
    assert roadmap.progress_ratio == 0.0
    assert roadmap.is_achieved is False
    assert roadmap.planned_points == []
    assert roadmap.footprint_dates == []
    assert roadmap.replan_marks == []
    assert roadmap.buffer_dates == []
    assert roadmap.overrun_days is None


def _make_book(db_session, goal_id, start_date, due_date, total_pages=200) -> Book:
    book = Book(
        goal_id=goal_id,
        title="テスト書籍",
        total_pages=total_pages,
        start_date=start_date,
        due_date=due_date,
    )
    db_session.add(book)
    db_session.flush()
    return book


def _add_reading_log(db_session, book_id, record_date, current_page) -> None:
    record = _get_or_create_record(db_session, record_date)
    db_session.add(
        ReadingLog(
            daily_record_id=record.id,
            book_id=book_id,
            recall_body="想起内容",
            current_page=current_page,
        )
    )
    db_session.flush()


def test_reading_roadmap_footprint_for_page_not_entered_day(db_session):
    """§0 要件：ページ未入力の記録日は足跡として置く。"""
    goal = _make_goal(db_session, category=GoalCategory.READING)
    book = _make_book(db_session, goal.id, dt.date(2026, 1, 1), dt.date(2026, 3, 1))
    _add_reading_log(db_session, book.id, dt.date(2026, 1, 5), current_page=20)
    _add_reading_log(db_session, book.id, dt.date(2026, 1, 6), current_page=None)

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 1, 10), True)

    assert [p.date for p in roadmap.actual_points] == [dt.date(2026, 1, 5)]
    assert roadmap.actual_points[0].ratio == 0.1
    assert [f.date for f in roadmap.footprint_dates] == [dt.date(2026, 1, 6)]
    assert roadmap.footprint_dates[0].has_input is False


def test_reading_roadmap_progress_100_percent_when_current_page_reaches_total(db_session):
    """境界ケース：進捗100%（現在ページ＝総ページ数）。"""
    goal = _make_goal(db_session, category=GoalCategory.READING)
    book = _make_book(
        db_session, goal.id, dt.date(2026, 1, 1), dt.date(2026, 3, 1), total_pages=100
    )
    _add_reading_log(db_session, book.id, dt.date(2026, 2, 1), current_page=100)

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 2, 5), True)

    assert roadmap.progress_ratio == 1.0
    assert roadmap.is_achieved is True


def test_reading_roadmap_planned_points_stay_at_1_past_goal_date(db_session):
    """境界ケース：ゴール当日・ゴール超過でも計画線がクラッシュせず1.0のまま延長する。"""
    goal = _make_goal(db_session, category=GoalCategory.READING)
    _make_book(db_session, goal.id, dt.date(2026, 1, 1), dt.date(2026, 1, 10))

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 1, 15), True)

    assert roadmap.planned_points[-1].date == dt.date(2026, 1, 15)
    assert roadmap.planned_points[-1].ratio == 1.0
    on_goal_date = next(p for p in roadmap.planned_points if p.date == dt.date(2026, 1, 10))
    assert on_goal_date.ratio == 1.0


def test_reading_roadmap_has_no_schedule_status_or_replan_marks(db_session):
    """§0 U7・U10：読書は進捗状態の新設・道の引き直し目印とも対象外。"""
    goal = _make_goal(db_session, category=GoalCategory.READING)
    _make_book(db_session, goal.id, dt.date(2026, 1, 1), dt.date(2026, 3, 1))

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 1, 10), True)

    assert roadmap.replan_marks == []
    assert roadmap.overrun_days is None


def test_reading_roadmap_buffer_dates_included(db_session):
    """§0 U8訂正（2026-10-30）：予備日（UI-07）は仕様書13.5のとおり読書目標も対象。"""
    goal = _make_goal(db_session, category=GoalCategory.READING)
    _make_book(db_session, goal.id, dt.date(2026, 1, 1), dt.date(2026, 3, 1))
    db_session.add(CalendarDayOverride(target_date=dt.date(2026, 1, 3), day_type=DayType.BUFFER))
    db_session.commit()

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 1, 1), True)

    assert dt.date(2026, 1, 3) in roadmap.buffer_dates


# --- WORK ---


def _make_work_assignment(db_session, goal_id, start_date=dt.date(2026, 1, 1)) -> WorkAssignment:
    assignment = WorkAssignment(
        goal_id=goal_id, expected_content="案件内容", start_date=start_date
    )
    db_session.add(assignment)
    db_session.flush()
    return assignment


def _add_work_log(db_session, work_assignment_id, record_date) -> None:
    record = _get_or_create_record(db_session, record_date)
    db_session.add(
        WorkLog(daily_record_id=record.id, work_assignment_id=work_assignment_id, body="業務内容")
    )
    db_session.flush()


def test_work_roadmap_with_no_assignment_does_not_crash(db_session):
    """境界ケース：記録0件（案件情報未登録の下書き中の目標）。"""
    goal = _make_goal(db_session, category=GoalCategory.WORK, status=GoalStatus.DRAFT)

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 4, 1), True)

    assert roadmap.category == GoalCategory.WORK
    assert roadmap.footprint_dates == []
    assert roadmap.planned_points == []
    assert roadmap.actual_points == []
    assert roadmap.replan_marks == []
    assert roadmap.buffer_dates == []
    assert roadmap.overrun_days is None


def test_work_roadmap_period_is_current_semiannual_range(db_session):
    """§0 U9：道の起点・終点は現評価期間（H1=3〜8月）。"""
    goal = _make_goal(db_session, category=GoalCategory.WORK)
    _make_work_assignment(db_session, goal.id)

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 4, 1), True)

    assert roadmap.start_date == dt.date(2026, 3, 1)
    assert roadmap.goal_date == dt.date(2026, 8, 31)


def test_work_roadmap_footprints_are_recorded_days_within_period(db_session):
    """§0 要件：記録した日を足跡として積み上げる。"""
    goal = _make_goal(db_session, category=GoalCategory.WORK)
    assignment = _make_work_assignment(db_session, goal.id)
    _add_work_log(db_session, assignment.id, dt.date(2026, 4, 5))
    _add_work_log(db_session, assignment.id, dt.date(2026, 4, 6))

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 4, 10), True)

    assert [f.date for f in roadmap.footprint_dates] == [dt.date(2026, 4, 5), dt.date(2026, 4, 6)]
    assert all(f.has_input for f in roadmap.footprint_dates)


def test_work_roadmap_is_achieved_on_the_last_day_of_the_period(db_session):
    """境界ケース：ゴール当日（評価期間の最終日）は達成扱い。"""
    goal = _make_goal(db_session, category=GoalCategory.WORK)
    _make_work_assignment(db_session, goal.id)

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 8, 31), True)

    assert roadmap.progress_ratio == 1.0
    assert roadmap.is_achieved is True


def test_work_roadmap_has_no_planned_or_actual_points(db_session):
    """§0 U17：仕事目標には進捗量の概念が無いため計画線・実績線を描かない。"""
    goal = _make_goal(db_session, category=GoalCategory.WORK)
    _make_work_assignment(db_session, goal.id)

    roadmap = roadmap_service.get_roadmap(db_session, goal, dt.date(2026, 4, 1), True)

    assert roadmap.planned_points == []
    assert roadmap.actual_points == []


# --- resolve_work_period / compute_elapsed_ratio ---


def test_compute_elapsed_ratio_clamps_between_0_and_1():
    assert roadmap_service.compute_elapsed_ratio(
        dt.date(2026, 3, 1), dt.date(2026, 8, 31), dt.date(2026, 3, 1)
    ) == 0.0
    assert roadmap_service.compute_elapsed_ratio(
        dt.date(2026, 3, 1), dt.date(2026, 8, 31), dt.date(2026, 8, 31)
    ) == 1.0


def test_compute_elapsed_ratio_handles_zero_length_period():
    same_day = dt.date(2026, 1, 1)
    assert roadmap_service.compute_elapsed_ratio(same_day, same_day, same_day) == 1.0


# --- 内部ヘルパーの防御分岐（date_from > date_to・空系列等） ---


def test_date_range_returns_empty_when_from_is_after_to():
    assert roadmap_service._date_range(dt.date(2026, 1, 2), dt.date(2026, 1, 1)) == []


def test_ratio_series_returns_empty_when_total_work_is_zero():
    assert (
        roadmap_service._ratio_series([], 0.0, dt.date(2026, 1, 1), dt.date(2026, 1, 5)) == {}
    )


def test_extend_to_range_pads_zero_before_first_and_holds_after_last():
    series = {dt.date(2026, 1, 3): 0.5, dt.date(2026, 1, 4): 0.8}

    extended = roadmap_service._extend_to_range(series, dt.date(2026, 1, 1), dt.date(2026, 1, 6))

    assert extended[dt.date(2026, 1, 1)] == 0.0
    assert extended[dt.date(2026, 1, 2)] == 0.0
    assert extended[dt.date(2026, 1, 3)] == 0.5
    assert extended[dt.date(2026, 1, 4)] == 0.8
    assert extended[dt.date(2026, 1, 5)] == 0.8
    assert extended[dt.date(2026, 1, 6)] == 0.8


def test_extend_to_range_returns_all_zero_when_series_is_empty():
    extended = roadmap_service._extend_to_range({}, dt.date(2026, 1, 1), dt.date(2026, 1, 2))

    assert extended == {dt.date(2026, 1, 1): 0.0, dt.date(2026, 1, 2): 0.0}
