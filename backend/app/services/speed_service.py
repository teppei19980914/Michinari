"""実効速度の周回別算出、必要速度、完了予測日（設計書 ロジック・プロンプト編 8〜10章）。"""

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.orm import Session

from app.constants.domain import FORECAST_ITERATION_CAP_DAYS, MIN_SPEED_SAMPLE_COUNT
from app.constants.enums import DayType
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import DailyRecord, StudyLog
from app.models.setting import CalendarDayOverride
from app.services import calendar_service, cycle_service, slot_service
from app.services.slot_service import MaterialWeight


@dataclass(frozen=True)
class CycleSpeed:
    """周回別の実効速度算出結果（8.1）。"""

    sample_count: int
    speed: float  # 分量／時間


@dataclass(frozen=True)
class EffectiveSpeed:
    """完了予測に用いる実効速度（8.2）。"""

    speed: float
    cycle_used: int
    sample_count: int


class ForecastUnavailableReason(StrEnum):
    """完了予測日が算出できない理由（8.5、10.1）。"""

    NO_SPEED_DATA = "NO_SPEED_DATA"
    ITERATION_LIMIT_EXCEEDED = "ITERATION_LIMIT_EXCEEDED"


@dataclass(frozen=True)
class ForecastResult:
    """完了予測日の算出結果（10章）。"""

    forecast_date: dt.date | None
    overrun_days: int | None
    unavailable_reason: ForecastUnavailableReason | None


def compute_cycle_speed(session: Session, material_id: int, cycle_number: int) -> CycleSpeed | None:
    """周回 c の実効速度 speed(m, c) を算出する（8.1、8.4）。

    minutes_spent が NULL/0 の実績、および OFF日の実績は除外する。
    OFF は calendar_day_override でのみ設定可能なため（4.1）、override テーブルのみ参照すればよい。
    """
    rows = (
        session.query(StudyLog.amount_completed, StudyLog.minutes_spent, DailyRecord.record_date)
        .join(DailyRecord, StudyLog.daily_record_id == DailyRecord.id)
        .filter(
            StudyLog.material_id == material_id,
            StudyLog.cycle_number == cycle_number,
            StudyLog.minutes_spent.isnot(None),
            StudyLog.minutes_spent > 0,
        )
        .all()
    )
    if not rows:
        return None

    record_dates = {record_date for _, _, record_date in rows}
    off_dates = {
        row.target_date
        for row in session.query(CalendarDayOverride).filter(
            CalendarDayOverride.target_date.in_(record_dates),
            CalendarDayOverride.day_type == DayType.OFF,
        )
    }

    filtered = [
        (amount, minutes) for amount, minutes, record_date in rows if record_date not in off_dates
    ]
    if not filtered:
        return None

    total_amount = sum(amount for amount, _ in filtered)
    # filtered の各行は minutes_spent > 0 のクエリ条件を満たす行の部分集合のため、
    # total_hours は必ず正になる（0除算のガードは不要）。
    total_hours = sum(minutes for _, minutes in filtered) / 60

    return CycleSpeed(sample_count=len(filtered), speed=total_amount / total_hours)


def compute_effective_speed(
    session: Session, material: Material, current_cycle: int
) -> EffectiveSpeed | None:
    """完了予測に用いる実効速度 speed_eff(m) を算出する（8.2）。

    現在周回のサンプルが3件未満のとき、直近周回（現在周回-1）の値で代替する。
    """
    current = compute_cycle_speed(session, material.id, current_cycle)
    if current is not None and current.sample_count >= MIN_SPEED_SAMPLE_COUNT:
        return EffectiveSpeed(
            speed=current.speed, cycle_used=current_cycle, sample_count=current.sample_count
        )

    if current_cycle > 1:
        previous = compute_cycle_speed(session, material.id, current_cycle - 1)
        if previous is not None:
            return EffectiveSpeed(
                speed=previous.speed,
                cycle_used=current_cycle - 1,
                sample_count=previous.sample_count,
            )

    return None


def compute_weights(session: Session, materials: list[Material]) -> dict[int, MaterialWeight]:
    """スロット按分に用いる各教材の重み（必要時間比、9.2）を算出する。

    remaining・speed_eff は算出時点で固定であるため、日ループの外で一度だけ計算する
    （CLAUDE.md パフォーマンスチェック: N+1禁止）。
    """
    result: dict[int, MaterialWeight] = {}
    for material in materials:
        progress = cycle_service.get_material_progress(session, material)
        effective_speed = compute_effective_speed(session, material, progress.current_cycle)
        weight = (
            progress.remaining / effective_speed.speed
            if effective_speed is not None
            else progress.remaining
        )
        result[material.id] = MaterialWeight(
            material=material, remaining=progress.remaining, weight=weight
        )
    return result


def _daily_allocated_hours(
    session: Session,
    goal: Goal,
    target_material: Material,
    weights: dict[int, MaterialWeight],
    slots_by_weekday: dict[int, list],
    day_types: dict[dt.date, DayType],
    coefficients: dict[dt.date, float],
    target_date: dt.date,
) -> float:
    """日 d における対象教材への割当時間（負荷係数適用後）を算出する（9.3、10.1で共用）。"""
    if day_types.get(target_date) != DayType.PLAN:
        return 0.0
    allocation = slot_service.allocate_day(
        weights, slots_by_weekday, target_date, goal.resource_ratio
    )
    return allocation.get(target_material.id, 0.0) * coefficients[target_date]


def compute_required_speed(
    session: Session,
    goal: Goal,
    material: Material,
    materials_in_contention: list[Material],
    today: dt.date,
    treat_holiday_as_buffer: bool,
) -> float | None:
    """必要速度 required_speed(m) を算出する（9.3）。

    materials_in_contention は同一スロットを奪い合う教材の集合（対象教材自身を含む、
    通常は同一goal配下でis_active=trueの全教材）。available_hours(m) が0の場合は算出不能（None）。
    """
    day_types = calendar_service.resolve_day_types(
        session, today, material.due_date, treat_holiday_as_buffer
    )
    if not day_types:
        return None
    coefficients = calendar_service.resolve_load_coefficients(
        session, goal.id, today, material.due_date
    )
    weights = compute_weights(session, materials_in_contention)
    slots_by_weekday = slot_service.group_slots_by_weekday(slot_service.get_active_slots(session))

    available_hours = sum(
        _daily_allocated_hours(
            session, goal, material, weights, slots_by_weekday, day_types, coefficients, d
        )
        for d in day_types
    )
    if available_hours <= 0:
        return None

    progress = cycle_service.get_material_progress(session, material)
    return progress.remaining / available_hours


def compute_forecast_date(
    session: Session,
    goal: Goal,
    material: Material,
    materials_in_contention: list[Material],
    today: dt.date,
    treat_holiday_as_buffer: bool,
) -> ForecastResult:
    """完了予測日と乖離日数を算出する（10章）。バッファ日は累積対象から除外する（10.2）。

    materials_in_contention は compute_required_speed と同様、対象教材自身を含む競合教材集合。
    """
    progress = cycle_service.get_material_progress(session, material)
    effective_speed = compute_effective_speed(session, material, progress.current_cycle)
    if effective_speed is None:
        return ForecastResult(
            forecast_date=None,
            overrun_days=None,
            unavailable_reason=ForecastUnavailableReason.NO_SPEED_DATA,
        )

    required_hours = progress.remaining / effective_speed.speed

    limit_date = material.due_date + dt.timedelta(days=FORECAST_ITERATION_CAP_DAYS)
    day_types = calendar_service.resolve_day_types(
        session, today, limit_date, treat_holiday_as_buffer
    )
    coefficients = calendar_service.resolve_load_coefficients(session, goal.id, today, limit_date)
    weights = compute_weights(session, materials_in_contention)
    slots_by_weekday = slot_service.group_slots_by_weekday(slot_service.get_active_slots(session))

    accumulated = 0.0
    current_date = today
    while accumulated < required_hours:
        if current_date > limit_date:
            return ForecastResult(
                forecast_date=None,
                overrun_days=None,
                unavailable_reason=ForecastUnavailableReason.ITERATION_LIMIT_EXCEEDED,
            )
        accumulated += _daily_allocated_hours(
            session,
            goal,
            material,
            weights,
            slots_by_weekday,
            day_types,
            coefficients,
            current_date,
        )
        current_date += dt.timedelta(days=1)

    forecast_date = current_date - dt.timedelta(days=1)
    overrun_days = (forecast_date - material.due_date).days
    return ForecastResult(
        forecast_date=forecast_date, overrun_days=overrun_days, unavailable_reason=None
    )
