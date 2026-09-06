"""リソーススロット・曜日別既定値のCRUDと配分状況の取得（設計書データ構造編5.2・6.2、
仕様書6.3・10章、実装フェーズ分割計画書Phase3）。
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.constants.app_setting_keys import CALENDAR_DAY_BOUNDARY_HOUR, HOLIDAY_TREAT_AS_BUFFER
from app.constants.enums import DayType, Environment, GoalStatus
from app.models.goal import Goal
from app.models.resource import ResourceSlot, ResourceSlotWeekday
from app.models.setting import AppSetting, DayTypeDefault
from app.services import setting_reader, slot_service
from app.services.exceptions import AppSettingNotFoundError, NotFoundError, ValidationError

_VALID_WEEKDAYS = frozenset(range(7))
#: 曜日既定値に設定できない日種別（models/setting.py: 「OFFは既定値に設定できない」）。
_FORBIDDEN_DEFAULT_DAY_TYPE = DayType.OFF
#: 1日の境界時刻の許容範囲（仕様書10章「0時から11時の範囲とする」）。
_MIN_DAY_BOUNDARY_HOUR = 0
_MAX_DAY_BOUNDARY_HOUR = 11


def get_slot(session: Session, slot_id: int) -> ResourceSlot:
    slot = session.get(ResourceSlot, slot_id)
    if slot is None:
        raise NotFoundError("リソーススロット", slot_id)
    return slot


def list_slots(session: Session) -> list[ResourceSlot]:
    return session.query(ResourceSlot).order_by(ResourceSlot.display_order).all()


def _validate_slot_fields(
    start_time, end_time, environment: Environment, weekdays: list[int]
) -> None:
    if start_time >= end_time:
        raise ValidationError("開始時刻は終了時刻より前にしてください")
    if environment == Environment.ANY:
        raise ValidationError("環境タグは机上のみまたは移動中でも可を指定してください")
    if not weekdays:
        raise ValidationError("適用曜日を1件以上指定してください")
    if not set(weekdays) <= _VALID_WEEKDAYS:
        raise ValidationError("適用曜日は0（月）〜6（日）で指定してください")


def create_slot(
    session: Session,
    *,
    name: str,
    start_time,
    end_time,
    environment: Environment,
    weekdays: list[int],
) -> ResourceSlot:
    _validate_slot_fields(start_time, end_time, environment, weekdays)
    next_order = (
        session.query(ResourceSlot.display_order)
        .order_by(ResourceSlot.display_order.desc())
        .first()
    )
    display_order = (next_order[0] if next_order else 0) + 1
    slot = ResourceSlot(
        name=name,
        start_time=start_time,
        end_time=end_time,
        environment=environment,
        display_order=display_order,
    )
    session.add(slot)
    session.flush()
    for weekday in sorted(set(weekdays)):
        session.add(ResourceSlotWeekday(slot_id=slot.id, weekday=weekday))
    session.flush()
    return slot


def update_slot(
    session: Session,
    slot: ResourceSlot,
    *,
    name: str | None = None,
    start_time=None,
    end_time=None,
    environment: Environment | None = None,
    weekdays: list[int] | None = None,
    is_active: bool | None = None,
) -> ResourceSlot:
    resolved_start = start_time if start_time is not None else slot.start_time
    resolved_end = end_time if end_time is not None else slot.end_time
    resolved_environment = environment if environment is not None else slot.environment
    resolved_weekdays = weekdays if weekdays is not None else [w.weekday for w in slot.weekdays]
    _validate_slot_fields(resolved_start, resolved_end, resolved_environment, resolved_weekdays)

    if name is not None:
        slot.name = name
    slot.start_time = resolved_start
    slot.end_time = resolved_end
    slot.environment = resolved_environment
    if is_active is not None:
        slot.is_active = is_active
    if weekdays is not None:
        session.query(ResourceSlotWeekday).filter(ResourceSlotWeekday.slot_id == slot.id).delete()
        session.flush()
        for weekday in sorted(set(weekdays)):
            session.add(ResourceSlotWeekday(slot_id=slot.id, weekday=weekday))
    session.flush()
    return slot


def delete_slot(session: Session, slot: ResourceSlot) -> None:
    session.delete(slot)
    session.flush()


def get_day_type_defaults(session: Session) -> dict[int, DayType]:
    return {row.weekday: row.day_type for row in session.query(DayTypeDefault).all()}


def update_day_type_defaults(session: Session, values: dict[int, DayType]) -> dict[int, DayType]:
    """曜日別の日種別既定値を一括更新する（仕様書6.3「曜日別の既定設定」）。OFFは指定不可。"""
    for weekday, day_type in values.items():
        if weekday not in _VALID_WEEKDAYS:
            raise ValidationError("曜日は0（月）〜6（日）で指定してください")
        if day_type == _FORBIDDEN_DEFAULT_DAY_TYPE:
            raise ValidationError("曜日別既定値にOFF（除外日）は設定できません")

    for weekday, day_type in values.items():
        row = session.get(DayTypeDefault, weekday)
        if row is None:
            session.add(DayTypeDefault(weekday=weekday, day_type=day_type))
        else:
            row.day_type = day_type
    session.flush()
    return get_day_type_defaults(session)


def get_day_boundary_hour(session: Session) -> int:
    """1日の境界時刻を取得する（仕様書6.3「日付が切り替わる時刻」）。"""
    return setting_reader.get_int(session, CALENDAR_DAY_BOUNDARY_HOUR)


def update_day_boundary_hour(session: Session, hour: int) -> int:
    """1日の境界時刻を更新する（仕様書10章「0時から11時の範囲とする」）。

    calendar_service.resolve_logical_today（Phase2）が読む app_setting を更新するだけであり、
    論理日の算出ロジック自体はここでは変更しない。
    """
    if not (_MIN_DAY_BOUNDARY_HOUR <= hour <= _MAX_DAY_BOUNDARY_HOUR):
        raise ValidationError("1日の境界時刻は0〜11時で指定してください")
    row = session.get(AppSetting, CALENDAR_DAY_BOUNDARY_HOUR)
    if row is None:
        raise AppSettingNotFoundError(CALENDAR_DAY_BOUNDARY_HOUR)
    row.value = str(hour)
    session.flush()
    return hour


def get_holiday_treat_as_buffer(session: Session) -> bool:
    """祝日を一律でバッファ日として扱うかを取得する（仕様書6.3「日種別の既定設定」）。"""
    return setting_reader.get_bool(session, HOLIDAY_TREAT_AS_BUFFER)


def update_holiday_treat_as_buffer(session: Session, treat_as_buffer: bool) -> bool:
    row = session.get(AppSetting, HOLIDAY_TREAT_AS_BUFFER)
    if row is None:
        raise AppSettingNotFoundError(HOLIDAY_TREAT_AS_BUFFER)
    row.value = "true" if treat_as_buffer else "false"
    session.flush()
    return treat_as_buffer


@dataclass(frozen=True)
class GoalAllocation:
    """目標ごとの配分状況（仕様書6.3「各目標への配分状況と未配分の残量」）。"""

    goal_id: int
    goal_name: str
    resource_ratio: float


@dataclass(frozen=True)
class AllocationStatus:
    """リソース配分状況（データ構造編6.2 GET /resources/allocation）。"""

    total_hours_by_weekday: dict[int, float]
    total_hours_by_environment: dict[str, float]
    goal_allocations: list[GoalAllocation] = field(default_factory=list)
    unallocated_ratio: float = 1.0


def get_allocation_status(session: Session) -> AllocationStatus:
    slots = slot_service.get_active_slots(session)
    slots_by_weekday = slot_service.group_slots_by_weekday(slots)

    total_hours_by_weekday = {
        weekday: sum(slot_service.slot_duration_hours(s) for s in slots_by_weekday.get(weekday, []))
        for weekday in range(7)
    }

    total_hours_by_environment: dict[str, float] = {}
    for slot in slots:
        weekly_hours = slot_service.slot_duration_hours(slot) * len(slot.weekdays)
        key = slot.environment.value
        total_hours_by_environment[key] = total_hours_by_environment.get(key, 0.0) + weekly_hours

    active_goals = (
        session.query(Goal).filter(Goal.status == GoalStatus.ACTIVE).order_by(Goal.id).all()
    )
    goal_allocations = [
        GoalAllocation(goal_id=g.id, goal_name=g.name, resource_ratio=g.resource_ratio)
        for g in active_goals
    ]
    unallocated_ratio = max(0.0, 1.0 - sum(g.resource_ratio for g in active_goals))

    return AllocationStatus(
        total_hours_by_weekday=total_hours_by_weekday,
        total_hours_by_environment=total_hours_by_environment,
        goal_allocations=goal_allocations,
        unallocated_ratio=unallocated_ratio,
    )
