"""calendar_service のテスト（ロジック・プロンプト編 3〜5章、20章の検証観点）。"""

import datetime as dt

from app.constants.enums import DayType, GoalStatus
from app.models.goal import Goal, LoadProfile
from app.models.setting import CalendarDayOverride, DayTypeDefault, Holiday
from app.services import calendar_service


def test_resolve_logical_today_returns_previous_day_before_boundary():
    """境界時刻より前の時刻において論理日が前日になること（Phase2完了条件・必須観点）。"""
    now = dt.datetime(2026, 3, 10, 1, 30)
    assert calendar_service.resolve_logical_today(now, boundary_hour=4) == dt.date(2026, 3, 9)


def test_resolve_logical_today_returns_system_date_at_or_after_boundary():
    now = dt.datetime(2026, 3, 10, 4, 0)
    assert calendar_service.resolve_logical_today(now, boundary_hour=4) == dt.date(2026, 3, 10)


def test_resolve_logical_today_matches_system_date_when_boundary_is_zero():
    """境界時刻が0の場合、システム日付と一致すること（20章）。"""
    now = dt.datetime(2026, 3, 10, 0, 0)
    assert calendar_service.resolve_logical_today(now, boundary_hour=0) == dt.date(2026, 3, 10)

    now_late = dt.datetime(2026, 3, 10, 23, 59)
    assert calendar_service.resolve_logical_today(now_late, boundary_hour=0) == dt.date(2026, 3, 10)


def test_override_takes_priority_over_holiday_and_weekday_default(db_session):
    """個別指定が祝日設定を上書きすること（Phase2完了条件・必須観点、日種別優先順位）。"""
    target = dt.date(2026, 1, 1)  # 木曜（平日=PLAN既定）かつ祝日
    db_session.add(Holiday(holiday_date=target, name="元日"))
    db_session.add(CalendarDayOverride(target_date=target, day_type=DayType.PLAN, note="特訓日"))
    # merge: 他テストの起動時シードで既にday_type_defaultが存在していても実行順に依存させない
    db_session.merge(DayTypeDefault(weekday=target.weekday(), day_type=DayType.PLAN))
    db_session.flush()

    day_type = calendar_service.resolve_day_type(db_session, target, treat_holiday_as_buffer=True)

    assert day_type == DayType.PLAN


def test_holiday_treated_as_buffer_when_setting_enabled(db_session):
    """祝日の扱いが設定値に従って切り替わること（20章）。"""
    target = dt.date(2026, 1, 2)  # 金曜
    db_session.add(Holiday(holiday_date=target, name="振替休日"))
    db_session.merge(DayTypeDefault(weekday=target.weekday(), day_type=DayType.PLAN))
    db_session.flush()

    assert (
        calendar_service.resolve_day_type(db_session, target, treat_holiday_as_buffer=True)
        == DayType.BUFFER
    )
    assert (
        calendar_service.resolve_day_type(db_session, target, treat_holiday_as_buffer=False)
        == DayType.PLAN
    )


def test_weekday_default_used_when_no_override_or_holiday(db_session):
    target = dt.date(2026, 1, 3)  # 土曜
    db_session.merge(DayTypeDefault(weekday=target.weekday(), day_type=DayType.BUFFER))
    db_session.flush()

    assert (
        calendar_service.resolve_day_type(db_session, target, treat_holiday_as_buffer=True)
        == DayType.BUFFER
    )


def test_resolve_day_types_returns_empty_dict_when_range_inverted(db_session):
    """残計画日0のケースに相当する境界値で例外が発生しないこと。"""
    result = calendar_service.resolve_day_types(
        db_session, dt.date(2026, 5, 10), dt.date(2026, 5, 1), treat_holiday_as_buffer=True
    )
    assert result == {}


def test_resolve_load_coefficients_returns_empty_dict_when_range_inverted(db_session):
    """境界値: 期間が逆転している場合に例外が発生しないこと。"""
    goal = Goal(name="係数境界値検証", start_date=dt.date(2026, 1, 1), status=GoalStatus.ACTIVE)
    db_session.add(goal)
    db_session.flush()

    result = calendar_service.resolve_load_coefficients(
        db_session, goal.id, dt.date(2026, 5, 10), dt.date(2026, 5, 1)
    )

    assert result == {}


def test_resolve_load_coefficient_defaults_to_one_when_no_profile(db_session):
    goal = Goal(name="係数検証", start_date=dt.date(2026, 1, 1), status=GoalStatus.ACTIVE)
    db_session.add(goal)
    db_session.flush()

    coefficient = calendar_service.resolve_load_coefficient(
        db_session, goal.id, dt.date(2026, 3, 1)
    )

    assert coefficient == 1.0


def test_resolve_load_coefficient_uses_matching_profile(db_session):
    """負荷係数を変更しても総量が保存されること（分子・分母双方に用いる係数の解決の前提を検証）。"""
    goal = Goal(name="係数検証2", start_date=dt.date(2026, 1, 1), status=GoalStatus.ACTIVE)
    db_session.add(goal)
    db_session.flush()
    db_session.add(
        LoadProfile(
            goal_id=goal.id,
            date_from=dt.date(2026, 6, 1),
            date_to=dt.date(2026, 6, 30),
            coefficient=0.5,
        )
    )
    db_session.flush()

    assert (
        calendar_service.resolve_load_coefficient(db_session, goal.id, dt.date(2026, 6, 15)) == 0.5
    )
    assert (
        calendar_service.resolve_load_coefficient(db_session, goal.id, dt.date(2026, 7, 1)) == 1.0
    )
