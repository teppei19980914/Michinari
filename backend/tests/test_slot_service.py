"""slot_service のテスト（ロジック・プロンプト編 9章、20章の検証観点）。"""

import datetime as dt

import pytest

from app.constants.enums import DayType, Environment, GoalStatus
from app.models.goal import Goal
from app.models.material import Material
from app.models.resource import ResourceSlot, ResourceSlotWeekday
from app.models.setting import CalendarDayOverride
from app.services import slot_service
from app.services.slot_service import MaterialWeight


def _make_goal(db_session) -> Goal:
    goal = Goal(name="スロット検証", start_date=dt.date(2026, 1, 1), status=GoalStatus.ACTIVE)
    db_session.add(goal)
    db_session.flush()
    return goal


def _make_material(
    db_session,
    goal_id: int,
    required_environment: Environment = Environment.ANY,
    required_block_minutes: int | None = None,
) -> Material:
    material = Material(
        goal_id=goal_id,
        name="教材",
        unit_label="問",
        total_amount=100,
        planned_cycles=1,
        start_date=dt.date(2026, 1, 1),
        due_date=dt.date(2026, 12, 31),
        required_environment=required_environment,
        required_block_minutes=required_block_minutes,
        display_order=1,
    )
    db_session.add(material)
    db_session.flush()
    return material


def _make_slot(
    db_session,
    start_time: dt.time,
    end_time: dt.time,
    environment: Environment,
    weekdays: list[int],
) -> ResourceSlot:
    slot = ResourceSlot(
        name="スロット",
        start_time=start_time,
        end_time=end_time,
        environment=environment,
        display_order=1,
    )
    db_session.add(slot)
    db_session.flush()
    for weekday in weekdays:
        db_session.add(ResourceSlotWeekday(slot_id=slot.id, weekday=weekday))
    db_session.flush()
    return slot


def _full_allocation(slots_by_weekday: dict) -> dict[int, int]:
    """全スロットの連続時間を丸ごと配分した状態（比率方式の resource_ratio=1.0 相当）。"""
    return {
        slot.id: slot_service.slot_duration_minutes(slot)
        for slots in slots_by_weekday.values()
        for slot in slots
    }


def _half_allocation(slots_by_weekday: dict) -> dict[int, int]:
    """全スロットの連続時間の半分を配分した状態（resource_ratio=0.5 相当）。"""
    return {
        slot.id: slot_service.slot_duration_minutes(slot) // 2
        for slots in slots_by_weekday.values()
        for slot in slots
    }


def _allocation_for_all_slots(db_session) -> dict[int, int]:
    """DB上の全スロットを丸ごと配分した状態（充足検証は配分済みスロットのみを見るため）。"""
    return {
        slot.id: slot_service.slot_duration_minutes(slot)
        for slot in db_session.query(ResourceSlot).all()
    }


def test_slot_duration_minutes_computed_from_start_and_end():
    slot = ResourceSlot(
        name="s",
        start_time=dt.time(6, 0),
        end_time=dt.time(7, 30),
        environment=Environment.ANY,
        display_order=1,
    )
    assert slot_service.slot_duration_minutes(slot) == 90


def test_environment_matching_respects_any_and_specific(db_session):
    """環境タグと必要連続時間による適合判定が正しいこと（20章）。"""
    goal = _make_goal(db_session)
    pc_material = _make_material(db_session, goal.id, required_environment=Environment.PC)
    mobile_slot = _make_slot(
        db_session, dt.time(7, 0), dt.time(7, 30), Environment.MOBILE, weekdays=[0]
    )
    pc_slot = _make_slot(db_session, dt.time(20, 0), dt.time(21, 0), Environment.PC, weekdays=[0])
    db_session.flush()

    weights = {pc_material.id: MaterialWeight(material=pc_material, remaining=100, weight=100)}
    slots_by_weekday = slot_service.group_slots_by_weekday([mobile_slot, pc_slot])

    allocation = slot_service.allocate_day(
        weights,
        slots_by_weekday,
        dt.date(2026, 1, 5),
        _full_allocation(slots_by_weekday),
    )  # 2026-01-05は月曜(weekday=0)

    # PC限定教材はmobileスロットに割り当てられず、pcスロット分(60分)のみ割り当てられる
    assert slot_service.sum_minutes_by_material(allocation)[pc_material.id] == 60


def test_block_minutes_matching_excludes_short_slots(db_session):
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, required_block_minutes=90)
    short_slot = _make_slot(
        db_session, dt.time(6, 0), dt.time(6, 30), Environment.ANY, weekdays=[0]
    )
    long_slot = _make_slot(
        db_session, dt.time(20, 0), dt.time(21, 30), Environment.ANY, weekdays=[0]
    )
    db_session.flush()

    weights = {material.id: MaterialWeight(material=material, remaining=100, weight=100)}
    slots_by_weekday = slot_service.group_slots_by_weekday([short_slot, long_slot])

    allocation = slot_service.allocate_day(
        weights,
        slots_by_weekday,
        dt.date(2026, 1, 5),
        _full_allocation(slots_by_weekday),
    )

    # long_slotのみ（90分ちょうど適合）
    assert slot_service.sum_minutes_by_material(allocation)[material.id] == 90


def test_allocate_day_splits_by_required_time_ratio(db_session):
    """M(s)が空でない場合、必要時間比で按分されること（9.2）。"""
    goal = _make_goal(db_session)
    material_a = _make_material(db_session, goal.id)
    material_b = _make_material(db_session, goal.id)
    slot = _make_slot(db_session, dt.time(19, 0), dt.time(22, 0), Environment.ANY, weekdays=[0])
    db_session.flush()

    # remaining/weightの比が 1:2 になるよう設定 -> 3時間のスロットが 1:2 = 1時間:2時間で按分される
    weights = {
        material_a.id: MaterialWeight(material=material_a, remaining=10, weight=10),
        material_b.id: MaterialWeight(material=material_b, remaining=20, weight=20),
    }
    slots_by_weekday = slot_service.group_slots_by_weekday([slot])

    allocation = slot_service.allocate_day(
        weights,
        slots_by_weekday,
        dt.date(2026, 1, 5),
        _full_allocation(slots_by_weekday),
    )

    totals = slot_service.sum_minutes_by_material(allocation)
    assert totals[material_a.id] == pytest.approx(60.0)
    assert totals[material_b.id] == pytest.approx(120.0)


def test_allocate_day_applies_per_slot_allocation(db_session):
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    slot = _make_slot(db_session, dt.time(19, 0), dt.time(21, 0), Environment.ANY, weekdays=[0])
    db_session.flush()

    weights = {material.id: MaterialWeight(material=material, remaining=10, weight=10)}
    slots_by_weekday = slot_service.group_slots_by_weekday([slot])

    allocation = slot_service.allocate_day(
        weights, slots_by_weekday, dt.date(2026, 1, 5), _half_allocation(slots_by_weekday)
    )

    # 120分の半分（60分）が配分されている
    assert slot_service.sum_minutes_by_material(allocation)[material.id] == 60


def test_allocate_day_skips_materials_outside_date_range(db_session):
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    material.start_date = dt.date(2026, 2, 1)  # まだ開始していない
    slot = _make_slot(db_session, dt.time(19, 0), dt.time(20, 0), Environment.ANY, weekdays=[0])
    db_session.flush()

    weights = {material.id: MaterialWeight(material=material, remaining=10, weight=10)}
    slots_by_weekday = slot_service.group_slots_by_weekday([slot])

    allocation = slot_service.allocate_day(
        weights,
        slots_by_weekday,
        dt.date(2026, 1, 5),
        _full_allocation(slots_by_weekday),
    )

    assert allocation == {}


def test_allocate_day_no_candidates_returns_empty_allocation_without_error(db_session):
    """M(s)が空の場合、そのスロットは未割当となる（例外を発生させない）。"""
    slot = _make_slot(db_session, dt.time(19, 0), dt.time(20, 0), Environment.ANY, weekdays=[0])
    db_session.flush()

    slots_by_weekday = slot_service.group_slots_by_weekday([slot])

    allocation = slot_service.allocate_day(
        {}, slots_by_weekday, dt.date(2026, 1, 5), _full_allocation(slots_by_weekday)
    )

    assert allocation == {}


def test_allocate_day_skips_when_total_weight_not_positive(db_session):
    """境界値: 候補は存在するが重みの合計が0以下の場合に例外が発生せず未割当となること。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    slot = _make_slot(db_session, dt.time(19, 0), dt.time(20, 0), Environment.ANY, weekdays=[0])
    db_session.flush()

    # remaining>0（候補には残るが）、weightを意図的に0として重み配分不能な状態を作る
    weights = {material.id: MaterialWeight(material=material, remaining=10, weight=0)}
    slots_by_weekday = slot_service.group_slots_by_weekday([slot])

    allocation = slot_service.allocate_day(
        weights,
        slots_by_weekday,
        dt.date(2026, 1, 5),
        _full_allocation(slots_by_weekday),
    )

    assert allocation == {}


def test_compute_total_minutes_for_date_sums_matching_slots(db_session):
    """日dに確保できる時間の総量 total_minutes(d)（9.1）。"""
    slot_a = _make_slot(db_session, dt.time(6, 0), dt.time(7, 0), Environment.ANY, weekdays=[0])
    slot_b = _make_slot(db_session, dt.time(20, 0), dt.time(22, 0), Environment.ANY, weekdays=[0])
    db_session.flush()

    slots_by_weekday = slot_service.group_slots_by_weekday([slot_a, slot_b])
    total_minutes = slot_service.compute_total_minutes_for_date(
        slots_by_weekday, dt.date(2026, 1, 5)
    )

    assert total_minutes == 180  # 60分 + 120分


def test_validate_slot_sufficiency_false_when_no_plan_days_in_period(db_session):
    """境界値: 教材期間内にPLAN日が1日も無い場合に例外が発生しないこと。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    material.start_date = dt.date(2026, 7, 1)
    material.due_date = dt.date(2026, 7, 3)
    for d in range(1, 4):
        db_session.add(
            CalendarDayOverride(target_date=dt.date(2026, 7, d), day_type=DayType.BUFFER)
        )
    _make_slot(
        db_session, dt.time(20, 0), dt.time(21, 0), Environment.ANY, weekdays=[0, 1, 2, 3, 4, 5, 6]
    )
    db_session.flush()

    assert not slot_service.validate_slot_sufficiency(
        db_session, material, True, _allocation_for_all_slots(db_session)
    )


def test_validate_slot_sufficiency_true_when_matching_slot_exists(db_session):
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, required_environment=Environment.PC)
    material.start_date = dt.date(2026, 3, 1)
    material.due_date = dt.date(2026, 3, 7)
    _make_slot(db_session, dt.time(20, 0), dt.time(21, 0), Environment.PC, weekdays=[0, 1, 2, 3, 4])
    for d in range(1, 8):
        db_session.add(CalendarDayOverride(target_date=dt.date(2026, 3, d), day_type=DayType.PLAN))
    db_session.flush()

    assert slot_service.validate_slot_sufficiency(
        db_session, material, True, _allocation_for_all_slots(db_session)
    )


def test_validate_slot_sufficiency_skips_non_matching_slots_before_finding_match(db_session):
    """環境不一致・曜日不一致のスロットを読み飛ばし、後続の適合スロットで真となること。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, required_environment=Environment.PC)
    # 2026-08-03(月)〜08-07(金)の5日間のみをPLANとし、土日(weekday 5,6)は計画日に含めない
    material.start_date = dt.date(2026, 8, 3)
    material.due_date = dt.date(2026, 8, 7)
    # 1件目: 環境不一致（MOBILE）-> continue
    _make_slot(
        db_session, dt.time(6, 0), dt.time(7, 0), Environment.MOBILE, weekdays=[0, 1, 2, 3, 4]
    )
    # 2件目: 環境・連続時間は適合するが、PLAN日と重ならない曜日（土日のみ）
    _make_slot(db_session, dt.time(20, 0), dt.time(21, 0), Environment.PC, weekdays=[5, 6])
    # 3件目: 環境・曜日ともに適合
    _make_slot(db_session, dt.time(21, 0), dt.time(22, 0), Environment.PC, weekdays=[0, 1, 2, 3, 4])
    for d in range(3, 8):
        db_session.add(CalendarDayOverride(target_date=dt.date(2026, 8, d), day_type=DayType.PLAN))
    db_session.flush()

    assert slot_service.validate_slot_sufficiency(
        db_session, material, True, _allocation_for_all_slots(db_session)
    )


def test_validate_slot_sufficiency_false_when_no_matching_slot(db_session):
    """適合するスロットが存在しない場合に警告が出ること（20章、falseを返すことで検証）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, required_block_minutes=180)
    material.start_date = dt.date(2026, 4, 1)
    material.due_date = dt.date(2026, 4, 7)
    _make_slot(
        db_session, dt.time(20, 0), dt.time(21, 0), Environment.ANY, weekdays=[0, 1, 2, 3, 4]
    )
    for d in range(1, 8):
        db_session.add(CalendarDayOverride(target_date=dt.date(2026, 4, d), day_type=DayType.PLAN))
    db_session.flush()

    assert not slot_service.validate_slot_sufficiency(
        db_session, material, True, _allocation_for_all_slots(db_session)
    )


def test_allocate_day_skips_slots_without_allocation(db_session):
    """配分を持たないスロットは割当対象から外れること（9.2 手順0）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    allocated = _make_slot(db_session, dt.time(6, 0), dt.time(7, 0), Environment.ANY, weekdays=[0])
    unallocated = _make_slot(
        db_session, dt.time(20, 0), dt.time(22, 0), Environment.ANY, weekdays=[0]
    )
    db_session.flush()

    weights = {material.id: MaterialWeight(material=material, remaining=100, weight=100)}
    slots_by_weekday = slot_service.group_slots_by_weekday([allocated, unallocated])

    allocation = slot_service.allocate_day(
        weights, slots_by_weekday, dt.date(2026, 1, 5), {allocated.id: 60}
    )

    assert set(allocation) == {allocated.id}
    assert slot_service.sum_minutes_by_material(allocation)[material.id] == 60


def test_allocate_day_caps_allocation_at_slot_duration(db_session):
    """配分がスロットの連続時間を超える場合（スロット短縮後）は連続時間で頭打ちになること
    （9.1 min(alloc, duration)、仕様書NT-09）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id)
    slot = _make_slot(db_session, dt.time(6, 0), dt.time(6, 30), Environment.ANY, weekdays=[0])
    db_session.flush()

    weights = {material.id: MaterialWeight(material=material, remaining=100, weight=100)}
    slots_by_weekday = slot_service.group_slots_by_weekday([slot])

    allocation = slot_service.allocate_day(
        weights, slots_by_weekday, dt.date(2026, 1, 5), {slot.id: 120}
    )

    assert slot_service.sum_minutes_by_material(allocation)[material.id] == 30


def test_block_minutes_compared_against_allocation_not_slot_duration(db_session):
    """必要連続時間はスロットの連続時間ではなく配分時間と比較すること（9.2 手順1）。

    120分のスロットでも30分しか配分していなければ、90分連続を要する教材は割り当たらない。
    """
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, required_block_minutes=90)
    slot = _make_slot(db_session, dt.time(20, 0), dt.time(22, 0), Environment.ANY, weekdays=[0])
    db_session.flush()

    weights = {material.id: MaterialWeight(material=material, remaining=100, weight=100)}
    slots_by_weekday = slot_service.group_slots_by_weekday([slot])

    assert (
        slot_service.allocate_day(weights, slots_by_weekday, dt.date(2026, 1, 5), {slot.id: 30})
        == {}
    )
    assert (
        slot_service.allocate_day(weights, slots_by_weekday, dt.date(2026, 1, 5), {slot.id: 90})
        != {}
    )


def test_validate_slot_sufficiency_false_when_slot_is_not_allocated(db_session):
    """条件を満たすスロットでも、その目標が配分を持たなければ充足しないこと（9.4）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, required_environment=Environment.PC)
    material.start_date = dt.date(2026, 3, 1)
    material.due_date = dt.date(2026, 3, 7)
    _make_slot(db_session, dt.time(20, 0), dt.time(21, 0), Environment.PC, weekdays=[0, 1, 2, 3, 4])
    for d in range(1, 8):
        db_session.add(CalendarDayOverride(target_date=dt.date(2026, 3, d), day_type=DayType.PLAN))
    db_session.flush()

    assert not slot_service.validate_slot_sufficiency(db_session, material, True, {})
