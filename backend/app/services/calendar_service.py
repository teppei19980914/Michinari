"""カレンダー算出（設計書 ロジック・プロンプト編 3〜5章）。

1日の境界時刻の解決、日種別の解決、負荷係数の解決を担う。
HTTPに関する知識は持ち込まない（CLAUDE.md）。
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.constants.enums import DayType
from app.models.goal import LoadProfile
from app.models.setting import CalendarDayOverride, DayTypeDefault, Holiday

#: 曜日既定値が未登録の場合のフォールバック（起動時シードで全曜日投入されるため通常は到達しない）。
_DEFAULT_WEEKDAY_TYPE = DayType.PLAN


def resolve_logical_today(now: dt.datetime, boundary_hour: int) -> dt.date:
    """論理的な本日を算出する（3.1）。

    boundary_hour（0〜11）未満の時刻は前日として扱う。
    """
    if now.hour < boundary_hour:
        return (now - dt.timedelta(days=1)).date()
    return now.date()


def resolve_day_types(
    session: Session,
    date_from: dt.date,
    date_to: dt.date,
    treat_holiday_as_buffer: bool,
) -> dict[dt.date, DayType]:
    """期間内の日種別を一括解決する（4.1、19.2の性能設計に基づく一括取得）。

    date_from > date_to の場合は空の辞書を返す（残計画日0のケースで例外を発生させないため）。
    """
    result: dict[dt.date, DayType] = {}
    if date_from > date_to:
        return result

    overrides = {
        row.target_date: DayType(row.day_type)
        for row in session.query(CalendarDayOverride)
        .filter(
            CalendarDayOverride.target_date >= date_from,
            CalendarDayOverride.target_date <= date_to,
        )
        .all()
    }
    holidays = (
        {
            row.holiday_date
            for row in session.query(Holiday.holiday_date)
            .filter(Holiday.holiday_date >= date_from, Holiday.holiday_date <= date_to)
            .all()
        }
        if treat_holiday_as_buffer
        else set()
    )
    weekday_defaults = {
        row.weekday: DayType(row.day_type) for row in session.query(DayTypeDefault).all()
    }

    target_date = date_from
    while target_date <= date_to:
        if target_date in overrides:
            result[target_date] = overrides[target_date]
        elif target_date in holidays:
            result[target_date] = DayType.BUFFER
        else:
            result[target_date] = weekday_defaults.get(target_date.weekday(), _DEFAULT_WEEKDAY_TYPE)
        target_date += dt.timedelta(days=1)

    return result


def resolve_day_type(
    session: Session, target_date: dt.date, treat_holiday_as_buffer: bool
) -> DayType:
    """単一日の日種別を解決する（4.1）。複数日をまとめて扱う場合は resolve_day_types を使う。"""
    return resolve_day_types(session, target_date, target_date, treat_holiday_as_buffer)[
        target_date
    ]


def resolve_load_coefficients(
    session: Session, goal_id: int, date_from: dt.date, date_to: dt.date
) -> dict[dt.date, float]:
    """期間内の負荷係数を一括解決する（5.1）。該当レコードがない日は1.0とする。"""
    result: dict[dt.date, float] = {}
    if date_from > date_to:
        return result

    profiles = (
        session.query(LoadProfile)
        .filter(
            LoadProfile.goal_id == goal_id,
            LoadProfile.date_to >= date_from,
            LoadProfile.date_from <= date_to,
        )
        .all()
    )

    target_date = date_from
    while target_date <= date_to:
        coefficient = 1.0
        for profile in profiles:
            if profile.date_from <= target_date <= profile.date_to:
                coefficient = profile.coefficient
                break
        result[target_date] = coefficient
        target_date += dt.timedelta(days=1)

    return result


def resolve_load_coefficient(session: Session, goal_id: int, target_date: dt.date) -> float:
    """単一日の負荷係数を解決する（5.1）。"""
    return resolve_load_coefficients(session, goal_id, target_date, target_date)[target_date]
