"""ai_context_service のテスト（ロジック・プロンプト編17.2〜17.4、実装フェーズ分割計画書Phase5）。

どのAIプロンプトへ渡す文言もPhase2〜4の既存算出ロジックの組み合わせであるため、
ここでは「必要な情報が文言に含まれているか」を中心に検証し、算出式自体の正しさは
各サービスの既存テスト（test_speed_service.py等）に委ねる（DRYの原則）。
"""

import datetime as dt

import pytest

from app.constants.enums import (
    BaselineReason,
    Environment,
    ExamDateType,
    ExamResultType,
    GoalCategory,
    GoalStatus,
    QualityMetricType,
    RecordState,
    RetrospectivePeriodType,
)
from app.models.goal import ExamSubject, Goal
from app.models.material import Material, PlanBaseline
from app.models.record import (
    DailyGoalDiary,
    DailyRecord,
    ExamResult,
    ReadingLog,
    StudyLog,
    WeeklySummary,
    WorkLog,
)
from app.models.resource import ResourceSlot, ResourceSlotWeekday
from app.models.retrospective import GoalRetrospective
from app.models.work import WorkAssignment
from app.services import ai_context_service
from app.services.record_service import DiaryEntryItem, ReadingLogItem, StudyLogItem, WorkLogItem
from tests import allocation_helpers, reading_helpers


def _make_goal(session, name="目標A", status=GoalStatus.ACTIVE):
    goal = Goal(name=name, start_date=dt.date(2026, 1, 1), status=status)
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
    defaults = dict(record_date=record_date, exam_record_state=state)
    defaults.update(overrides)
    record = DailyRecord(**defaults)
    session.add(record)
    session.flush()
    return record


def _make_diary_entry(session, daily_record, goal, **overrides):
    defaults = dict(daily_record_id=daily_record.id, goal_id=goal.id)
    defaults.update(overrides)
    entry = DailyGoalDiary(**defaults)
    session.add(entry)
    session.flush()
    return entry


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


# --- build_diary_text ---


def test_build_diary_text_returns_raw_text_for_single_goal(seeded_session):
    """1目標のみのときは見出しを付けず、既存の単一目標運用時の出力を変えない。"""
    goal = _make_goal(seeded_session, name="目標A")
    entries = [DiaryEntryItem(goal_id=goal.id, diary_body="今日は頑張った", diary_learned="学び")]

    diary_body, diary_learned = ai_context_service.build_diary_text(entries, [goal])

    assert diary_body == "今日は頑張った"
    assert diary_learned == "学び"


def test_build_diary_text_groups_by_goal_when_multiple_goals_have_content(seeded_session):
    goal_a = _make_goal(seeded_session, name="目標A")
    goal_b = _make_goal(seeded_session, name="目標B")
    entries = [
        DiaryEntryItem(goal_id=goal_a.id, diary_body="Aの所感", diary_learned="Aの学び"),
        DiaryEntryItem(goal_id=goal_b.id, diary_body="Bの所感", diary_learned="Bの学び"),
    ]

    diary_body, diary_learned = ai_context_service.build_diary_text(entries, [goal_a, goal_b])

    assert "■ 目標A" in diary_body
    assert "Aの所感" in diary_body
    assert "■ 目標B" in diary_body
    assert "Bの所感" in diary_body
    assert "■ 目標A" in diary_learned
    assert "Aの学び" in diary_learned


def test_build_diary_text_excludes_goals_with_empty_content(seeded_session):
    goal_a = _make_goal(seeded_session, name="目標A")
    goal_b = _make_goal(seeded_session, name="目標B")
    entries = [
        DiaryEntryItem(goal_id=goal_a.id, diary_body="Aの所感", diary_learned=""),
        DiaryEntryItem(goal_id=goal_b.id, diary_body="", diary_learned=""),
    ]

    diary_body, diary_learned = ai_context_service.build_diary_text(entries, [goal_a, goal_b])

    assert diary_body == "Aの所感"
    assert diary_learned == ""


def test_build_diary_text_empty_when_no_entries():
    diary_body, diary_learned = ai_context_service.build_diary_text([], [])
    assert diary_body == ""
    assert diary_learned == ""


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


def test_build_material_status_entries_excludes_not_yet_started_material(seeded_session):
    """開始日が本日より後の教材は、現在の学習スコープ外としてAIへの状況出力から除外する
    （quota_serviceが日次ノルマを一貫して0とする対象と同じ教材。含めるとAIが未着手の
    教材へ不適切に言及・提案してしまう）。"""
    goal = _make_goal(seeded_session)
    started = _make_material(seeded_session, goal, name="午前対策", start_date=dt.date(2026, 1, 1))
    not_started = _make_material(
        seeded_session,
        goal,
        name="午後過去問",
        start_date=dt.date(2026, 10, 28),
        display_order=2,
    )

    entries = ai_context_service.build_material_status_entries(
        seeded_session,
        [started, not_started],
        today=dt.date(2026, 8, 24),
        treat_holiday_as_buffer=True,
    )

    assert len(entries) == 1
    assert "午前対策" in entries[0].text
    assert "午後過去問" not in entries[0].text


def test_build_material_status_entries_includes_forecast_when_computable(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(
        seeded_session, goal, name="過去問道場", total_amount=100.0, due_date=dt.date(2027, 12, 31)
    )
    # 現在周回のサンプルを3件以上用意し、実効速度・完了予測日が算出可能な状態にする
    # （ロジック・プロンプト編8.2・8.5）。
    for day in (18, 19, 20):
        record = _make_daily_record(seeded_session, dt.date(2026, 8, day))
        _make_study_log(seeded_session, record, material, amount_completed=10.0, minutes_spent=60)
    monday = dt.date(2026, 8, 24)
    slot = _make_slot(seeded_session, dt.time(19, 0), dt.time(21, 0), weekdays=list(range(7)))
    allocation_helpers.allocate_full(seeded_session, goal.id, slot)

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
    slot = _make_slot(seeded_session, dt.time(20, 0), dt.time(22, 0), weekdays=[monday.weekday()])
    allocation_helpers.allocate_full(seeded_session, goal.id, slot)

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
    slot = _make_slot(
        seeded_session,
        dt.time(20, 0),
        dt.time(22, 0),
        weekdays=[monday.weekday()],
        environment=Environment.PC,
    )
    allocation_helpers.allocate_full(seeded_session, goal.id, slot)

    text = ai_context_service.build_slot_summary(seeded_session, [matched, unmatched], today=monday)

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
            slot_minutes={1: 45},
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

    text = ai_context_service.build_progress_summary(
        seeded_session, [material], today=dt.date(2026, 8, 24)
    )

    assert material.name in text
    assert "現在2周目" in text


def test_build_progress_summary_excludes_not_yet_started_material(seeded_session):
    """開始日が本日より後の教材は、現在の学習スコープ外として「今日の一言」向けの
    進捗要約からも除外する（build_material_status_entriesと同じ判定基準）。"""
    goal = _make_goal(seeded_session)
    started = _make_material(seeded_session, goal, name="午前対策", start_date=dt.date(2026, 1, 1))
    not_started = _make_material(
        seeded_session,
        goal,
        name="午後過去問",
        start_date=dt.date(2026, 10, 28),
        display_order=2,
    )

    text = ai_context_service.build_progress_summary(
        seeded_session, [started, not_started], today=dt.date(2026, 8, 24)
    )

    assert "午前対策" in text
    assert "午後過去問" not in text


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


def test_build_recent_activity_text_excludes_other_goals_activity(seeded_session):
    """複数目標が同時進行している場合、渡された目標以外の実績が混入しないこと
    （未決事項L-04関連。「今日の一言」の目標別独立生成に必須）。"""
    goal_a = _make_goal(seeded_session, name="目標A")
    goal_b = _make_goal(seeded_session, name="目標B")
    material_a = _make_material(seeded_session, goal_a)
    material_b = _make_material(seeded_session, goal_b)
    record = _make_daily_record(seeded_session, dt.date(2026, 8, 23))
    _make_study_log(seeded_session, record, material_a, amount_completed=5.0)
    _make_study_log(seeded_session, record, material_b, amount_completed=100.0)

    text = ai_context_service.build_recent_activity_text(
        seeded_session, [goal_a], today=dt.date(2026, 8, 24)
    )

    assert "完了量計 5.0" in text
    assert "100.0" not in text


def test_build_recent_activity_text_empty_when_goals_have_no_materials(seeded_session):
    goal = _make_goal(seeded_session)
    text = ai_context_service.build_recent_activity_text(
        seeded_session, [goal], today=dt.date(2026, 8, 24)
    )
    assert "対象教材はありません" in text


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


# --- resolve_weekly_compressed_period／exclude_covered_dates（L-11、2026-09-16是正） ---


def _add_weekly_summary(session, goal, week_start, *, summary_body=None, is_anonymized=False):
    week_end = week_start + dt.timedelta(days=6)
    session.add(
        WeeklySummary(
            goal_id=goal.id,
            week_start_date=week_start,
            week_end_date=week_end,
            summary_body=summary_body or f"{week_start.isoformat()}の要約",
            is_anonymized=is_anonymized,
        )
    )
    session.flush()
    return week_end


def test_resolve_weekly_compressed_period_no_summaries_returns_empty(seeded_session):
    goal = _make_goal(seeded_session)

    result = ai_context_service.resolve_weekly_compressed_period(
        seeded_session, goal, period_start=dt.date(2026, 7, 6), period_end=dt.date(2026, 7, 26)
    )

    assert result.weekly_summary_entries == []
    assert result.covered_ranges == []


def test_resolve_weekly_compressed_period_includes_all_weeks_fully_inside_period(seeded_session):
    """period_startが週境界（月曜）と一致しなくても、[period_start, period_end]に
    フル収容される週次要約はすべて圧縮対象とする（2026-09-16是正。旧実装はperiod_startと
    週開始日が完全一致する場合しか圧縮が発動しないバグがあった）。"""
    goal = _make_goal(seeded_session)
    _add_weekly_summary(seeded_session, goal, dt.date(2026, 7, 6))  # 7/6-7/12
    _add_weekly_summary(seeded_session, goal, dt.date(2026, 7, 13))  # 7/13-7/19

    # period_startを週開始日からわざと1日ずらす（火曜始まり）。
    result = ai_context_service.resolve_weekly_compressed_period(
        seeded_session, goal, period_start=dt.date(2026, 7, 1), period_end=dt.date(2026, 7, 26)
    )

    assert [entry.record_date for entry in result.weekly_summary_entries] == [
        dt.date(2026, 7, 6),
        dt.date(2026, 7, 13),
    ]
    assert result.covered_ranges == [
        (dt.date(2026, 7, 6), dt.date(2026, 7, 12)),
        (dt.date(2026, 7, 13), dt.date(2026, 7, 19)),
    ]


def test_resolve_weekly_compressed_period_includes_weeks_independently_across_a_gap(
    seeded_session,
):
    """途中に未生成の週（欠け）があっても、それより後ろの週次要約は独立して圧縮対象に
    含める（旧実装は欠けで以降すべて打ち切っていたが、生ログ側はexclude_covered_datesで
    日付単位に除外するため、打ち切る必要がない、2026-09-16是正）。"""
    goal = _make_goal(seeded_session)
    _add_weekly_summary(seeded_session, goal, dt.date(2026, 7, 6))  # 7/6-7/12
    # 7/13週は未生成（欠け）
    _add_weekly_summary(seeded_session, goal, dt.date(2026, 7, 20))  # 7/20-7/26

    result = ai_context_service.resolve_weekly_compressed_period(
        seeded_session, goal, period_start=dt.date(2026, 7, 6), period_end=dt.date(2026, 8, 2)
    )

    assert [entry.record_date for entry in result.weekly_summary_entries] == [
        dt.date(2026, 7, 6),
        dt.date(2026, 7, 20),
    ]
    assert result.covered_ranges == [
        (dt.date(2026, 7, 6), dt.date(2026, 7, 12)),
        (dt.date(2026, 7, 20), dt.date(2026, 7, 26)),
    ]


def test_resolve_weekly_compressed_period_excludes_weeks_not_fully_inside_period(seeded_session):
    """開始日がperiod_startより前、または終了日がperiod_endより後ろの週は、部分的にしか
    重ならないため圧縮対象から除外する（フル収容のみ対象、L-11）。"""
    goal = _make_goal(seeded_session)
    _add_weekly_summary(seeded_session, goal, dt.date(2026, 6, 22))  # 6/22-6/28、period_startより前
    _add_weekly_summary(seeded_session, goal, dt.date(2026, 7, 27))  # 7/27-8/2、period_endより後

    result = ai_context_service.resolve_weekly_compressed_period(
        seeded_session, goal, period_start=dt.date(2026, 7, 6), period_end=dt.date(2026, 7, 26)
    )

    assert result.weekly_summary_entries == []
    assert result.covered_ranges == []


def test_resolve_weekly_compressed_period_excludes_anonymized(seeded_session):
    goal = _make_goal(seeded_session)
    _add_weekly_summary(seeded_session, goal, dt.date(2026, 7, 6), is_anonymized=True)

    result = ai_context_service.resolve_weekly_compressed_period(
        seeded_session, goal, period_start=dt.date(2026, 7, 6), period_end=dt.date(2026, 7, 26)
    )

    assert result.weekly_summary_entries == []
    assert result.covered_ranges == []


def test_resolve_weekly_compressed_period_limit_keeps_most_recent_weeks_and_drops_oldest(
    seeded_session,
):
    """limit指定時は、period_end側に近い（新しい）方からlimit件までに絞り、古い方から
    溢れた分は圧縮対象から除外する（縮退の方向性＝直近の記憶を優先し遠い過去から
    削る、と同じ考え方をweekly_summariesの選定にも適用する、2026-09-16）。"""
    goal = _make_goal(seeded_session)
    for week_start in (dt.date(2026, 7, 6), dt.date(2026, 7, 13), dt.date(2026, 7, 20)):
        _add_weekly_summary(seeded_session, goal, week_start)

    result = ai_context_service.resolve_weekly_compressed_period(
        seeded_session,
        goal,
        period_start=dt.date(2026, 7, 6),
        period_end=dt.date(2026, 7, 26),
        limit=2,
    )

    # 新しい順に2件（7/13・7/20）を採用したのち、古い順へ並べ替える。7/6は溢れて除外。
    assert [entry.record_date for entry in result.weekly_summary_entries] == [
        dt.date(2026, 7, 13),
        dt.date(2026, 7, 20),
    ]
    assert result.covered_ranges == [
        (dt.date(2026, 7, 13), dt.date(2026, 7, 19)),
        (dt.date(2026, 7, 20), dt.date(2026, 7, 26)),
    ]


def test_exclude_covered_dates_removes_entries_within_ranges(seeded_session):
    entries = [
        ai_context_service.DatedLogEntry(record_date=dt.date(2026, 7, 6), text="7/6"),
        ai_context_service.DatedLogEntry(record_date=dt.date(2026, 7, 10), text="7/10"),
        ai_context_service.DatedLogEntry(record_date=dt.date(2026, 7, 15), text="7/15"),
    ]

    result = ai_context_service.exclude_covered_dates(
        entries, covered_ranges=[(dt.date(2026, 7, 6), dt.date(2026, 7, 12))]
    )

    assert [entry.record_date for entry in result] == [dt.date(2026, 7, 15)]


def test_exclude_covered_dates_returns_entries_unchanged_when_no_ranges(seeded_session):
    entries = [ai_context_service.DatedLogEntry(record_date=dt.date(2026, 7, 6), text="7/6")]

    result = ai_context_service.exclude_covered_dates(entries, covered_ranges=[])

    assert result == entries


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
    goal = _make_goal(seeded_session)

    text = ai_context_service.build_week_diaries_text(
        seeded_session, goal, week_start=dt.date(2026, 7, 6), week_end=dt.date(2026, 7, 12)
    )

    assert "この週の日記はありません" in text


def test_build_week_diaries_text_includes_only_reported_days(seeded_session):
    goal = _make_goal(seeded_session)
    record = _make_daily_record(seeded_session, dt.date(2026, 7, 8), state=RecordState.REPORTED)
    _make_diary_entry(
        seeded_session,
        record,
        goal,
        diary_body="今日は集中できた",
        diary_learned="ネットワークの基礎",
    )
    _make_daily_record(seeded_session, dt.date(2026, 7, 9), state=RecordState.PROGRESS_ONLY)

    text = ai_context_service.build_week_diaries_text(
        seeded_session, goal, week_start=dt.date(2026, 7, 6), week_end=dt.date(2026, 7, 12)
    )

    assert "今日は集中できた" in text
    assert "2026-07-09" not in text


def test_build_week_diaries_text_excludes_other_goals_diary(seeded_session):
    """複数目標が同時進行していた週に、他目標の日記が混入しないこと（未決事項L-04）。"""
    goal_a = _make_goal(seeded_session, name="目標A")
    goal_b = _make_goal(seeded_session, name="目標B")
    record = _make_daily_record(seeded_session, dt.date(2026, 7, 8), state=RecordState.REPORTED)
    _make_diary_entry(seeded_session, record, goal_a, diary_body="目標Aの日記")
    _make_diary_entry(seeded_session, record, goal_b, diary_body="目標Bの日記")

    text = ai_context_service.build_week_diaries_text(
        seeded_session, goal_a, week_start=dt.date(2026, 7, 6), week_end=dt.date(2026, 7, 12)
    )

    assert "目標Aの日記" in text
    assert "目標Bの日記" not in text


def test_build_week_metrics_text_summarizes_week(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal, quality_metric_type=QualityMetricType.OBJECTIVE)
    record = _make_daily_record(seeded_session, dt.date(2026, 7, 8))
    _make_study_log(
        seeded_session,
        record,
        material,
        minutes_spent=60,
        amount_completed=20.0,
        quality_value=90.0,
    )

    text = ai_context_service.build_week_metrics_text(
        seeded_session,
        goal,
        week_start=dt.date(2026, 7, 6),
        week_end=dt.date(2026, 7, 12),
        treat_holiday_as_buffer=True,
    )

    assert "総投下時間: 1.0時間" in text
    assert "総完了量: 20.0" in text
    assert "報告日数: 1日" in text


# --- 総括レポート向け（Phase10） ---


def test_build_material_summary_text_includes_totals_and_hours(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal, planned_cycles=2)
    record = _make_daily_record(seeded_session, dt.date(2026, 7, 8))
    _make_study_log(seeded_session, record, material, minutes_spent=60, amount_completed=100.0)

    text = ai_context_service.build_material_summary_text(seeded_session, [material])

    assert "教材A" in text
    assert "総量 100.0ページ × 2周" in text
    assert "実績 1周完了" in text
    assert "投下時間 1.0時間" in text


def test_build_material_summary_text_handles_no_materials():
    assert "対象教材はありません" in ai_context_service.build_material_summary_text(None, [])


def test_build_overall_metrics_text_summarizes_goal(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    record = _make_daily_record(seeded_session, dt.date(2026, 1, 1))
    _make_study_log(seeded_session, record, material, minutes_spent=90, amount_completed=10.0)

    text = ai_context_service.build_overall_metrics_text(
        seeded_session, goal, today=dt.date(2026, 1, 1), treat_holiday_as_buffer=True
    )

    assert "総投下時間: 1.5時間" in text
    assert "学習日数: 1日" in text
    assert "報告率: 100%" in text
    assert "リプラン回数: 0回" in text


def test_build_overall_metrics_text_handles_goal_without_materials(seeded_session):
    goal = _make_goal(seeded_session)

    text = ai_context_service.build_overall_metrics_text(
        seeded_session, goal, today=dt.date(2026, 1, 1), treat_holiday_as_buffer=True
    )

    assert "総投下時間: 0.0時間" in text


def test_build_quality_trend_text_groups_by_cycle_and_month(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal, quality_metric_type=QualityMetricType.OBJECTIVE)
    record = _make_daily_record(seeded_session, dt.date(2026, 1, 15))
    _make_study_log(seeded_session, record, material, cycle_number=1, quality_value=70.0)

    text = ai_context_service.build_quality_trend_text(seeded_session, [material])

    assert "教材A" in text
    assert "1周目" in text
    assert "70.0" in text


def test_build_quality_trend_text_handles_no_records(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)

    text = ai_context_service.build_quality_trend_text(seeded_session, [material])

    assert "品質指標の記録はありません" in text


def test_build_replan_history_text_shows_before_and_after_quota(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    seeded_session.add(
        PlanBaseline(
            material_id=material.id,
            effective_from=dt.date(2026, 1, 1),
            baseline_daily_quota=10.0,
            remaining_at_baseline=100.0,
            plan_days_at_baseline=10,
            planned_cycles_at_baseline=1,
            reason=BaselineReason.INITIAL,
        )
    )
    seeded_session.add(
        PlanBaseline(
            material_id=material.id,
            effective_from=dt.date(2026, 1, 5),
            baseline_daily_quota=15.0,
            remaining_at_baseline=80.0,
            plan_days_at_baseline=6,
            planned_cycles_at_baseline=1,
            reason=BaselineReason.REPLAN,
        )
    )
    seeded_session.flush()

    text = ai_context_service.build_replan_history_text(seeded_session, goal)

    assert "初期設定" in text
    assert "10.0（初期値）" in text
    assert "リプラン" in text
    assert "10.0→15.0" in text


def test_build_replan_history_text_handles_no_baselines(seeded_session):
    goal = _make_goal(seeded_session)

    text = ai_context_service.build_replan_history_text(seeded_session, goal)

    assert "計画基準値の記録はありません" in text


def test_build_exam_results_text_includes_registered_and_unregistered(seeded_session):
    goal = _make_goal(seeded_session)
    registered = _make_subject(seeded_session, goal, name="登録済み科目", display_order=1)
    _make_subject(seeded_session, goal, name="未登録科目", display_order=2)
    seeded_session.add(
        ExamResult(
            subject_id=registered.id,
            taken_date=dt.date(2026, 12, 1),
            result=ExamResultType.PASS,
            score=88.0,
        )
    )
    seeded_session.flush()
    seeded_session.refresh(registered)

    text = ai_context_service.build_exam_results_text(goal)

    assert "登録済み科目: 合格、得点 88.0" in text
    assert "未登録科目: 未登録" in text


def test_build_exam_results_text_handles_no_subjects(seeded_session):
    goal = _make_goal(seeded_session)

    text = ai_context_service.build_exam_results_text(goal)

    assert "試験科目未登録" in text


def test_build_all_weekly_summaries_entries_orders_chronologically(seeded_session):
    goal = _make_goal(seeded_session)
    seeded_session.add(
        WeeklySummary(
            goal_id=goal.id,
            week_start_date=dt.date(2026, 1, 12),
            week_end_date=dt.date(2026, 1, 18),
            summary_body="2週目",
        )
    )
    seeded_session.add(
        WeeklySummary(
            goal_id=goal.id,
            week_start_date=dt.date(2026, 1, 5),
            week_end_date=dt.date(2026, 1, 11),
            summary_body="1週目",
        )
    )
    seeded_session.flush()

    entries = ai_context_service.build_all_weekly_summaries_entries(seeded_session, goal)

    assert [entry.record_date for entry in entries] == [dt.date(2026, 1, 5), dt.date(2026, 1, 12)]
    text = "\n\n".join(entry.text for entry in entries)
    assert text.index("1週目") < text.index("2週目")


def test_build_all_weekly_summaries_entries_handles_no_summaries(seeded_session):
    goal = _make_goal(seeded_session)

    entries = ai_context_service.build_all_weekly_summaries_entries(seeded_session, goal)

    assert entries == []


def test_build_anonymize_instruction_empty_when_not_anonymizing():
    assert ai_context_service.build_anonymize_instruction(False) == ""


def test_build_anonymize_instruction_returns_text_when_anonymizing():
    text = ai_context_service.build_anonymize_instruction(True)

    assert "匿名化" in text


@pytest.mark.parametrize("category", [GoalCategory.EXAM, GoalCategory.READING, GoalCategory.WORK])
def test_build_perspective_suggestion_instruction_empty_when_above_threshold(category):
    assert ai_context_service.build_perspective_suggestion_instruction(category, False) == ""


@pytest.mark.parametrize("category", [GoalCategory.EXAM, GoalCategory.READING, GoalCategory.WORK])
def test_build_perspective_suggestion_instruction_returns_category_specific_text(category):
    text = ai_context_service.build_perspective_suggestion_instruction(category, True)

    assert text != ""
    assert "断定" in text


def test_list_active_exam_goals_excludes_reading_goals(seeded_session):
    """読書目標（category=READING）は資格試験用プロンプトの文脈から除外されること
    （試験科目未登録という誤った文脈の混入を防ぐ、実装フェーズ分割計画書Phase15）。
    """
    exam_goal = _make_goal(seeded_session, name="資格目標")
    reading_goal = Goal(
        category=GoalCategory.READING,
        name="読書目標",
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    seeded_session.add(reading_goal)
    seeded_session.commit()

    active_goals = ai_context_service.list_active_exam_goals(seeded_session)

    assert exam_goal.id in {g.id for g in active_goals}
    assert reading_goal.id not in {g.id for g in active_goals}


def test_list_active_exam_goals_excludes_work_goals(seeded_session):
    """仕事目標（category=WORK）も資格試験用プロンプトの文脈から除外されること
    （読書と同じ理由。実装フェーズ分割計画書Phase21回帰防止観点）。
    """
    exam_goal = _make_goal(seeded_session, name="資格目標")
    work_goal = Goal(
        category=GoalCategory.WORK,
        name="仕事目標",
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    seeded_session.add(work_goal)
    seeded_session.commit()

    active_goals = ai_context_service.list_active_exam_goals(seeded_session)

    assert exam_goal.id in {g.id for g in active_goals}
    assert work_goal.id not in {g.id for g in active_goals}


def test_build_goal_summary_does_not_leak_reading_goal_context(seeded_session):
    """読書目標を list_active_exam_goals で除外した後は、資格試験プロンプトの
    goal_summaryに読書目標の名前が現れないこと。"""
    reading_goal = Goal(
        category=GoalCategory.READING,
        name="読書目標",
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    seeded_session.add(reading_goal)
    seeded_session.commit()

    active_exam_goals = ai_context_service.list_active_exam_goals(seeded_session)
    text = ai_context_service.build_goal_summary(active_exam_goals, dt.date(2026, 1, 10))

    assert "読書目標" not in text


# --- 読書向けビルダー（DAILY_FEEDBACK_READING・GOAL_RETROSPECTIVE_READING、Phase16） ---


def _make_reading_goal(session, name="読書目標A"):
    return reading_helpers.make_reading_goal(session, name=name)


def _make_book(session, goal, **overrides):
    return reading_helpers.make_book(session, goal.id, **overrides)


def _add_reading_log(session, book_id, record_date, **overrides):
    record = DailyRecord(record_date=record_date, reading_record_state=RecordState.PROGRESS_ONLY)
    session.add(record)
    session.flush()
    defaults = dict(daily_record_id=record.id, book_id=book_id, recall_body="想起本文")
    defaults.update(overrides)
    session.add(ReadingLog(**defaults))
    session.flush()


def test_list_active_reading_goals_excludes_exam_goals(seeded_session):
    exam_goal = _make_goal(seeded_session, name="資格目標")
    reading_goal = _make_reading_goal(seeded_session)

    active = ai_context_service.list_active_reading_goals(seeded_session)

    assert reading_goal.id in {g.id for g in active}
    assert exam_goal.id not in {g.id for g in active}


def test_list_active_books_returns_book_of_each_goal(seeded_session):
    goal_with_book = _make_reading_goal(seeded_session, name="読書目標A")
    book = _make_book(seeded_session, goal_with_book)
    goal_without_book = _make_reading_goal(seeded_session, name="読書目標B")

    books = ai_context_service.list_active_books([goal_with_book, goal_without_book])

    assert books == [book]


def test_build_daily_book_summary_text_includes_title_and_remaining_days(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal, title="達人プログラマー", due_date=dt.date(2026, 1, 20))

    text = ai_context_service.build_daily_book_summary_text([book], dt.date(2026, 1, 10))

    assert "達人プログラマー" in text
    assert "残り10日" in text


def test_build_daily_book_summary_text_handles_no_books(seeded_session):
    text = ai_context_service.build_daily_book_summary_text([], dt.date(2026, 1, 10))
    assert "進行中の読書目標はありません" in text


def test_build_today_recall_text_includes_book_title_and_recall_body(seeded_session):
    """ページに関する数値は注入しない（仕様変更2026-09-11）。読書の日次報告は評価の場では
    ないため、プロンプト本文の「ページ数や読了ペースを評価しないでください」（ロジック・プロンプト編17.6）と
    矛盾しないよう、現在ページは画面表示専用とし文脈からも外す。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal, title="達人プログラマー")
    item = ReadingLogItem(book_id=book.id, recall_body="DRY原則の話が印象的だった", current_page=20)

    text = ai_context_service.build_today_recall_text([item], {book.id: book})

    assert text == "■ 達人プログラマー\nDRY原則の話が印象的だった"


def test_build_today_recall_text_handles_no_items():
    text = ai_context_service.build_today_recall_text([], {})
    assert "本日の想起入力はまだありません" in text


def test_build_recent_recalls_entries_excludes_entries_outside_window(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal, title="書籍A")
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 9), recall_body="窓内の記録")
    _add_reading_log(seeded_session, book.id, dt.date(2025, 12, 1), recall_body="窓外の記録")

    entries = ai_context_service.build_recent_recalls_entries(
        seeded_session, [book], dt.date(2026, 1, 10), recent_days=14
    )

    texts = [entry.text for entry in entries]
    assert any("窓内の記録" in text for text in texts)
    assert not any("窓外の記録" in text for text in texts)


def test_build_recent_recalls_entries_excludes_todays_own_record(seeded_session):
    """対象日（today）自身の想起記録は含めない。todayの分は{{today_recall}}で別途渡す
    ため、含めると二重にプロンプトへ注入される不具合になる（2026-09-15是正）。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal, title="書籍A")
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 10), recall_body="本日分の記録")
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 9), recall_body="前日分の記録")

    entries = ai_context_service.build_recent_recalls_entries(
        seeded_session, [book], dt.date(2026, 1, 10), recent_days=14
    )

    texts = [entry.text for entry in entries]
    assert not any("本日分の記録" in text for text in texts)
    assert any("前日分の記録" in text for text in texts)


def test_build_recent_recalls_entries_window_covers_recent_days_count_ending_yesterday(
    seeded_session,
):
    """todayを除外する分、窓をtoday-recent_days〜today-1へ後ろへずらし、実質的な日数
    （recent_days）を変えない（2026-09-15是正）。recent_days=3・today=2026-1-10なら
    2026-1-7〜2026-1-9の3日分が対象。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal, title="書籍A")
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 7), recall_body="窓の始点")
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 6), recall_body="窓の1日外側")

    entries = ai_context_service.build_recent_recalls_entries(
        seeded_session, [book], dt.date(2026, 1, 10), recent_days=3
    )

    texts = [entry.text for entry in entries]
    assert any("窓の始点" in text for text in texts)
    assert not any("窓の1日外側" in text for text in texts)


def test_build_recent_recalls_entries_orders_oldest_first(seeded_session):
    # build_with_degradable_entriesの段階（古い日から除外）はリスト先頭を古い順と
    # 前提しているため、record_dateの昇順で返ることを固定する（16.5・21.4）。
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal, title="書籍A")
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 9), recall_body="新しい記録")
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 8), recall_body="古い記録")

    entries = ai_context_service.build_recent_recalls_entries(
        seeded_session, [book], dt.date(2026, 1, 10), recent_days=14
    )

    assert [entry.record_date for entry in entries] == [dt.date(2026, 1, 8), dt.date(2026, 1, 9)]


def test_build_recent_recalls_entries_handles_no_books(seeded_session):
    entries = ai_context_service.build_recent_recalls_entries(
        seeded_session, [], dt.date(2026, 1, 10), recent_days=14
    )
    assert entries == []


def test_build_recent_recalls_entries_handles_no_logs(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal, title="書籍A")

    entries = ai_context_service.build_recent_recalls_entries(
        seeded_session, [book], dt.date(2026, 1, 10), recent_days=14
    )

    assert entries == []


def test_build_retrospective_book_summary_text_includes_period(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(
        seeded_session,
        goal,
        title="達人プログラマー",
        author="デイブトーマス",
        start_date=dt.date(2026, 1, 1),
        due_date=dt.date(2026, 3, 1),
    )

    text = ai_context_service.build_retrospective_book_summary_text(book)

    assert "達人プログラマー" in text
    assert "デイブトーマス" in text
    assert "2026-01-01" in text and "2026-03-01" in text


def test_build_reading_overall_metrics_text_computes_max_streak(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    # 1/1〜1/3が3日連続、1/10が単発（最長は3日）。
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 1))
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 2))
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 3))
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 10))

    text = ai_context_service.build_reading_overall_metrics_text(seeded_session, book)

    assert "記録日数: 4日" in text
    assert "最長連続記録日数: 3日" in text


def test_build_reading_logs_entries_orders_chronologically(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 2), recall_body="2日目の想起")
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 1), recall_body="1日目の想起")

    entries = ai_context_service.build_reading_logs_entries(seeded_session, book)

    assert [entry.record_date for entry in entries] == [dt.date(2026, 1, 1), dt.date(2026, 1, 2)]


def test_build_reading_logs_entries_date_from_excludes_earlier_entries(seeded_session):
    """L-11: 週次要約で既に圧縮済みの範囲を除外するため、date_from以降のみに絞れること。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 1), recall_body="圧縮済みの想起")
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 10), recall_body="未圧縮の想起")

    entries = ai_context_service.build_reading_logs_entries(
        seeded_session, book, date_from=dt.date(2026, 1, 5)
    )

    assert [entry.record_date for entry in entries] == [dt.date(2026, 1, 10)]


def test_build_reading_logs_entries_handles_no_logs(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)

    entries = ai_context_service.build_reading_logs_entries(seeded_session, book)

    assert entries == []


def test_build_week_recalls_text_lists_entries_within_range(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 9), recall_body="窓内の記録")
    _add_reading_log(seeded_session, book.id, dt.date(2026, 1, 20), recall_body="窓外の記録")

    text = ai_context_service.build_week_recalls_text(
        seeded_session, book, dt.date(2026, 1, 5), dt.date(2026, 1, 11)
    )

    assert "窓内の記録" in text
    assert "窓外の記録" not in text


def test_build_week_recalls_text_handles_no_logs(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)

    text = ai_context_service.build_week_recalls_text(
        seeded_session, book, dt.date(2026, 1, 5), dt.date(2026, 1, 11)
    )

    assert "この週の想起記録はありません" in text


# --- 仕事目標（WORK、実装フェーズ分割計画書Phase22） ---


def _make_work_goal(session, name="仕事目標A"):
    goal = Goal(
        category=GoalCategory.WORK,
        name=name,
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    session.add(goal)
    session.flush()
    return goal


def _make_work_assignment(session, goal, **overrides):
    defaults = dict(
        goal_id=goal.id,
        expected_content="想定業務内容",
        start_date=dt.date(2026, 1, 1),
    )
    defaults.update(overrides)
    work_assignment = WorkAssignment(**defaults)
    session.add(work_assignment)
    session.flush()
    return work_assignment


def _add_work_log(session, work_assignment_id, record_date, **overrides):
    record = DailyRecord(record_date=record_date, work_record_state=RecordState.PROGRESS_ONLY)
    session.add(record)
    session.flush()
    defaults = dict(
        daily_record_id=record.id, work_assignment_id=work_assignment_id, body="業務内容本文"
    )
    defaults.update(overrides)
    session.add(WorkLog(**defaults))
    session.flush()


def test_list_active_work_goals_excludes_exam_goals(seeded_session):
    exam_goal = _make_goal(seeded_session, name="資格目標")
    work_goal = _make_work_goal(seeded_session)

    active = ai_context_service.list_active_work_goals(seeded_session)

    assert work_goal.id in {g.id for g in active}
    assert exam_goal.id not in {g.id for g in active}


def test_list_active_work_assignments_returns_assignment_of_each_goal(seeded_session):
    goal_with_assignment = _make_work_goal(seeded_session, name="仕事目標A")
    work_assignment = _make_work_assignment(seeded_session, goal_with_assignment)
    goal_without_assignment = _make_work_goal(seeded_session, name="仕事目標B")

    assignments = ai_context_service.list_active_work_assignments(
        [goal_with_assignment, goal_without_assignment]
    )

    assert assignments == [work_assignment]


def test_build_daily_work_summary_text_includes_name_and_elapsed_days(seeded_session):
    goal = _make_work_goal(seeded_session, name="仕事目標X")
    work_assignment = _make_work_assignment(
        seeded_session, goal, client_name="A社", start_date=dt.date(2026, 1, 1)
    )

    text = ai_context_service.build_daily_work_summary_text([work_assignment], dt.date(2026, 1, 11))

    assert "仕事目標X" in text
    assert "A社" in text
    assert "経過日数: 10日" in text


def test_build_daily_work_summary_text_handles_no_assignments():
    text = ai_context_service.build_daily_work_summary_text([], dt.date(2026, 1, 10))
    assert "進行中の仕事目標はありません" in text


def test_build_today_work_text_includes_goal_name_and_body(seeded_session):
    goal = _make_work_goal(seeded_session, name="仕事目標X")
    work_assignment = _make_work_assignment(seeded_session, goal)
    item = WorkLogItem(work_assignment_id=work_assignment.id, body="今日はAPIを実装した")

    text = ai_context_service.build_today_work_text([item], {work_assignment.id: work_assignment})

    assert "仕事目標X" in text
    assert "今日はAPIを実装した" in text


def test_build_today_work_text_handles_no_items():
    text = ai_context_service.build_today_work_text([], {})
    assert "本日の業務記録はまだありません" in text


def test_build_recent_work_logs_entries_excludes_entries_outside_window(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 9), body="窓内の記録")
    _add_work_log(seeded_session, work_assignment.id, dt.date(2025, 12, 1), body="窓外の記録")

    entries = ai_context_service.build_recent_work_logs_entries(
        seeded_session, [work_assignment], dt.date(2026, 1, 10), recent_days=14
    )

    texts = [entry.text for entry in entries]
    assert any("窓内の記録" in text for text in texts)
    assert not any("窓外の記録" in text for text in texts)


def test_build_recent_work_logs_entries_excludes_todays_own_record(seeded_session):
    """対象日（today）自身の業務記録は含めない。理由はbuild_recent_recalls_entriesと同じ
    （2026-09-15是正）。"""
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 10), body="本日分の記録")
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 9), body="前日分の記録")

    entries = ai_context_service.build_recent_work_logs_entries(
        seeded_session, [work_assignment], dt.date(2026, 1, 10), recent_days=14
    )

    texts = [entry.text for entry in entries]
    assert not any("本日分の記録" in text for text in texts)
    assert any("前日分の記録" in text for text in texts)


def test_build_recent_work_logs_entries_orders_oldest_first(seeded_session):
    # build_with_degradable_entriesの段階（古い日から除外）はリスト先頭を古い順と
    # 前提しているため、record_dateの昇順で返ることを固定する（16.5・22.4）。
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 9), body="新しい記録")
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 8), body="古い記録")

    entries = ai_context_service.build_recent_work_logs_entries(
        seeded_session, [work_assignment], dt.date(2026, 1, 10), recent_days=14
    )

    assert [entry.record_date for entry in entries] == [dt.date(2026, 1, 8), dt.date(2026, 1, 9)]


def test_build_recent_work_logs_entries_handles_no_assignments(seeded_session):
    entries = ai_context_service.build_recent_work_logs_entries(
        seeded_session, [], dt.date(2026, 1, 10), recent_days=14
    )
    assert entries == []


def test_build_recent_work_logs_entries_handles_no_logs(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)

    entries = ai_context_service.build_recent_work_logs_entries(
        seeded_session, [work_assignment], dt.date(2026, 1, 10), recent_days=14
    )

    assert entries == []


def test_build_retrospective_work_summary_text_includes_client_and_start_date(seeded_session):
    goal = _make_work_goal(seeded_session, name="仕事目標X")
    work_assignment = _make_work_assignment(
        seeded_session,
        goal,
        client_name="B社",
        expected_content="Webサイト改修",
        start_date=dt.date(2026, 2, 1),
    )

    text = ai_context_service.build_retrospective_work_summary_text(work_assignment)

    assert "仕事目標X" in text
    assert "B社" in text
    assert "Webサイト改修" in text
    assert "2026-02-01" in text


def test_build_work_logs_entries_for_period_orders_chronologically(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 2), body="2日目の業務")
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 1), body="1日目の業務")

    entries = ai_context_service.build_work_logs_entries_for_period(
        seeded_session, work_assignment, dt.date(2026, 1, 1), dt.date(2026, 1, 31)
    )

    assert [entry.record_date for entry in entries] == [dt.date(2026, 1, 1), dt.date(2026, 1, 2)]


def test_build_work_logs_entries_for_period_excludes_entries_outside_range(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 15), body="範囲内の業務")
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 2, 1), body="範囲外の業務")

    entries = ai_context_service.build_work_logs_entries_for_period(
        seeded_session, work_assignment, dt.date(2026, 1, 1), dt.date(2026, 1, 31)
    )

    texts = [entry.text for entry in entries]
    assert any("範囲内の業務" in text for text in texts)
    assert not any("範囲外の業務" in text for text in texts)


def test_build_work_logs_entries_for_period_handles_no_logs(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)

    entries = ai_context_service.build_work_logs_entries_for_period(
        seeded_session, work_assignment, dt.date(2026, 1, 1), dt.date(2026, 1, 31)
    )

    assert entries == []


def test_build_week_work_logs_text_lists_entries_within_range(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 9), body="窓内の記録")
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 20), body="窓外の記録")

    text = ai_context_service.build_week_work_logs_text(
        seeded_session, work_assignment, dt.date(2026, 1, 5), dt.date(2026, 1, 11)
    )

    assert "窓内の記録" in text
    assert "窓外の記録" not in text


def test_build_week_work_logs_text_handles_no_logs(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)

    text = ai_context_service.build_week_work_logs_text(
        seeded_session, work_assignment, dt.date(2026, 1, 5), dt.date(2026, 1, 11)
    )

    assert "この週の業務記録はありません" in text


def test_build_work_progress_summary_includes_elapsed_days_and_streak(seeded_session):
    goal = _make_work_goal(seeded_session, name="仕事目標X")
    work_assignment = _make_work_assignment(seeded_session, goal, start_date=dt.date(2026, 1, 1))
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 10))

    text = ai_context_service.build_work_progress_summary(
        seeded_session, [work_assignment], dt.date(2026, 1, 10)
    )

    assert "仕事目標X" in text
    assert "経過9日" in text
    assert "連続記録1日" in text
    assert "直近記録日 2026-01-10" in text
    assert "直近の月次報告なし" in text


def test_build_work_progress_summary_includes_recent_monthly_report(seeded_session):
    """22.1: WORK用の{{progress_summary}}は直近の月次報告有無を含める
    （未生成の期に「今日の一言」から月次報告の作成を促せるようにするため）。"""
    goal = _make_work_goal(seeded_session, name="仕事目標Y")
    work_assignment = _make_work_assignment(seeded_session, goal, start_date=dt.date(2026, 1, 1))
    seeded_session.add(
        GoalRetrospective(
            goal_id=goal.id,
            body="前月の月次報告",
            period_type=RetrospectivePeriodType.MONTHLY,
            period_key="2026-01",
        )
    )
    seeded_session.flush()

    text = ai_context_service.build_work_progress_summary(
        seeded_session, [work_assignment], dt.date(2026, 2, 10)
    )

    assert "直近の月次報告あり" in text


def test_build_work_progress_summary_handles_no_assignments(seeded_session):
    text = ai_context_service.build_work_progress_summary(seeded_session, [], dt.date(2026, 1, 10))
    assert "対象案件はありません" in text


def test_build_work_recent_activity_text_counts_reported_days(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    record = DailyRecord(record_date=dt.date(2026, 1, 9), work_record_state=RecordState.REPORTED)
    seeded_session.add(record)
    seeded_session.flush()
    seeded_session.add(
        WorkLog(daily_record_id=record.id, work_assignment_id=work_assignment.id, body="業務内容")
    )
    seeded_session.flush()

    text = ai_context_service.build_work_recent_activity_text(
        seeded_session, [work_assignment], dt.date(2026, 1, 10)
    )

    assert "記録日数: 1日" in text
    assert "報告確定 1日" in text


def test_build_work_recent_activity_text_handles_no_assignments(seeded_session):
    text = ai_context_service.build_work_recent_activity_text(
        seeded_session, [], dt.date(2026, 1, 10)
    )
    assert "対象案件はありません" in text


def test_build_work_recent_activity_text_handles_no_logs(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)

    text = ai_context_service.build_work_recent_activity_text(
        seeded_session, [work_assignment], dt.date(2026, 1, 10)
    )

    assert "直近の業務記録はありません" in text


def test_list_daily_message_target_goals_includes_exam_and_work_excludes_reading(seeded_session):
    exam_goal = _make_goal(seeded_session, name="資格目標")
    work_goal = _make_work_goal(seeded_session, name="仕事目標")
    reading_goal = _make_reading_goal(seeded_session, name="読書目標")

    targets = ai_context_service.list_daily_message_target_goals(seeded_session)

    target_ids = {g.id for g in targets}
    assert exam_goal.id in target_ids
    assert work_goal.id in target_ids
    assert reading_goal.id not in target_ids
