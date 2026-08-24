"""スロットの取得、教材への割当、充足検証（設計書 ロジック・プロンプト編 9章）。"""

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy.orm import Session, joinedload

from app.constants.enums import DayType, Environment
from app.models.material import Material
from app.models.resource import ResourceSlot
from app.services import calendar_service

# speed_service には依存しない（speed_service -> slot_service の一方向依存を保つための設計上の制約。
# 重み算出（remaining/speed_eff）は speed_service.compute_weights が担う）。


@dataclass(frozen=True)
class MaterialWeight:
    """スロット按分に用いる教材の状態（9.2）。"""

    material: Material
    remaining: float
    weight: float


def get_active_slots(session: Session) -> list[ResourceSlot]:
    """有効なスロットを、適用曜日を含めて取得する。"""
    return (
        session.query(ResourceSlot)
        .options(joinedload(ResourceSlot.weekdays))
        .filter(ResourceSlot.is_active.is_(True))
        .all()
    )


def group_slots_by_weekday(slots: list[ResourceSlot]) -> dict[int, list[ResourceSlot]]:
    """スロットを適用曜日ごとにグルーピングする。"""
    grouped: dict[int, list[ResourceSlot]] = defaultdict(list)
    for slot in slots:
        for weekday_row in slot.weekdays:
            grouped[weekday_row.weekday].append(slot)
    return grouped


def slot_duration_hours(slot: ResourceSlot) -> float:
    """スロットの連続時間を時間単位で算出する（保存しない、9.1）。"""
    start = dt.datetime.combine(dt.date.min, slot.start_time)
    end = dt.datetime.combine(dt.date.min, slot.end_time)
    return (end - start).total_seconds() / 3600


def compute_total_hours_for_date(
    slots_by_weekday: dict[int, list[ResourceSlot]], target_date: dt.date
) -> float:
    """日 d に確保できる時間の総量 total_hours(d)（9.1）。"""
    return sum(slot_duration_hours(s) for s in slots_by_weekday.get(target_date.weekday(), []))


def _environment_matches(material: Material, slot: ResourceSlot) -> bool:
    return (
        material.required_environment == Environment.ANY
        or material.required_environment == slot.environment
    )


def _block_minutes_matches(material: Material, slot: ResourceSlot) -> bool:
    if material.required_block_minutes is None:
        return True
    return material.required_block_minutes <= slot_duration_hours(slot) * 60


def allocate_day(
    weights: dict[int, MaterialWeight],
    slots_by_weekday: dict[int, list[ResourceSlot]],
    target_date: dt.date,
    goal_resource_ratio: float,
) -> dict[int, float]:
    """日 d における各教材への割当時間（H(g,d)に占める配分、9.2）を算出する。"""
    allocation: dict[int, float] = defaultdict(float)
    for slot in slots_by_weekday.get(target_date.weekday(), []):
        candidates = [
            material_id
            for material_id, state in weights.items()
            if state.remaining > 0
            and state.material.start_date <= target_date <= state.material.due_date
            and _environment_matches(state.material, slot)
            and _block_minutes_matches(state.material, slot)
        ]
        if not candidates:
            continue

        total_weight = sum(weights[material_id].weight for material_id in candidates)
        if total_weight <= 0:
            continue

        goal_share = slot_duration_hours(slot) * goal_resource_ratio
        for material_id in candidates:
            allocation[material_id] += goal_share * (weights[material_id].weight / total_weight)

    return dict(allocation)


def validate_slot_sufficiency(
    session: Session, material: Material, treat_holiday_as_buffer: bool
) -> bool:
    """教材の必要条件を満たすスロットが存在するかを検証する（9.4）。

    OFFは calendar_day_override でのみ設定可能なため、resolve_day_types による解決結果を
    そのまま使ってPLAN日の曜日集合を求める。
    """
    day_types = calendar_service.resolve_day_types(
        session, material.start_date, material.due_date, treat_holiday_as_buffer
    )
    plan_weekdays = {d.weekday() for d, day_type in day_types.items() if day_type == DayType.PLAN}
    if not plan_weekdays:
        return False

    for slot in get_active_slots(session):
        if not _environment_matches(material, slot):
            continue
        if not _block_minutes_matches(material, slot):
            continue
        slot_weekdays = {row.weekday for row in slot.weekdays}
        if slot_weekdays & plan_weekdays:
            return True

    return False
