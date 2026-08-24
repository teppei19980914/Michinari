"""ai_context_service のテスト（ロジック・プロンプト編17.2〜17.4、実装フェーズ分割計画書Phase5）。

どのAIプロンプトへ渡す文言もPhase2〜4の既存算出ロジックの組み合わせであるため、
ここでは「必要な情報が文言に含まれているか」を中心に検証し、算出式自体の正しさは
各サービスの既存テスト（test_speed_service.py等）に委ねる（DRYの原則）。
"""

import datetime as dt

from app.constants.enums import (
    Environment,
    ExamDateType,
    GoalStatus,
    QualityMetricType,
    RecordState,
)
from app.models.goal import ExamSubject, Goal
from app.models.material import Material
from app.models.record import DailyRecord, StudyLog, WeeklySummary
from app.models.resource import ResourceSlot, ResourceSlotWeekday
from app.services import ai_context_service
from app.services.record_service import StudyLogItem


def _make_goal(session, name="目標A", status=GoalStatus.ACTIVE, resource_ratio=1.0):
    goal = Goal(
        name=name, start_date=dt.date(2026, 1, 1), status=status, resource_ratio=resource_ratio
    )
    session.add(goal)
    session.flush()
    return goal


def _make_subject(session, goal, **overrides):
    defaults = dict(
        goal_id=goal.id,
        name="午前科目",
        exam_date_type=ExamDateType.FIXED,
        exam_date_fixed=dt.date(2026, 12, 1),
        display_order=1,
    )
    defaults.update(overrides)
    subject = ExamSubject(**defaults)
    session.add(subject)
    session.flush()
    return subject


def _make_material(session, goal, **overrides):
    defaults = dict(
        goal_id=goal.id,
        name="教材A",
        unit_label="ページ",
        total_amount=100.0,
        planned_cycles=1,
        start_date=dt.date(2026, 1, 1),
        due_date=dt.date(2026, 11, 30),
        quality_metric_type=QualityMetricType.NONE,
        display_order=1,
    )
    defaults.update(overrides)
    material = Material(**defaults)
    session.add(material)
    session.flush()
    return material


def _make_slot(session, start_time, end_time, weekdays, environment=Environment.ANY):
    slot = ResourceSlot(
        name="スロット",
        start_time=start_time,
        end_time=end_time,
        environment=environment,
        display_order=1,
    )
    session.add(slot)
    session.flush()
    for weekday in weekdays:
        session.add(ResourceSlotWeekday(slot_id=slot.id, weekday=weekday))
    session.flush()
    return slot


def _make_daily_record(session, record_date, state=RecordState.REPORTED, **overrides):
    defaults = dict(record_date=record_date, record_state=state)
    defaults.update(overrides)
    record = DailyRecord(**defaults)
    session.add(record)
    session.flush()
    return record


def _make_study_log(session, daily_record, material, **overrides):
    defaults = dict(
        daily_record_id=daily_record.id,
        material_id=material.id,
        minutes_spent=30,
        amount_completed=10.0,
        cycle_number=1,
        quality_value=None,
    )
    defaults.update(overrides)
    log = StudyLog(**defaults)
    session.add(log)
    session.flush()
    return log


# --- list_active_goals / list_active_materials ---


def test_list_active_goals_excludes_non_active(seeded_session):
    active = _make_goal(seeded_session, name="進行中", status=GoalStatus.ACTIVE)
    _make_goal(seeded_session, name="下書き", status=GoalStatus.DRAFT)

    result = ai_context_service.list_active_goals(seeded_session)

    assert [g.id for g in result] == [active.id]


def test_list_active_materials_excludes_inactive(seeded_session):
    goal = _make_goal(seeded_session)
    active_material = _make_material(seeded_session, goal, name="有効教材")
    _make_material(seeded_session, goal, name="無効教材", is_active=False, display_order=2)

    result = ai_context_service.list_active_materials([goal])

    assert [m.id for m in result] == [active_material.id]


# --- build_goal_summary ---


def test_build_goal_summary_includes_subject_and_days_remaining(seeded_session):
    goal = _make_goal(seeded_session, name="基本情報技術者")
    _make_subject(seeded_session, goal, name="午前", exam_date_fixed=dt.date(2026, 9, 3))

    text = ai_context_service.build_goal_summary([goal], today=dt.date(2026, 8, 24))

    assert "基本情報技術者" in text
    assert "午前" in text
    assert "2026-09-03" in text
    assert "残り10日" in text


def test_build_goal_summary_empty_when_no_active_goals():
    text = ai_context_service.build_goal_summary([], today=dt.date(2026, 8, 24))
    assert "進行中の目標はありません" in text


# --- build_material_status_entries ---


def test_build_material_status_entries_includes_core_numbers(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal, name="過去問道場", total_amount=200.0)
    record = _make_daily_record(seeded_session, dt.date(2026, 8, 20))
    _make_study_log(seeded_session, record, material, amount_completed=50.0)

    entries = ai_context_service.build_material_status_entries(
        seeded_session, [material], today=dt.date(2026, 8, 24), treat_holiday_as_buffer=True
    )

    assert len(entries) == 1
    text = entries[0].text
    assert "過去問道場" in text
    assert "残量" in text
    assert "締切" in text
    assert "日次ノルマ" in text


def test_build_material_status_entries_includes_forecast_when_computable(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(
        seeded_session, goal, name="過去問道場", total_amount=100.0, due_date=dt.date(2027, 12, 31)
    )
    # 現在周回のサンプルを3件以上用意し、実効速度・完了予測日が算出可能な状態にする
    # （ロジック・プロンプト編8.2・8.5）。
    for day in (18, 19, 20):
        record = _make_daily_record(seeded_session, dt.date(2026, 8, day))
        _make_study_log(
            seeded_session, record, material, amount_completed=10.0, minutes_spent=60
        )
    monday = dt.date(2026, 8, 24)
    _make_slot(seeded_session, dt.time(19, 0), dt.time(21, 0), weekdays=list(range(7)))

    entries = ai_context_service.build_material_status_entries(
        seeded_session, [material], today=monday, treat_holiday_as_buffer=True
    )

    assert "完了予測日 2026-" in entries[0].text


# --- build_slot_summary ---


def test_build_slot_summary_reports_no_slots_when_none_active(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)

    text = ai_context_service.build_slot_summary(
        seeded_session, [material], today=dt.date(2026, 8, 24)
    )

    assert "本日利用可能なスロットはありません" in text


def test_build_slot_summary_allocates_hours_to_material(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    monday = dt.date(2026, 8, 24)  # 2026-08-24は月曜日
    _make_slot(seeded_session, dt.time(20, 0), dt.time(22, 0), weekdays=[monday.weekday()])

    text = ai_context_service.build_slot_summary(seeded_session, [material], today=monday)

    assert "総利用可能時間: 2.0時間" in text
    assert material.name in text


def test_build_slot_summary_omits_material_with_no_allocated_hours(seeded_session):
    goal = _make_goal(seeded_session)
    matched = _make_material(
        seeded_session, goal, name="PC教材", required_environment=Environment.PC
    )
    unmatched = _make_material(
        seeded_session,
        goal,
        name="モバイル教材",
        required_environment=Environment.MOBILE,
        display_order=2,
    )
    monday = dt.date(2026, 8, 24)
    _make_slot(
        seeded_session,
        dt.time(20, 0),
        dt.time(22, 0),
        weekdays=[monday.weekday()],
        environment=Environment.PC,
    )

    text = ai_context_service.build_slot_summary(
        seeded_session, [matched, unmatched], today=monday
    )

    assert matched.name in text
    assert unmatched.name not in text


# --- build_buffer_usage_rate_text ---


def test_build_buffer_usage_rate_text_reports_unavailable_before_start_date(seeded_session):
    goal = _make_goal(seeded_session)

    text = ai_context_service.build_buffer_usage_rate_text(
        seeded_session, [goal], today=goal.start_date, treat_holiday_as_buffer=True
    )

    assert "算出不可" in text


def test_build_buffer_usage_rate_text_empty_when_no_goals(seeded_session):
    text = ai_context_service.build_buffer_usage_rate_text(
        seeded_session, [], dt.date(2026, 8, 24), True
    )
    assert "進行中の目標はありません" in text


# --- build_today_logs_text ---


def test_build_today_logs_text_formats_each_entry(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    items = [
        StudyLogItem(
            material_id=material.id,
            minutes_spent=45,
            amount_completed=12.5,
            cycle_number=2,
            quality_value=80.0,
        )
    ]
    materials_by_id = {material.id: material}

    text = ai_context_service.build_today_logs_text(items, materials_by_id)

    assert material.name in text
    assert "45分" in text
    assert "2周目" in text
    assert "品質指標 80.0" in text


def test_build_today_logs_text_empty_when_no_items():
    text = ai_context_service.build_today_logs_text([], {})
    assert "本日の実績入力はまだありません" in text


# --- build_progress_summary / build_recent_activity_text ---


def test_build_progress_summary_includes_current_cycle(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal, total_amount=100.0, planned_cycles=2)
    record = _make_daily_record(seeded_session, dt.date(2026, 8, 20))
    _make_study_log(seeded_session, record, material, amount_completed=100.0)

    text = ai_context_service.build_progress_summary(seeded_session, [material])

    assert material.name in text
    assert "現在2周目" in text


def test_build_recent_activity_text_lists_recent_records(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    record = _make_daily_record(seeded_session, dt.date(2026, 8, 23))
    _make_study_log(seeded_session, record, material, amount_completed=5.0)

    text = ai_context_service.build_recent_activity_text(
        seeded_session, [goal], today=dt.date(2026, 8, 24)
    )

    assert "2026-08-23" in text
    assert "報告済み" in text


# --- build_recent_weekly_summaries ---


def test_build_recent_weekly_summaries_orders_newest_first_and_respects_limit(seeded_session):
    goal = _make_goal(seeded_session)
    for week_start in (dt.date(2026, 7, 6), dt.date(2026, 7, 13), dt.date(2026, 7, 20)):
        seeded_session.add(
            WeeklySummary(
                goal_id=goal.id,
                week_start_date=week_start,
                week_end_date=week_start + dt.timedelta(days=6),
                summary_body=f"{week_start.isoformat()}の要約",
            )
        )
    seeded_session.flush()

    result = ai_context_service.build_recent_weekly_summaries(
        seeded_session, [goal], inject_weeks=2
    )

    assert len(result) == 2
    assert "2026-07-20" in result[0]
    assert "2026-07-13" in result[1]


def test_build_recent_weekly_summaries_empty_when_no_goals(seeded_session):
    result = ai_context_service.build_recent_weekly_summaries(seeded_session, [], inject_weeks=4)
    assert result == []


# --- build_week_logs_text / build_week_diaries_text / build_week_metrics_text ---


def test_build_week_logs_text_lists_entries_within_range(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    record = _make_daily_record(seeded_session, dt.date(2026, 7, 8))
    _make_study_log(seeded_session, record, material, amount_completed=15.0, cycle_number=1)

    text = ai_context_service.build_week_logs_text(
        seeded_session, goal, week_start=dt.date(2026, 7, 6), week_end=dt.date(2026, 7, 12)
    )

    assert "2026-07-08" in text
    assert material.name in text


def test_build_week_logs_text_empty_when_goal_has_no_materials(seeded_session):
    goal = _make_goal(seeded_session)

    text = ai_context_service.build_week_logs_text(
        seeded_session, goal, week_start=dt.date(2026, 7, 6), week_end=dt.date(2026, 7, 12)
    )

    assert "対象教材はありません" in text


def test_build_week_logs_text_reports_no_logs_when_material_exists_without_records(
    seeded_session,
):
    goal = _make_goal(seeded_session)
    _make_material(seeded_session, goal)

    text = ai_context_service.build_week_logs_text(
        seeded_session, goal, week_start=dt.date(2026, 7, 6), week_end=dt.date(2026, 7, 12)
    )

    assert "この週の実績はありません" in text


def test_build_week_diaries_text_empty_when_no_reported_days(seeded_session):
    text = ai_context_service.build_week_diaries_text(
        seeded_session, week_start=dt.date(2026, 7, 6), week_end=dt.date(2026, 7, 12)
    )

    assert "この週の日記はありません" in text


def test_build_week_diaries_text_includes_only_reported_days(seeded_session):
    _make_daily_record(
        seeded_session,
        dt.date(2026, 7, 8),
        state=RecordState.REPORTED,
        diary_body="今日は集中できた",
        diary_learned="ネットワークの基礎",
    )
    _make_daily_record(seeded_session, dt.date(2026, 7, 9), state=RecordState.PROGRESS_ONLY)

    text = ai_context_service.build_week_diaries_text(
        seeded_session, week_start=dt.date(2026, 7, 6), week_end=dt.date(2026, 7, 12)
    )

    assert "今日は集中できた" in text
    assert "2026-07-09" not in text


def test_build_week_metrics_text_summarizes_week(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal, quality_metric_type=QualityMetricType.OBJECTIVE)
    record = _make_daily_record(seeded_session, dt.date(2026, 7, 8))
    _make_study_log(
        seeded_session, record, material, minutes_spent=60, amount_completed=20.0,
        quality_value=90.0,
    )

    text = ai_context_service.build_week_metrics_text(
        seeded_session, goal, week_start=dt.date(2026, 7, 6), week_end=dt.date(2026, 7, 12),
        treat_holiday_as_buffer=True,
    )

    assert "総投下時間: 1.0時間" in text
    assert "総完了量: 20.0" in text
    assert "報告日数: 1日" in text
