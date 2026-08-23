"""カレンダー算出（設計書 ロジック・プロンプト編 3〜5章）。

1日の境界時刻の解決、日種別の解決、負荷係数の解決を担う。
日種別の個別指定・祝日データの取込（実装フェーズ分割計画書Phase4）もカレンダー領域の
関心事としてここに置く。HTTPに関する知識は持ち込まない（CLAUDE.md）。
"""

import csv
import datetime as dt
import io
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.constants.enums import DayType
from app.models.goal import LoadProfile
from app.models.setting import CalendarDayOverride, DayTypeDefault, Holiday
from app.services.exceptions import NotFoundError, ValidationError

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


def set_day_type_override(
    session: Session, target_date: dt.date, day_type: DayType, note: str | None
) -> CalendarDayOverride:
    """日種別の個別指定を追加・更新する（データ構造編6.2 PUT /calendar/{date}/day-type）。

    個別指定は祝日設定より優先されるため（4.1、日種別優先順位）、OFFを含む全ての
    DayType値を許容する。
    """
    override = session.get(CalendarDayOverride, target_date)
    if override is None:
        override = CalendarDayOverride(target_date=target_date, day_type=day_type, note=note)
        session.add(override)
    else:
        override.day_type = day_type
        override.note = note
    session.flush()
    return override


def clear_day_type_override(session: Session, target_date: dt.date) -> None:
    """日種別の個別指定を解除する（データ構造編6.2 DELETE /calendar/{date}/day-type）。"""
    override = session.get(CalendarDayOverride, target_date)
    if override is None:
        raise NotFoundError("日種別個別指定", target_date)
    session.delete(override)
    session.flush()


@dataclass(frozen=True)
class HolidayImportResult:
    """祝日CSV取込の結果（技術選定書6.3 手順6「取込件数と対象年の範囲を画面に表示する」）。"""

    imported_count: int
    year_from: int
    year_to: int


def import_holidays(session: Session, csv_bytes: bytes) -> HolidayImportResult:
    """内閣府「国民の祝日」CSVを取り込む（技術選定書6.2〜6.3）。

    文字コードはcp932（Shift-JISでは扱えない機種依存文字（丸数字等）に対応するため）、
    日付形式は `YYYY/M/D`（ゼロ埋めなし）。取り込んだ年の範囲の既存レコードを
    先に削除してから全行を挿入する（同一年の重複祝日を残さないため）。
    """
    try:
        text = csv_bytes.decode("cp932")
    except UnicodeDecodeError as exc:
        raise ValidationError(
            "祝日CSVの文字コードが不正です（Shift-JIS/cp932で保存してください）"
        ) from exc

    rows = list(csv.reader(io.StringIO(text, newline="")))
    if len(rows) <= 1:
        raise ValidationError("祝日CSVに有効な行がありません")

    parsed: dict[dt.date, str] = {}
    for row in rows[1:]:  # 1行目はヘッダのためスキップする
        if not row or not row[0].strip():
            continue
        if len(row) < 2:
            raise ValidationError(f"祝日CSVの列数が不正です: {row}")
        try:
            holiday_date = dt.datetime.strptime(row[0].strip(), "%Y/%m/%d").date()
        except ValueError as exc:
            raise ValidationError(f"祝日CSVの日付形式が不正です: {row[0]}") from exc
        parsed[holiday_date] = row[1].strip()

    if not parsed:
        raise ValidationError("祝日CSVに有効な行がありません")

    years = {holiday_date.year for holiday_date in parsed}
    year_from, year_to = min(years), max(years)
    session.query(Holiday).filter(
        Holiday.holiday_date >= dt.date(year_from, 1, 1),
        Holiday.holiday_date <= dt.date(year_to, 12, 31),
    ).delete()
    session.flush()
    for holiday_date, name in parsed.items():
        session.add(Holiday(holiday_date=holiday_date, name=name))
    session.flush()
    return HolidayImportResult(imported_count=len(parsed), year_from=year_from, year_to=year_to)
