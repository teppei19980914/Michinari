"""allocation_service のテスト（データ構造編5.2 goal_slot_allocation、仕様書6.2・7.1、
要件定義書R-07・R-64・R-74・R-84〜R-87）。
"""

import datetime as dt

import pytest

from app.constants.enums import Environment, GoalCategory, GoalStatus
from app.models.goal import Goal
from app.services import allocation_service, resource_service
from app.services.exceptions import ResourceAllocationExceededError, ValidationError


def _make_goal(session, category=GoalCategory.EXAM, status=GoalStatus.DRAFT, name="目標A") -> Goal:
    goal = Goal(category=category, name=name, start_date=dt.date(2026, 1, 1), status=status)
    session.add(goal)
    session.flush()
    return goal


def _make_slot(session, name="夜", start=dt.time(20, 0), end=dt.time(22, 0)):
    return resource_service.create_slot(
        session,
        name=name,
        start_time=start,
        end_time=end,
        environment=Environment.PC,
        weekdays=[0, 1, 2, 3, 4, 5, 6],
    )


def test_replace_allocations_stores_only_positive_minutes(db_session):
    """0分の指定は行を作らない（行の非存在と0分を同義とする。データ構造編5.2）。"""
    goal = _make_goal(db_session)
    slot_a = _make_slot(db_session, name="朝", start=dt.time(6, 0), end=dt.time(7, 0))
    slot_b = _make_slot(db_session, name="夜")

    allocation_service.replace_allocations(db_session, goal, {slot_a.id: 30, slot_b.id: 0})

    assert allocation_service.get_allocation_minutes(db_session, goal.id) == {slot_a.id: 30}
    assert allocation_service.sum_allocated_minutes(db_session, goal.id) == 30


def test_replace_allocations_is_idempotent_replacement(db_session):
    """一括更新は置き換えであり、送信されなかった枠の配分は消えること。"""
    goal = _make_goal(db_session)
    slot_a = _make_slot(db_session, name="朝", start=dt.time(6, 0), end=dt.time(7, 0))
    slot_b = _make_slot(db_session, name="夜")
    allocation_service.replace_allocations(db_session, goal, {slot_a.id: 30, slot_b.id: 60})

    allocation_service.replace_allocations(db_session, goal, {slot_b.id: 45})

    assert allocation_service.get_allocation_minutes(db_session, goal.id) == {slot_b.id: 45}


def test_replace_allocations_rejects_exceeding_capacity_for_active_goal(db_session):
    """ACTIVEな目標の配分更新は、スロット単位の上限を超えると拒否される（仕様書NT-04）。"""
    slot = _make_slot(db_session)  # 120分
    other = _make_goal(db_session, status=GoalStatus.ACTIVE, name="他の目標")
    allocation_service.replace_allocations(db_session, other, {slot.id: 90})
    goal = _make_goal(db_session, status=GoalStatus.ACTIVE)

    with pytest.raises(ResourceAllocationExceededError):
        allocation_service.replace_allocations(db_session, goal, {slot.id: 31})


def test_replace_allocations_allows_exceeding_for_draft_goal(db_session):
    """DRAFT・PAUSEDの目標は合計計算に算入されないため、設定時点では上限検証しない。

    開始・復帰の時点であらためて検証される（仕様書7.1）。
    """
    slot = _make_slot(db_session)  # 120分
    other = _make_goal(db_session, status=GoalStatus.ACTIVE, name="他の目標")
    allocation_service.replace_allocations(db_session, other, {slot.id: 120})
    goal = _make_goal(db_session, status=GoalStatus.DRAFT)

    allocation_service.replace_allocations(db_session, goal, {slot.id: 60})

    assert allocation_service.get_allocation_minutes(db_session, goal.id) == {slot.id: 60}


def test_replace_allocations_rejects_work_goal(db_session):
    """仕事目標は配分の対象外（要件定義書R-74）。"""
    slot = _make_slot(db_session)
    goal = _make_goal(db_session, category=GoalCategory.WORK)

    with pytest.raises(ValidationError):
        allocation_service.replace_allocations(db_session, goal, {slot.id: 30})


def test_replace_allocations_accepts_reading_goal(db_session):
    """読書目標は配分の対象に含める（要件定義書R-64。仕事とは扱いが異なる）。"""
    slot = _make_slot(db_session)
    goal = _make_goal(db_session, category=GoalCategory.READING)

    allocation_service.replace_allocations(db_session, goal, {slot.id: 30})

    assert allocation_service.get_allocation_minutes(db_session, goal.id) == {slot.id: 30}


def test_minutes_by_slot_counts_only_active_goals(db_session):
    """合計計算に算入するのはACTIVEな目標のみ（PAUSED・CLOSEDは解放済み。仕様書7.1）。"""
    slot = _make_slot(db_session)
    active = _make_goal(db_session, status=GoalStatus.ACTIVE, name="進行中")
    paused = _make_goal(db_session, status=GoalStatus.PAUSED, name="一時停止")
    allocation_service.replace_allocations(db_session, active, {slot.id: 40})
    allocation_service.replace_allocations(db_session, paused, {slot.id: 50})

    assert allocation_service.minutes_by_slot(db_session) == {slot.id: 40}
    assert allocation_service.minutes_by_slot(db_session, exclude_goal_id=active.id) == {}


def test_list_allocations_returns_every_slot_with_free_minutes(db_session):
    """全スロットを行として返し、未配分の枠は0分とすること（仕様書6.2の入力表）。"""
    slot_a = _make_slot(db_session, name="朝", start=dt.time(6, 0), end=dt.time(7, 0))
    slot_b = _make_slot(db_session, name="夜")
    other = _make_goal(db_session, status=GoalStatus.ACTIVE, name="他の目標")
    allocation_service.replace_allocations(db_session, other, {slot_b.id: 30})
    goal = _make_goal(db_session)
    allocation_service.replace_allocations(db_session, goal, {slot_a.id: 20})

    views = {view.slot_id: view for view in allocation_service.list_allocations(db_session, goal)}

    assert views[slot_a.id].minutes == 20
    assert views[slot_a.id].others_minutes == 0
    assert views[slot_b.id].minutes == 0
    assert views[slot_b.id].others_minutes == 30
    assert views[slot_b.id].duration_minutes == 120
    assert views[slot_b.id].is_over_capacity is False


def test_validate_capacity_ignores_unknown_slot_ids(db_session):
    """存在しないスロットIDは容量検証の対象外（削除直後の競合でも例外にしない）。"""
    goal = _make_goal(db_session, status=GoalStatus.ACTIVE)

    allocation_service.validate_capacity(db_session, {9999: 999}, exclude_goal_id=goal.id)
