"""スロットの取得、教材への割当、充足検証（設計書 ロジック・プロンプト編 9章）。

割当の算出は分（整数）で行う。時間（hour）への換算は表示・速度算出の直前にのみ行う
（services/duration.py、仕様書6.3）。
"""

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

#: 1分あたりの秒数（スロットの連続時間を分へ換算する際の除数）。
_SECONDS_PER_MINUTE = 60


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


def slot_duration_minutes(slot: ResourceSlot) -> int:
    """スロットの連続時間を分単位で算出する（保存しない、9.1）。"""
    start = dt.datetime.combine(dt.date.min, slot.start_time)
    end = dt.datetime.combine(dt.date.min, slot.end_time)
    return int((end - start).total_seconds() // _SECONDS_PER_MINUTE)


def compute_total_minutes_for_date(
    slots_by_weekday: dict[int, list[ResourceSlot]], target_date: dt.date
) -> int:
    """日 d に確保できる時間の総量 total_minutes(d)（9.1）。"""
    return sum(slot_duration_minutes(s) for s in slots_by_weekday.get(target_date.weekday(), []))


def effective_allocation_minutes(slot: ResourceSlot, allocated_minutes: int) -> int:
    """スロット s から目標へ実際に割り当てられる分数 min(alloc(g, s), duration(s))（9.1）。

    配分の設定後にスロットを短縮すると alloc > duration となりうる（仕様書NT-09。この状態は
    警告のみで保存を許容するため、算出側で安全に丸める必要がある）。
    """
    return min(allocated_minutes, slot_duration_minutes(slot))


def _environment_matches(material: Material, slot: ResourceSlot) -> bool:
    return (
        material.required_environment == Environment.ANY
        or material.required_environment == slot.environment
    )


def _block_minutes_matches(material: Material, available_minutes: int) -> bool:
    """教材の必要連続時間を、そのスロットへの配分時間と比較する（9.2 手順1）。

    スロットの連続時間ではなく配分時間と比べるのは、120分のスロットに30分しか配分して
    いない場合、そこで90分連続を要する教材を進めることは実際にはできないため。
    """
    if material.required_block_minutes is None:
        return True
    return material.required_block_minutes <= available_minutes


def allocate_day(
    weights: dict[int, MaterialWeight],
    slots_by_weekday: dict[int, list[ResourceSlot]],
    target_date: dt.date,
    allocated_minutes_by_slot: dict[int, int],
) -> dict[int, dict[int, float]]:
    """日 d における各教材への割当分数（9.2）を、スロットごとの内訳として算出する。

    `allocated_minutes_by_slot` は対象目標の slot_id → 配分分数（goal_slot_allocation）。
    戻り値は slot_id → {material_id: 割当分数}。日次報告の入力欄の初期値（仕様書6.5）が
    スロット別の値を必要とするため、教材単位へ合算せずに返す。合算は
    `sum_minutes_by_material` を用いる。
    """
    allocation: dict[int, dict[int, float]] = {}
    for slot in slots_by_weekday.get(target_date.weekday(), []):
        goal_share = effective_allocation_minutes(slot, allocated_minutes_by_slot.get(slot.id, 0))
        if goal_share <= 0:
            continue

        candidates = [
            material_id
            for material_id, state in weights.items()
            if state.remaining > 0
            and state.material.start_date <= target_date <= state.material.due_date
            and _environment_matches(state.material, slot)
            and _block_minutes_matches(state.material, goal_share)
        ]
        if not candidates:
            continue

        total_weight = sum(weights[material_id].weight for material_id in candidates)
        if total_weight <= 0:
            continue

        per_material = {
            material_id: goal_share * (weights[material_id].weight / total_weight)
            for material_id in candidates
        }
        allocation[slot.id] = per_material

    return allocation


def sum_minutes_by_material(allocation: dict[int, dict[int, float]]) -> dict[int, float]:
    """`allocate_day` のスロット別内訳を教材ごとの合計分数へ畳み込む。"""
    totals: dict[int, float] = defaultdict(float)
    for per_material in allocation.values():
        for material_id, minutes in per_material.items():
            totals[material_id] += minutes
    return dict(totals)


def validate_slot_sufficiency(
    session: Session,
    material: Material,
    treat_holiday_as_buffer: bool,
    allocated_minutes_by_slot: dict[int, int],
) -> bool:
    """教材の必要条件を満たす配分済みスロットが存在するかを検証する（9.4）。

    OFFは calendar_day_override でのみ設定可能なため、resolve_day_types による解決結果を
    そのまま使ってPLAN日の曜日集合を求める。

    検証対象を全スロットではなく「その目標が配分を持つスロット」に限定するのは、9.2の割当が
    配分済みスロットに対してのみ行われるため（配分していないスロットが条件を満たしていても
    その教材に時間は割り当たらない）。
    """
    day_types = calendar_service.resolve_day_types(
        session, material.start_date, material.due_date, treat_holiday_as_buffer
    )
    plan_weekdays = {d.weekday() for d, day_type in day_types.items() if day_type == DayType.PLAN}
    if not plan_weekdays:
        return False

    for slot in get_active_slots(session):
        available = effective_allocation_minutes(slot, allocated_minutes_by_slot.get(slot.id, 0))
        if available <= 0:
            continue
        if not _environment_matches(material, slot):
            continue
        if not _block_minutes_matches(material, available):
            continue
        slot_weekdays = {row.weekday for row in slot.weekdays}
        if slot_weekdays & plan_weekdays:
            return True

    return False
