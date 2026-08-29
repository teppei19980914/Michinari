"""metrics_service のテスト（ロジック・プロンプト編 13〜14章、20章の検証観点）。"""

import datetime as dt

import pytest

from app.constants.enums import (
    BaselineReason,
    DayType,
    ExamDateType,
    GoalStatus,
    Granularity,
    PassingScoreType,
    QualityMetricType,
    RecordState,
)
from app.models.goal import ExamSubject, Goal
from app.models.material import Material, MaterialSubject, PlanBaseline
from app.models.record import DailyRecord, StudyLog
from app.models.setting import CalendarDayOverride
from app.services import cycle_service, metrics_service


def _make_goal(db_session, start_date: dt.date = dt.date(2026, 1, 1)) -> Goal:
    goal = Goal(name="指標検証", start_date=start_date, status=GoalStatus.ACTIVE)
    db_session.add(goal)
    db_session.flush()
    return goal


def _make_material(db_session, goal_id: int) -> Material:
    material = Material(
        goal_id=goal_id,
        name="教材",
        unit_label="問",
        total_amount=100,
        planned_cycles=1,
        start_date=dt.date(2026, 1, 1),
        due_date=dt.date(2026, 12, 31),
        display_order=1,
    )
    db_session.add(material)
    db_session.flush()
    return material


def _override(db_session, date_from: dt.date, date_to: dt.date, day_type: DayType) -> None:
    d = date_from
    while d <= date_to:
        db_session.add(CalendarDayOverride(target_date=d, day_type=day_type))
        d += dt.timedelta(days=1)


def _make_record(db_session, record_date: dt.date, state: RecordState) -> DailyRecord:
    record = DailyRecord(record_date=record_date, record_state=state)
    db_session.add(record)
    db_session.flush()
    return record


def test_buffer_usage_rate_counts_days_with_study_log(db_session):
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    _override(db_session, dt.date(2026, 1, 2), dt.date(2026, 1, 3), DayType.BUFFER)
    record = _make_record(db_session, dt.date(2026, 1, 2), RecordState.PROGRESS_ONLY)
    db_session.add(
        StudyLog(
            daily_record_id=record.id,
            material_id=material.id,
            minutes_spent=30,
            amount_completed=5,
            cycle_number=1,
        )
    )
    db_session.flush()

    rate = metrics_service.compute_buffer_usage_rate(
        db_session, goal, dt.date(2026, 1, 4), treat_holiday_as_buffer=True
    )

    assert rate == pytest.approx(0.5)  # 経過バッファ日2日のうち実績あり1日


def test_buffer_usage_rate_none_when_no_elapsed_buffer_days(db_session):
    """境界値: 経過バッファ日が0件の場合に例外が発生しないこと。"""
    goal = _make_goal(db_session)
    _override(db_session, dt.date(2026, 1, 2), dt.date(2026, 1, 5), DayType.PLAN)
    db_session.flush()

    rate = metrics_service.compute_buffer_usage_rate(
        db_session, goal, dt.date(2026, 1, 5), treat_holiday_as_buffer=True
    )

    assert rate is None


def test_buffer_usage_rate_none_when_today_is_not_after_start_date(db_session):
    """境界値: 本日が開始日以前の場合に例外が発生しないこと。"""
    goal = _make_goal(db_session, start_date=dt.date(2026, 1, 5))

    rate = metrics_service.compute_buffer_usage_rate(
        db_session, goal, dt.date(2026, 1, 5), treat_holiday_as_buffer=True
    )

    assert rate is None


def test_progress_rate_uses_total_work_and_completed(db_session):
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    record = _make_record(db_session, dt.date(2026, 1, 2), RecordState.PROGRESS_ONLY)
    db_session.add(
        StudyLog(
            daily_record_id=record.id,
            material_id=material.id,
            minutes_spent=30,
            amount_completed=25,
            cycle_number=1,
        )
    )
    db_session.flush()

    progress = cycle_service.get_material_progress(db_session, material)
    rate = metrics_service.compute_progress_rate(progress)

    assert rate == pytest.approx(0.25)


def test_progress_rate_zero_when_total_work_is_zero():
    """境界値: 総作業量が0の場合に例外が発生しないこと。"""
    progress = cycle_service.MaterialProgress(
        total_work=0, completed=0, remaining=0, current_cycle=1
    )

    assert metrics_service.compute_progress_rate(progress) == 0.0


def test_report_rate_computed_over_elapsed_days(db_session):
    goal = _make_goal(db_session, start_date=dt.date(2026, 1, 1))
    _make_record(db_session, dt.date(2026, 1, 1), RecordState.REPORTED)
    _make_record(db_session, dt.date(2026, 1, 2), RecordState.PROGRESS_ONLY)
    _make_record(db_session, dt.date(2026, 1, 3), RecordState.REPORTED)

    rate = metrics_service.compute_report_rate(db_session, goal, dt.date(2026, 1, 4))

    assert rate == pytest.approx(2 / 4)  # 1/1〜1/4の4日中、報告済み2日


def test_report_rate_zero_when_today_before_start_date(db_session):
    """境界値: 本日が開始日より前の場合に例外が発生しないこと。"""
    goal = _make_goal(db_session, start_date=dt.date(2026, 1, 10))

    rate = metrics_service.compute_report_rate(db_session, goal, dt.date(2026, 1, 5))

    assert rate == 0.0


def test_recent_report_rate_uses_window_days_when_history_is_longer(db_session):
    goal = _make_goal(db_session, start_date=dt.date(2026, 1, 1))
    # 窓の外（1/1）は分母・分子から除外される
    _make_record(db_session, dt.date(2026, 1, 1), RecordState.REPORTED)
    _make_record(db_session, dt.date(2026, 1, 2), RecordState.REPORTED)
    _make_record(db_session, dt.date(2026, 1, 3), RecordState.PROGRESS_ONLY)

    rate = metrics_service.compute_recent_report_rate(
        db_session, goal, dt.date(2026, 1, 3), window_days=2
    )

    assert rate == pytest.approx(1 / 2)  # 窓は1/2〜1/3の2日、報告済みは1/2の1日のみ


def test_recent_report_rate_uses_elapsed_days_when_shorter_than_window(db_session):
    """境界値: 目標開始からの経過日数がwindow_days未満の場合は経過日数のみを母数とする。"""
    goal = _make_goal(db_session, start_date=dt.date(2026, 1, 1))
    _make_record(db_session, dt.date(2026, 1, 1), RecordState.REPORTED)

    rate = metrics_service.compute_recent_report_rate(
        db_session, goal, dt.date(2026, 1, 2), window_days=30
    )

    assert rate == pytest.approx(1 / 2)  # 1/1〜1/2の2日中、報告済み1日


def test_recent_report_rate_zero_when_today_before_start_date(db_session):
    """境界値: 本日が開始日より前の場合に例外が発生しないこと。"""
    goal = _make_goal(db_session, start_date=dt.date(2026, 1, 10))

    rate = metrics_service.compute_recent_report_rate(
        db_session, goal, dt.date(2026, 1, 5), window_days=30
    )

    assert rate == 0.0


def test_consecutive_report_days_zero_when_today_before_start_date(db_session):
    """境界値: 本日が開始日より前の場合に例外が発生しないこと。"""
    goal = _make_goal(db_session, start_date=dt.date(2026, 1, 10))

    count = metrics_service.compute_consecutive_report_days(
        db_session, goal, dt.date(2026, 1, 5), treat_holiday_as_buffer=True
    )

    assert count == 0


def test_consecutive_report_days_not_broken_by_buffer_or_off(db_session):
    goal = _make_goal(db_session, start_date=dt.date(2026, 1, 1))
    _override(db_session, dt.date(2026, 1, 1), dt.date(2026, 1, 5), DayType.PLAN)
    db_session.flush()
    override_buffer = db_session.get(CalendarDayOverride, dt.date(2026, 1, 3))
    override_buffer.day_type = DayType.BUFFER
    _make_record(db_session, dt.date(2026, 1, 1), RecordState.REPORTED)
    _make_record(db_session, dt.date(2026, 1, 2), RecordState.REPORTED)
    # 1/3はBUFFER日で無報告（連続を中断しない）
    _make_record(db_session, dt.date(2026, 1, 4), RecordState.REPORTED)
    _make_record(db_session, dt.date(2026, 1, 5), RecordState.REPORTED)

    count = metrics_service.compute_consecutive_report_days(
        db_session, goal, dt.date(2026, 1, 5), treat_holiday_as_buffer=True
    )

    assert count == 4  # 1/3(バッファ、無報告)を除いた報告日数


def test_consecutive_report_days_broken_by_unreported_plan_day(db_session):
    goal = _make_goal(db_session, start_date=dt.date(2026, 1, 1))
    _override(db_session, dt.date(2026, 1, 1), dt.date(2026, 1, 5), DayType.PLAN)
    _make_record(db_session, dt.date(2026, 1, 1), RecordState.REPORTED)
    # 1/2はPLAN日だが無報告 -> 連続はここで途切れる
    _make_record(db_session, dt.date(2026, 1, 4), RecordState.REPORTED)
    _make_record(db_session, dt.date(2026, 1, 5), RecordState.REPORTED)

    count = metrics_service.compute_consecutive_report_days(
        db_session, goal, dt.date(2026, 1, 5), treat_holiday_as_buffer=True
    )

    assert count == 2  # 1/4, 1/5のみ


def test_replan_count_excludes_initial_reason(db_session):
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    db_session.add(
        PlanBaseline(
            material_id=material.id,
            effective_from=dt.date(2026, 1, 1),
            baseline_daily_quota=5,
            remaining_at_baseline=100,
            plan_days_at_baseline=20,
            planned_cycles_at_baseline=1,
            reason=BaselineReason.INITIAL,
        )
    )
    db_session.add(
        PlanBaseline(
            material_id=material.id,
            effective_from=dt.date(2026, 3, 1),
            baseline_daily_quota=8,
            remaining_at_baseline=60,
            plan_days_at_baseline=10,
            planned_cycles_at_baseline=1,
            reason=BaselineReason.REPLAN,
        )
    )
    db_session.flush()

    assert metrics_service.compute_replan_count(db_session, goal) == 1


def test_normalize_quality_value_none_type_returns_none():
    assert metrics_service.normalize_quality_value(QualityMetricType.NONE, 80) is None


def test_normalize_quality_value_objective_passthrough():
    assert metrics_service.normalize_quality_value(QualityMetricType.OBJECTIVE, 73.5) == 73.5


def test_normalize_quality_value_subjective_normalized():
    """主観的手応えが正しく正規化されること（20章）。"""
    assert metrics_service.normalize_quality_value(QualityMetricType.SUBJECTIVE, 1) == 20.0
    assert metrics_service.normalize_quality_value(QualityMetricType.SUBJECTIVE, 3) == 60.0
    assert metrics_service.normalize_quality_value(QualityMetricType.SUBJECTIVE, 5) == 100.0


def test_normalize_quality_value_subjective_out_of_range_raises():
    with pytest.raises(ValueError):
        metrics_service.normalize_quality_value(QualityMetricType.SUBJECTIVE, 6)


def test_group_quality_by_cycle_separates_series(db_session):
    """周回別に系列が分離されること（Phase2必須観点の関連観点、20章）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    record1 = _make_record(db_session, dt.date(2026, 1, 2), RecordState.REPORTED)
    db_session.add(
        StudyLog(
            daily_record_id=record1.id,
            material_id=material.id,
            minutes_spent=30,
            amount_completed=10,
            cycle_number=1,
            quality_value=60.0,
        )
    )
    record2 = _make_record(db_session, dt.date(2026, 2, 2), RecordState.REPORTED)
    db_session.add(
        StudyLog(
            daily_record_id=record2.id,
            material_id=material.id,
            minutes_spent=30,
            amount_completed=10,
            cycle_number=2,
            quality_value=90.0,
        )
    )
    db_session.flush()

    grouped = metrics_service.group_quality_by_cycle(db_session, material.id)

    assert grouped == {1: [60.0], 2: [90.0]}


def _add_quality_log(
    db_session, material_id: int, record_date: dt.date, quality: float, cycle: int = 1
) -> None:
    record = _make_record(db_session, record_date, RecordState.REPORTED)
    db_session.add(
        StudyLog(
            daily_record_id=record.id,
            material_id=material_id,
            minutes_spent=30,
            amount_completed=10,
            cycle_number=cycle,
            quality_value=quality,
        )
    )
    db_session.flush()


def test_quality_trend_day_granularity_keeps_one_point_per_day(db_session):
    """分析画面ANL-01: 日別粒度では実績日ごとに1点となること（14.2）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    _add_quality_log(db_session, material.id, dt.date(2026, 1, 5), 60.0)
    _add_quality_log(db_session, material.id, dt.date(2026, 1, 6), 80.0)

    trend = metrics_service.compute_quality_trend(db_session, material.id, Granularity.DAY)

    assert [p.period_start for p in trend[1]] == [dt.date(2026, 1, 5), dt.date(2026, 1, 6)]
    assert [p.value for p in trend[1]] == [60.0, 80.0]


def test_quality_trend_week_granularity_averages_within_monday_start_week(db_session):
    """週別粒度は月曜始まりの週内で単純平均すること（14.2、15.1と同じ週定義）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    # 2026-01-05は月曜、2026-01-08は同じ週の木曜
    _add_quality_log(db_session, material.id, dt.date(2026, 1, 5), 60.0)
    _add_quality_log(db_session, material.id, dt.date(2026, 1, 8), 100.0)

    trend = metrics_service.compute_quality_trend(db_session, material.id, Granularity.WEEK)

    assert len(trend[1]) == 1
    assert trend[1][0].period_start == dt.date(2026, 1, 5)
    assert trend[1][0].value == pytest.approx(80.0)  # (60+100)/2の単純平均（加重平均ではない）
    assert trend[1][0].sample_count == 2


def test_quality_trend_month_granularity_buckets_by_first_of_month(db_session):
    """月別粒度は月の値を単純平均し、区間開始日は月初になること（14.2）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    _add_quality_log(db_session, material.id, dt.date(2026, 3, 1), 40.0)
    _add_quality_log(db_session, material.id, dt.date(2026, 3, 31), 60.0)

    trend = metrics_service.compute_quality_trend(db_session, material.id, Granularity.MONTH)

    assert len(trend[1]) == 1
    assert trend[1][0].period_start == dt.date(2026, 3, 1)
    assert trend[1][0].value == pytest.approx(50.0)


def test_quality_trend_separates_series_by_cycle(db_session):
    """周回別に系列分離されること（14.3、2周目以降を1周目と混同しない）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    _add_quality_log(db_session, material.id, dt.date(2026, 1, 5), 50.0, cycle=1)
    _add_quality_log(db_session, material.id, dt.date(2026, 2, 5), 90.0, cycle=2)

    trend = metrics_service.compute_quality_trend(db_session, material.id, Granularity.DAY)

    assert set(trend.keys()) == {1, 2}
    assert trend[2][0].value == 90.0


def test_quality_trend_empty_when_no_quality_values(db_session):
    """境界値: 品質指標が1件も記録されていない場合に例外が発生しないこと。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)

    assert metrics_service.compute_quality_trend(db_session, material.id, Granularity.DAY) == {}


def _link_subject(
    db_session,
    goal_id: int,
    material_id: int,
    passing_score: float | None,
    display_order: int = 1,
    passing_score_type: PassingScoreType = PassingScoreType.PERCENTAGE,
    passing_score_max: float | None = None,
) -> None:
    subject = ExamSubject(
        goal_id=goal_id,
        name="科目",
        exam_date_type=ExamDateType.FIXED,
        exam_date_fixed=dt.date(2026, 12, 1),
        passing_score=passing_score,
        passing_score_type=passing_score_type,
        passing_score_max=passing_score_max,
        display_order=display_order,
    )
    db_session.add(subject)
    db_session.flush()
    db_session.add(MaterialSubject(material_id=material_id, subject_id=subject.id))
    db_session.flush()


def test_resolve_passing_score_none_when_no_linked_subjects(db_session):
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)

    assert metrics_service.resolve_passing_score(material) is None


def test_resolve_passing_score_uses_highest_when_multiple_subjects_linked(db_session):
    """14.4: 教材が複数科目に紐づく場合、最も高いpassing_scoreを採用する。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    _link_subject(db_session, goal.id, material.id, passing_score=60.0, display_order=1)
    _link_subject(db_session, goal.id, material.id, passing_score=75.0, display_order=2)

    assert metrics_service.resolve_passing_score(material) == 75.0


def test_resolve_passing_score_normalizes_raw_score_by_max(db_session):
    """点数入力（RAW_SCORE）は満点で除して百分率に正規化する（ロジック・プロンプト編14.4）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    _link_subject(
        db_session,
        goal.id,
        material.id,
        passing_score=700.0,
        passing_score_type=PassingScoreType.RAW_SCORE,
        passing_score_max=1000.0,
    )

    assert metrics_service.resolve_passing_score(material) == 70.0


def test_resolve_passing_score_compares_normalized_values_across_mixed_types(db_session):
    """百分率入力と点数入力が混在する場合、正規化後の値同士で比較する。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    _link_subject(db_session, goal.id, material.id, passing_score=60.0, display_order=1)
    _link_subject(
        db_session,
        goal.id,
        material.id,
        passing_score=800.0,
        display_order=2,
        passing_score_type=PassingScoreType.RAW_SCORE,
        passing_score_max=1000.0,
    )

    assert metrics_service.resolve_passing_score(material) == 80.0
