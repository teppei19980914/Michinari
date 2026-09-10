"""speed_service のテスト（ロジック・プロンプト編 8〜10章、20章の検証観点）。"""

import datetime as dt

import pytest

from app.constants.enums import DayType, Environment, GoalStatus, RecordState
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import DailyRecord, StudyLog
from app.models.resource import ResourceSlot, ResourceSlotWeekday
from app.models.setting import CalendarDayOverride
from app.services import speed_service


def _make_goal(db_session) -> Goal:
    goal = Goal(
        name="速度検証",
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    db_session.add(goal)
    db_session.flush()
    return goal


def _make_material(
    db_session,
    goal_id: int,
    total_amount: float = 100,
    planned_cycles: int = 2,
    due_date: dt.date = dt.date(2026, 12, 31),
) -> Material:
    material = Material(
        goal_id=goal_id,
        name="教材",
        unit_label="問",
        total_amount=total_amount,
        planned_cycles=planned_cycles,
        start_date=dt.date(2026, 1, 1),
        due_date=due_date,
        display_order=1,
    )
    db_session.add(material)
    db_session.flush()
    return material


def _add_study_log(
    db_session,
    material_id: int,
    record_date: dt.date,
    amount: float,
    cycle: int,
    minutes: int | None,
) -> None:
    record = DailyRecord(record_date=record_date, exam_record_state=RecordState.PROGRESS_ONLY)
    db_session.add(record)
    db_session.flush()
    db_session.add(
        StudyLog(
            daily_record_id=record.id,
            material_id=material_id,
            minutes_spent=minutes,
            amount_completed=amount,
            cycle_number=cycle,
        )
    )
    db_session.flush()


def test_cycle_speed_computed_from_amount_and_minutes(db_session):
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    _add_study_log(db_session, material.id, dt.date(2026, 9, 1), amount=10, cycle=1, minutes=60)
    _add_study_log(db_session, material.id, dt.date(2026, 9, 2), amount=20, cycle=1, minutes=60)

    result = speed_service.compute_cycle_speed(db_session, material.id, cycle_number=1)

    assert result.sample_count == 2
    assert result.speed == pytest.approx(15.0)  # (10+20) / (60+60)/60時間 = 30/2 = 15


def test_cycle_speed_excludes_null_or_zero_minutes(db_session):
    """時間未入力の実績が分母・分子とも除外されること（Phase2必須観点）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    _add_study_log(db_session, material.id, dt.date(2026, 9, 1), amount=10, cycle=1, minutes=60)
    _add_study_log(db_session, material.id, dt.date(2026, 9, 2), amount=999, cycle=1, minutes=None)
    _add_study_log(db_session, material.id, dt.date(2026, 9, 3), amount=999, cycle=1, minutes=0)

    result = speed_service.compute_cycle_speed(db_session, material.id, cycle_number=1)

    assert result.sample_count == 1
    assert result.speed == pytest.approx(10.0)


def test_cycle_speed_excludes_off_day_records(db_session):
    """OFF日の実績が除外されること（20章）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    off_date = dt.date(2026, 9, 5)
    db_session.add(CalendarDayOverride(target_date=off_date, day_type=DayType.OFF))
    db_session.flush()
    _add_study_log(db_session, material.id, dt.date(2026, 9, 1), amount=10, cycle=1, minutes=60)
    _add_study_log(db_session, material.id, off_date, amount=999, cycle=1, minutes=60)

    result = speed_service.compute_cycle_speed(db_session, material.id, cycle_number=1)

    assert result.sample_count == 1
    assert result.speed == pytest.approx(10.0)


def test_cycle_speed_none_when_no_valid_records(db_session):
    """実績が存在しない場合に算出不能として扱われること（20章）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)

    assert speed_service.compute_cycle_speed(db_session, material.id, cycle_number=1) is None


def test_cycle_speed_none_when_all_records_are_off_day(db_session):
    """境界値: 実績はあるが全てOFF日のため除外後0件となる場合に算出不能となること。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    off_date = dt.date(2026, 9, 5)
    db_session.add(CalendarDayOverride(target_date=off_date, day_type=DayType.OFF))
    db_session.flush()
    _add_study_log(db_session, material.id, off_date, amount=10, cycle=1, minutes=60)

    assert speed_service.compute_cycle_speed(db_session, material.id, cycle_number=1) is None


def test_cycle_speeds_batched_groups_results_by_cycle_without_mixing(db_session):
    """compute_cycle_speeds（Phase3 GET /materials/{id}/cyclesのN+1回避用一括版）が
    複数周回を1クエリでまとめて取得しても、周回ごとの実績を混同しないこと。
    """
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    _add_study_log(db_session, material.id, dt.date(2026, 9, 1), amount=10, cycle=1, minutes=60)
    _add_study_log(db_session, material.id, dt.date(2026, 9, 2), amount=40, cycle=2, minutes=60)

    result = speed_service.compute_cycle_speeds(db_session, material.id, [1, 2, 3])

    assert result[1].sample_count == 1
    assert result[1].speed == pytest.approx(10.0)
    assert result[2].sample_count == 1
    assert result[2].speed == pytest.approx(40.0)
    assert 3 not in result  # 実績が無い周回はキーに含まれない


def test_cycle_speeds_batched_empty_when_no_rows(db_session):
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)

    assert speed_service.compute_cycle_speeds(db_session, material.id, [1, 2]) == {}


def test_effective_speed_separated_by_cycle(db_session):
    """周回ごとに分離して算出されること（Phase2必須観点: 周回別速度）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    # 1周目: 遅い速度（10/h）、3件以上
    for day, amount in [(1, 10), (2, 10), (3, 10)]:
        _add_study_log(
            db_session, material.id, dt.date(2026, 9, day), amount=amount, cycle=1, minutes=60
        )
    # 2周目: 速い速度（30/h）、3件以上
    for day, amount in [(11, 30), (12, 30), (13, 30)]:
        _add_study_log(
            db_session, material.id, dt.date(2026, 9, day), amount=amount, cycle=2, minutes=60
        )

    speed_cycle1 = speed_service.compute_effective_speed(db_session, material, current_cycle=1)
    speed_cycle2 = speed_service.compute_effective_speed(db_session, material, current_cycle=2)

    assert speed_cycle1.speed == pytest.approx(10.0)
    assert speed_cycle1.cycle_used == 1
    assert speed_cycle2.speed == pytest.approx(30.0)
    assert speed_cycle2.cycle_used == 2


def test_effective_speed_falls_back_to_previous_cycle_when_sample_insufficient(db_session):
    """現在周回のサンプルが3件未満のとき直近周回の値で代替されること（Phase2必須観点）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    for day, amount in [(1, 10), (2, 10), (3, 10)]:
        _add_study_log(
            db_session, material.id, dt.date(2026, 9, day), amount=amount, cycle=1, minutes=60
        )
    # 2周目はサンプル2件のみ（3件未満）
    for day, amount in [(11, 30), (12, 30)]:
        _add_study_log(
            db_session, material.id, dt.date(2026, 9, day), amount=amount, cycle=2, minutes=60
        )

    effective = speed_service.compute_effective_speed(db_session, material, current_cycle=2)

    assert effective.cycle_used == 1
    assert effective.speed == pytest.approx(10.0)


def test_effective_speed_none_when_both_cycles_insufficient(db_session):
    """境界値: サンプル不足時に算出不能となり例外が発生しないこと（8.5）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)

    assert speed_service.compute_effective_speed(db_session, material, current_cycle=1) is None


def test_effective_speed_none_when_previous_cycle_also_insufficient(db_session):
    """境界値: 現在周回・直近周回のいずれもサンプル不足の場合に算出不能となること（8.5）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    # 1周目の実績が0件、2周目のサンプルも不足（1件のみ）
    _add_study_log(db_session, material.id, dt.date(2026, 9, 11), amount=30, cycle=2, minutes=60)

    assert speed_service.compute_effective_speed(db_session, material, current_cycle=2) is None


def test_forecast_unavailable_when_no_speed_data(db_session):
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=100, planned_cycles=1)

    result = speed_service.compute_forecast_date(
        db_session,
        goal,
        material,
        [material],
        today=dt.date(2026, 1, 1),
        treat_holiday_as_buffer=True,
    )

    assert result.forecast_date is None
    assert result.unavailable_reason == speed_service.ForecastUnavailableReason.NO_SPEED_DATA


def _make_daily_slot(db_session) -> None:
    slot = ResourceSlot(
        name="夜スロット",
        start_time=dt.time(20, 0),
        end_time=dt.time(22, 0),
        environment=Environment.ANY,
        display_order=1,
    )
    db_session.add(slot)
    db_session.flush()
    for weekday in range(7):
        db_session.add(ResourceSlotWeekday(slot_id=slot.id, weekday=weekday))
    db_session.flush()


def test_forecast_excludes_buffer_days_from_accumulation(db_session):
    """完了予測はバッファ日を累積対象から除外すること（Phase2必須観点、10.2）。"""
    goal = _make_goal(db_session)
    due_date = dt.date(2026, 3, 31)
    material = _make_material(
        db_session, goal.id, total_amount=100, planned_cycles=1, due_date=due_date
    )
    _make_daily_slot(db_session)
    for day, amount in [(1, 10), (2, 10), (3, 10)]:
        _add_study_log(
            db_session, material.id, dt.date(2026, 1, day), amount=amount, cycle=1, minutes=60
        )
    # 実効速度: 30/3h = 10/h、残量70 -> 必要時間7h -> 2時間スロット/日なら4日分
    # 曜日既定値の状態に依存しないよう、対象期間の全日を明示的に上書きする
    today = dt.date(2026, 1, 10)
    db_session.add(CalendarDayOverride(target_date=today, day_type=DayType.BUFFER))
    for offset in range(1, 10):
        db_session.add(
            CalendarDayOverride(
                target_date=today + dt.timedelta(days=offset), day_type=DayType.PLAN
            )
        )
    db_session.flush()

    result_with_buffer = speed_service.compute_forecast_date(
        db_session, goal, material, [material], today=today, treat_holiday_as_buffer=True
    )

    # バッファ日(1/10)を挟まず、翌日からPLANのみで積算した場合と比較する
    result_without_buffer_gap = speed_service.compute_forecast_date(
        db_session,
        goal,
        material,
        [material],
        today=today + dt.timedelta(days=1),
        treat_holiday_as_buffer=True,
    )

    assert result_with_buffer.forecast_date is not None
    assert result_with_buffer.forecast_date == result_without_buffer_gap.forecast_date


def test_forecast_iteration_limit_exceeded_returns_reason_without_raising(db_session):
    """完了予測: 反復上限で打ち切られること（例外を発生させない、20章）。"""
    goal = _make_goal(db_session)
    due_date = dt.date(2026, 1, 31)
    # 総量を極端に大きくし、割当スロットなし（未割当）で絶対に完了しない状況を作る
    material = _make_material(
        db_session, goal.id, total_amount=1_000_000, planned_cycles=1, due_date=due_date
    )
    _add_study_log(db_session, material.id, dt.date(2026, 1, 1), amount=10, cycle=1, minutes=60)
    _add_study_log(db_session, material.id, dt.date(2026, 1, 2), amount=10, cycle=1, minutes=60)
    _add_study_log(db_session, material.id, dt.date(2026, 1, 3), amount=10, cycle=1, minutes=60)
    # スロットを一切登録しない -> 割当時間は常に0 -> 決して収束しない

    result = speed_service.compute_forecast_date(
        db_session,
        goal,
        material,
        [material],
        today=dt.date(2026, 1, 4),
        treat_holiday_as_buffer=True,
    )

    assert result.forecast_date is None
    assert (
        result.unavailable_reason
        == speed_service.ForecastUnavailableReason.ITERATION_LIMIT_EXCEEDED
    )


def test_required_speed_none_when_available_hours_zero(db_session):
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=100, due_date=dt.date(2026, 9, 1))
    # スロット未登録 -> available_hours = 0

    required = speed_service.compute_required_speed(
        db_session,
        goal,
        material,
        [material],
        today=dt.date(2026, 1, 1),
        treat_holiday_as_buffer=True,
    )

    assert required is None


def test_required_speed_none_when_today_after_due_date(db_session):
    """境界値: 本日が締切より後（残計画日0）の場合に例外が発生しないこと。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=100, due_date=dt.date(2026, 1, 5))

    required = speed_service.compute_required_speed(
        db_session,
        goal,
        material,
        [material],
        today=dt.date(2026, 1, 10),
        treat_holiday_as_buffer=True,
    )

    assert required is None


def test_speed_trend_returns_one_point_per_valid_record_grouped_by_cycle(db_session):
    """分析画面ANL-06: 実績1件ごとに1点として、周回別に系列分離されること。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    _add_study_log(db_session, material.id, dt.date(2026, 9, 1), amount=10, cycle=1, minutes=60)
    _add_study_log(db_session, material.id, dt.date(2026, 9, 2), amount=20, cycle=1, minutes=60)
    _add_study_log(db_session, material.id, dt.date(2026, 9, 11), amount=30, cycle=2, minutes=60)

    trend = speed_service.compute_speed_trend(db_session, material.id)

    assert [p.speed for p in trend[1]] == [pytest.approx(10.0), pytest.approx(20.0)]
    assert [p.record_date for p in trend[1]] == [dt.date(2026, 9, 1), dt.date(2026, 9, 2)]
    assert [p.speed for p in trend[2]] == [pytest.approx(30.0)]


def test_speed_trend_excludes_null_zero_minutes_and_off_days(db_session):
    """実効速度推移も compute_cycle_speed と同じ除外基準（時間未入力・OFF日）を適用すること。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    off_date = dt.date(2026, 9, 5)
    db_session.add(CalendarDayOverride(target_date=off_date, day_type=DayType.OFF))
    db_session.flush()
    _add_study_log(db_session, material.id, dt.date(2026, 9, 1), amount=10, cycle=1, minutes=60)
    _add_study_log(db_session, material.id, dt.date(2026, 9, 2), amount=999, cycle=1, minutes=None)
    _add_study_log(db_session, material.id, dt.date(2026, 9, 3), amount=999, cycle=1, minutes=0)
    _add_study_log(db_session, material.id, off_date, amount=999, cycle=1, minutes=60)

    trend = speed_service.compute_speed_trend(db_session, material.id)

    assert len(trend[1]) == 1
    assert trend[1][0].record_date == dt.date(2026, 9, 1)


def test_speed_trend_empty_when_no_valid_records(db_session):
    """境界値: 有効な実績が0件のケースで例外が発生しないこと。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)

    assert speed_service.compute_speed_trend(db_session, material.id) == {}


def test_required_speed_computed_from_remaining_and_available_hours(db_session):
    goal = _make_goal(db_session)
    due_date = dt.date(2026, 1, 5)
    material = _make_material(
        db_session, goal.id, total_amount=100, planned_cycles=1, due_date=due_date
    )
    _make_daily_slot(db_session)  # 2時間/日 x 5日 = 10時間
    for d in range(1, 6):
        db_session.add(CalendarDayOverride(target_date=dt.date(2026, 1, d), day_type=DayType.PLAN))
    db_session.flush()

    required = speed_service.compute_required_speed(
        db_session,
        goal,
        material,
        [material],
        today=dt.date(2026, 1, 1),
        treat_holiday_as_buffer=True,
    )

    assert required == pytest.approx(10.0)  # 残量100 / 10時間
