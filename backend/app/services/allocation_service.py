"""目標へのスロット別リソース配分（設計書 データ構造編5.2 goal_slot_allocation、
仕様書6.2「リソース配分タブ」、要件定義書R-07・R-84〜R-87）。

配分の上限はスロット単位で判定する（あるスロットについて、ACTIVEな目標の配分分数の合計が
そのスロットの連続時間を超えないこと）。合計計算に含めるのは EXAM・READING の目標であり、
WORK は対象外とする（配分の要否は「自由な時間に行う活動か否か」で決まる。R-64・R-74）。
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.constants.enums import GoalCategory, GoalStatus
from app.models.goal import Goal
from app.models.resource import GoalSlotAllocation, ResourceSlot
from app.services import slot_service
from app.services.exceptions import ResourceAllocationExceededError, ValidationError

#: リソース配分を持てない目標種別（要件定義書R-74）。
_UNSUPPORTED_CATEGORIES = (GoalCategory.WORK,)

#: 配分の合計計算に算入する目標の状態（PAUSED・CLOSEDは解放済みとして算入しない。仕様書7.1）。
_COUNTED_STATUSES = (GoalStatus.ACTIVE,)


@dataclass(frozen=True)
class SlotAllocationView:
    """リソース配分タブ1行分の表示情報（仕様書6.2）。"""

    slot_id: int
    slot_name: str
    environment: str
    weekdays: list[int]
    duration_minutes: int
    #: 本目標への配分分数。
    minutes: int
    #: 他目標（ACTIVE）の配分分数の合計。空き時間 = duration_minutes - others_minutes。
    others_minutes: int


def ensure_allocatable(goal: Goal) -> None:
    """リソース配分を設定できる目標かを検証する（WORKのみ不可）。"""
    if goal.category in _UNSUPPORTED_CATEGORIES:
        raise ValidationError("仕事目標にはリソース配分を設定できません")


def get_allocation_minutes(session: Session, goal_id: int) -> dict[int, int]:
    """目標の slot_id → 配分分数。行が無いスロットは辞書に含めない（＝0分）。"""
    rows = session.query(GoalSlotAllocation).filter(GoalSlotAllocation.goal_id == goal_id).all()
    return {row.slot_id: row.minutes for row in rows}


def sum_allocated_minutes(session: Session, goal_id: int) -> int:
    """目標に配分されている分数の合計（開始・復帰条件の判定に用いる）。"""
    return sum(get_allocation_minutes(session, goal_id).values())


def minutes_by_slot(session: Session, exclude_goal_id: int | None = None) -> dict[int, int]:
    """スロットごとの、ACTIVEな目標の配分分数の合計（`exclude_goal_id` の分は除く）。

    リソース設定画面の空き時間表示（仕様書6.3）と、配分の上限検証の双方で使う。
    """
    query = (
        session.query(GoalSlotAllocation.slot_id, GoalSlotAllocation.minutes)
        .join(Goal, Goal.id == GoalSlotAllocation.goal_id)
        .filter(Goal.status.in_(_COUNTED_STATUSES))
    )
    if exclude_goal_id is not None:
        query = query.filter(GoalSlotAllocation.goal_id != exclude_goal_id)

    totals: dict[int, int] = {}
    for slot_id, minutes in query.all():
        totals[slot_id] = totals.get(slot_id, 0) + minutes
    return totals


def validate_capacity(
    session: Session, candidate_minutes: dict[int, int], exclude_goal_id: int
) -> None:
    """候補の配分を適用したとき、いずれのスロットも容量を超えないことを検証する。

    超過するスロットが複数ある場合は、最初の1件をエラーとして返す（画面上は1件ずつ解消して
    もらう想定。仕様書NT-04は保存拒否）。
    """
    others = minutes_by_slot(session, exclude_goal_id)
    slots = {slot.id: slot for slot in session.query(ResourceSlot).all()}
    for slot_id in sorted(candidate_minutes):
        slot = slots.get(slot_id)
        if slot is None:
            continue
        total = others.get(slot_id, 0) + candidate_minutes[slot_id]
        capacity = slot_service.slot_duration_minutes(slot)
        if total > capacity:
            raise ResourceAllocationExceededError(slot.name, total, capacity)


def list_allocations(session: Session, goal: Goal) -> list[SlotAllocationView]:
    """全スロットを行として返す（未配分のスロットは minutes=0）。仕様書6.2の入力表。"""
    current = get_allocation_minutes(session, goal.id)
    others = minutes_by_slot(session, goal.id)
    slots = session.query(ResourceSlot).order_by(ResourceSlot.display_order).all()
    return [
        SlotAllocationView(
            slot_id=slot.id,
            slot_name=slot.name,
            environment=slot.environment.value,
            weekdays=sorted(row.weekday for row in slot.weekdays),
            duration_minutes=slot_service.slot_duration_minutes(slot),
            minutes=current.get(slot.id, 0),
            others_minutes=others.get(slot.id, 0),
        )
        for slot in slots
    ]


def replace_allocations(
    session: Session, goal: Goal, minutes_by_slot_id: dict[int, int]
) -> list[SlotAllocationView]:
    """目標のスロット別配分を一括更新する（仕様書6.2、PUT /goals/{id}/slot-allocations）。

    0分の指定は行を作らない（行の非存在と minutes=0 を同義とするため。データ構造編5.2）。
    容量検証はACTIVEな目標に対してのみ行う（DRAFT・PAUSEDの目標は合計計算に算入されず、
    開始・復帰の時点であらためて検証される。仕様書7.1）。
    """
    ensure_allocatable(goal)
    for slot_id, minutes in minutes_by_slot_id.items():
        if minutes < 0:
            raise ValidationError("配分時間は0以上で入力してください")
        if session.get(ResourceSlot, slot_id) is None:
            raise ValidationError("存在しない時間枠が指定されています")

    positive = {slot_id: minutes for slot_id, minutes in minutes_by_slot_id.items() if minutes > 0}
    if goal.status in _COUNTED_STATUSES:
        validate_capacity(session, positive, exclude_goal_id=goal.id)

    session.query(GoalSlotAllocation).filter(GoalSlotAllocation.goal_id == goal.id).delete()
    session.flush()
    for slot_id in sorted(positive):
        session.add(GoalSlotAllocation(goal_id=goal.id, slot_id=slot_id, minutes=positive[slot_id]))
    session.flush()
    return list_allocations(session, goal)
