"""カレンダー算出（設計書 ロジック・プロンプト編 3〜5章）。

1日の境界時刻の解決、日種別の解決、負荷係数の解決を担う。
日種別の個別指定・祝日データの取込（実装フェーズ分割計画書Phase4）もカレンダー領域の
関心事としてここに置く。HTTPに関する知識は持ち込まない（CLAUDE.md）。
"""

import csv
import datetime as dt
import hashlib
import io
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.constants.app_setting_keys import HOLIDAY_BUNDLED_CSV_SHA256, HOLIDAY_IMPORTED_VIA_MANUAL
from app.constants.enums import DayType
from app.models.goal import LoadProfile
from app.models.setting import AppSetting, CalendarDayOverride, DayTypeDefault, Holiday
from app.services import setting_reader
from app.services.exceptions import AppSettingNotFoundError, NotFoundError, ValidationError

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
        raise NotFoundError("CalendarDayOverride", target_date)
    session.delete(override)
    session.flush()


@dataclass(frozen=True)
class HolidayImportResult:
    """祝日CSV取込の結果（技術選定書6.3 手順6「取込件数と対象年の範囲を画面に表示する」）。"""

    imported_count: int
    year_from: int
    year_to: int


def parse_holiday_csv(csv_bytes: bytes) -> dict[dt.date, str]:
    """内閣府「国民の祝日」CSVを解析する（技術選定書6.3）。DBには触れない。

    文字コードはcp932（Shift-JISでは扱えない機種依存文字（丸数字等）に対応するため）、
    日付形式は `YYYY/M/D`（ゼロ埋めなし）。`import_holidays`（取込み本体）と
    `scripts/update_holiday_csv.py`（リリース時の取得CSVの検証）の両方がこの解析結果を
    使う（CLAUDE.md DRYの原則。開発Todo_スケジュール・ガントチャート_v1.1.md D-43）。
    """
    try:
        text = csv_bytes.decode("cp932")
    except UnicodeDecodeError as exc:
        raise ValidationError(
            "Holiday CSV has an invalid encoding (save as Shift-JIS/cp932)"
        ) from exc

    rows = list(csv.reader(io.StringIO(text, newline="")))
    if len(rows) <= 1:
        raise ValidationError("Holiday CSV has no valid rows")

    parsed: dict[dt.date, str] = {}
    for row in rows[1:]:  # 1行目はヘッダのためスキップする
        if not row or not row[0].strip():
            continue
        if len(row) < 2:
            raise ValidationError(f"Holiday CSV row has an invalid column count: {row}")
        try:
            holiday_date = dt.datetime.strptime(row[0].strip(), "%Y/%m/%d").date()
        except ValueError as exc:
            raise ValidationError(f"Holiday CSV has an invalid date format: {row[0]}") from exc
        parsed[holiday_date] = row[1].strip()

    if not parsed:
        raise ValidationError("Holiday CSV has no valid rows")

    return parsed


def import_holidays(session: Session, csv_bytes: bytes) -> HolidayImportResult:
    """内閣府「国民の祝日」CSVを取り込む（技術選定書6.2〜6.3）。

    取り込んだ年の範囲の既存レコードを先に削除してから全行を挿入する
    （同一年の重複祝日を残さないため）。
    """
    parsed = parse_holiday_csv(csv_bytes)
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


def mark_manual_holiday_import(session: Session) -> None:
    """手動インポート（`POST /calendar/holidays/import`）が行われたことを記録する。

    `import_holidays`自体は`import_bundled_holidays_if_needed`（同梱データの自動取込み）
    からも呼ばれる共有関数のため、ここでは呼ばない。API層（手動インポートの経路）から
    `import_holidays`成功後に明示的に呼び、`import_bundled_holidays_if_needed`の
    「手動データを古い同梱データで上書きしない」判定（D-44）に使う。
    """
    row = session.get(AppSetting, HOLIDAY_IMPORTED_VIA_MANUAL)
    if row is None:
        raise AppSettingNotFoundError(HOLIDAY_IMPORTED_VIA_MANUAL)
    row.value = "true"
    session.flush()


@dataclass(frozen=True)
class HolidayCoverage:
    """祝日データの収録範囲（`GET /holidays`、D-46の年範囲表示）。

    1件も取り込まれていない場合は`year_from`/`year_to`ともに`None`とする。
    """

    year_from: int | None
    year_to: int | None


def get_holiday_coverage(session: Session) -> HolidayCoverage:
    """収録済みの祝日の最初と最後の年を返す（`holiday`テーブル全体が対象）。"""
    year_from, year_to = session.query(
        func.min(Holiday.holiday_date), func.max(Holiday.holiday_date)
    ).one()
    if year_from is None or year_to is None:
        return HolidayCoverage(year_from=None, year_to=None)
    return HolidayCoverage(year_from=year_from.year, year_to=year_to.year)


def list_holidays(
    session: Session, date_from: dt.date | None, date_to: dt.date | None
) -> list[Holiday]:
    """期間内の祝日を日付の昇順で返す（`GET /holidays`）。

    どちらも省略した場合は空リストを返す（収録範囲の表示のみが目的の呼び出しに対応する、
    D-46「収録済みの年の範囲」表示はこの関数を呼ばずに`get_holiday_coverage`だけで足りる）。
    """
    if date_from is None or date_to is None:
        return []
    return (
        session.query(Holiday)
        .filter(Holiday.holiday_date >= date_from, Holiday.holiday_date <= date_to)
        .order_by(Holiday.holiday_date)
        .all()
    )


def import_bundled_holidays_if_needed(
    session: Session, csv_bytes: bytes
) -> HolidayImportResult | None:
    """同梱の祝日CSVが前回取り込んだものから変わっていればDBへ取り込む（D-44）。

    **呼び出し元の注意**: 本関数は実機起動時（`app/main.py`の`main()`）からのみ呼ぶこと。
    `bootstrap_database`（`TestClient`の`lifespan`経由で全APIテストが毎回実行する）には
    含めない。含めると、実世界の祝日データが全テストDBへ無条件に注入され、日付をまたぐ
    既存テストの`resolve_day_types`経由のノルマ計算結果が広範囲に変わってしまうため
    （開発Todo_スケジュール・ガントチャート_単位1_v1.0.md「重要な設計判断」1）。

    冪等性: 同梱CSVのSHA256が前回取り込んだ値と同じであれば何もしない。

    利用者が手動で取り込んだ新しいデータを古い同梱データで上書きしないため、**手動
    インポート（`import_holidays`を`POST /calendar/holidays/import`経由で呼んだ場合）が
    一度でも行われていれば**、既存の収録範囲（年）が同梱CSVの範囲以上である間は取り込ま
    ない（D-44）。この場合「前回取り込んだSHA256」は更新しない（実際には取り込んでいない
    ため）。

    手動インポートが一度も行われていない場合は、収録年の比較を行わず常に同梱データを
    適用する。これが無いと、同梱CSVが同じ年の範囲内の内容だけを訂正する更新（内閣府の
    祝日データは法改正等で既存年の日付が事後的に変わることがある）を、収録年が伸びない
    という理由だけで永久に取り込めなくなる不具合になる（独立レビューで指摘、2026-11-23）。

    戻り値:
        実際に取り込んだ場合はその結果、取り込まなかった場合は`None`。
    """
    csv_sha256 = hashlib.sha256(csv_bytes).hexdigest()
    row = session.get(AppSetting, HOLIDAY_BUNDLED_CSV_SHA256)
    if row is None:
        raise AppSettingNotFoundError(HOLIDAY_BUNDLED_CSV_SHA256)
    if csv_sha256 == row.value:
        return None

    if setting_reader.get_bool(session, HOLIDAY_IMPORTED_VIA_MANUAL):
        parsed = parse_holiday_csv(csv_bytes)
        bundled_year_to = max(holiday_date.year for holiday_date in parsed)
        current_coverage = get_holiday_coverage(session)
        if current_coverage.year_to is not None and current_coverage.year_to >= bundled_year_to:
            return None

    result = import_holidays(session, csv_bytes)
    row.value = csv_sha256
    session.flush()
    return result
