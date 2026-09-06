"""calendar_service のテスト（ロジック・プロンプト編 3〜5章、20章の検証観点、
技術選定書6章、実装フェーズ分割計画書Phase4）。"""

import datetime as dt

import pytest

from app.constants.enums import DayType, GoalStatus
from app.models.goal import Goal, LoadProfile
from app.models.setting import CalendarDayOverride, DayTypeDefault, Holiday
from app.services import calendar_service
from app.services.exceptions import NotFoundError, ValidationError


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


# --- 日種別の個別指定（データ構造編6.2、Phase4） ---


def test_set_day_type_override_creates_new_override(db_session):
    target = dt.date(2026, 4, 1)

    override = calendar_service.set_day_type_override(db_session, target, DayType.OFF, "特別休止日")

    assert override.day_type == DayType.OFF
    assert override.note == "特別休止日"
    assert db_session.get(CalendarDayOverride, target) is not None


def test_set_day_type_override_updates_existing_override(db_session):
    target = dt.date(2026, 4, 2)
    db_session.add(CalendarDayOverride(target_date=target, day_type=DayType.BUFFER, note="旧"))
    db_session.flush()

    calendar_service.set_day_type_override(db_session, target, DayType.PLAN, "新")

    override = db_session.get(CalendarDayOverride, target)
    assert override.day_type == DayType.PLAN
    assert override.note == "新"


def test_clear_day_type_override_removes_existing(db_session):
    target = dt.date(2026, 4, 3)
    db_session.add(CalendarDayOverride(target_date=target, day_type=DayType.BUFFER))
    db_session.flush()

    calendar_service.clear_day_type_override(db_session, target)

    assert db_session.get(CalendarDayOverride, target) is None


def test_clear_day_type_override_missing_raises_not_found(db_session):
    with pytest.raises(NotFoundError):
        calendar_service.clear_day_type_override(db_session, dt.date(2026, 4, 4))


# --- 祝日CSVの取込（技術選定書6.2〜6.3） ---


def _holiday_csv_bytes(rows: list[tuple[str, str]]) -> bytes:
    header = "国民の祝日・休日月日,国民の祝日・休日名称"
    lines = [header] + [f"{date_text},{name}" for date_text, name in rows]
    return ("\r\n".join(lines) + "\r\n").encode("cp932")


def test_import_holidays_parses_cp932_csv_and_inserts_rows(db_session):
    content = _holiday_csv_bytes([("2026/1/1", "元日"), ("2026/1/12", "成人の日")])

    result = calendar_service.import_holidays(db_session, content)

    assert result.imported_count == 2
    assert result.year_from == 2026
    assert result.year_to == 2026
    assert db_session.get(Holiday, dt.date(2026, 1, 1)).name == "元日"
    assert db_session.get(Holiday, dt.date(2026, 1, 12)).name == "成人の日"


def test_import_holidays_replaces_existing_rows_within_year_range(db_session):
    db_session.add(Holiday(holiday_date=dt.date(2026, 3, 20), name="旧データ"))
    db_session.flush()

    content = _holiday_csv_bytes([("2026/1/1", "元日")])
    result = calendar_service.import_holidays(db_session, content)

    assert result.imported_count == 1
    assert db_session.get(Holiday, dt.date(2026, 3, 20)) is None
    assert db_session.get(Holiday, dt.date(2026, 1, 1)) is not None


def test_import_holidays_rejects_invalid_encoding(db_session):
    with pytest.raises(ValidationError):
        calendar_service.import_holidays(db_session, bytes([0x81, 0xFF]))


def test_import_holidays_rejects_malformed_date(db_session):
    content = "国民の祝日・休日月日,国民の祝日・休日名称\r\n2026-01-01,元日\r\n".encode("cp932")

    with pytest.raises(ValidationError):
        calendar_service.import_holidays(db_session, content)


def test_import_holidays_rejects_header_only_csv(db_session):
    content = "国民の祝日・休日月日,国民の祝日・休日名称\r\n".encode("cp932")

    with pytest.raises(ValidationError):
        calendar_service.import_holidays(db_session, content)


def test_import_holidays_rejects_empty_bytes(db_session):
    with pytest.raises(ValidationError):
        calendar_service.import_holidays(db_session, b"")


def test_import_holidays_skips_blank_lines_between_rows(db_session):
    """内閣府CSVは末尾に空行を含むことがあるため、空行は無視して取り込む。"""
    content = ("国民の祝日・休日月日,国民の祝日・休日名称\r\n\r\n2026/1/1,元日\r\n").encode("cp932")

    result = calendar_service.import_holidays(db_session, content)

    assert result.imported_count == 1


def test_import_holidays_rejects_row_missing_name_column(db_session):
    content = ("国民の祝日・休日月日,国民の祝日・休日名称\r\n2026/1/1\r\n").encode("cp932")

    with pytest.raises(ValidationError):
        calendar_service.import_holidays(db_session, content)


def test_import_holidays_rejects_when_only_blank_rows_present(db_session):
    content = ("国民の祝日・休日月日,国民の祝日・休日名称\r\n\r\n").encode("cp932")

    with pytest.raises(ValidationError):
        calendar_service.import_holidays(db_session, content)
