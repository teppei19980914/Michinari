"""スケジュール・ガントチャート機能のサービス層
（開発Todo_スケジュール・ガントチャート_v1.1 第6章・第7章・第8章、単位2）。

検証はここに集約する（6.1「検証はサービス層の1か所に集約」、CODING_RULES.md DRYの原則）。
`validate_item_fields`は1行分の状況・実績日の検証だけを行う小さな関数とし、単位4
（日次報告・SC-07からの`schedule_item_updates`）からも共通で呼べるようにする。
一方、`save_schedule`（列・行・セルの差分適用、revisionの楽観ロック）は本単位の
一括保存専用の処理であり、単位4は再利用しない（日次報告は行の追加・削除を行わない）。
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants.app_setting_keys import SCHEDULE_MAX_CUSTOM_COLUMNS, SCHEDULE_MAX_ITEMS
from app.constants.enums import ScheduleItemStatus, ScheduleUpdateSource
from app.models.base import utcnow
from app.models.goal import Goal
from app.models.schedule import (
    GoalSchedule,
    ScheduleCell,
    ScheduleColumn,
    ScheduleItem,
    ScheduleItemHistory,
)
from app.schemas.schedule import ScheduleColumnInput, ScheduleItemInput, ScheduleSaveRequest
from app.services import goal_service, setting_reader
from app.services.exceptions import ScheduleRevisionConflictError, ValidationError

#: 行が存在しない目標の既定値（本書7.1）。
_DEFAULT_FROZEN_COLUMN_COUNT = 1
_DEFAULT_FROZEN_ROW_COUNT = 0
_DEFAULT_REVISION = 0

#: 既定7列（D-08）の個数。固定する列数の有効範囲の算出に使う。
_DEFAULT_COLUMN_COUNT = 7

#: 列・セルの参照キー（既存列はid、新規列はtemp_keyで対応付ける、本書8.1）。
_ColumnKey = tuple[str, int] | tuple[str, str]


@dataclass(frozen=True)
class ScheduleView:
    """GET /goals/{goal_id}/schedule の組み立てに使う1目標分のデータ（本書8章）。"""

    revision: int
    frozen_row_count: int
    frozen_column_count: int
    columns: list[ScheduleColumn]
    items: list[ScheduleItem]
    cells_by_item_id: dict[int, dict[int, str]]


def _get_goal_schedule(session: Session, goal_id: int) -> GoalSchedule | None:
    return session.execute(
        select(GoalSchedule).where(GoalSchedule.goal_id == goal_id)
    ).scalar_one_or_none()


def _column_key(column_id: int | None, temp_key: str | None) -> _ColumnKey:
    if column_id is not None:
        return ("id", column_id)
    assert temp_key is not None  # ScheduleColumnInput/ScheduleCellInputのmodel_validatorが保証
    return ("temp", temp_key)


def get_schedule_view(session: Session, goal: Goal) -> ScheduleView:
    """GET /goals/{goal_id}/schedule の組み立て用データを返す（本書8章）。"""
    schedule = _get_goal_schedule(session, goal.id)
    columns = list(
        session.execute(
            select(ScheduleColumn)
            .where(ScheduleColumn.goal_id == goal.id)
            .order_by(ScheduleColumn.display_order)
        ).scalars()
    )
    items = list(
        session.execute(
            select(ScheduleItem)
            .where(ScheduleItem.goal_id == goal.id)
            .order_by(ScheduleItem.display_order)
        ).scalars()
    )
    cells_by_item_id: dict[int, dict[int, str]] = {item.id: {} for item in items}
    if items:
        cells = session.execute(
            select(ScheduleCell).where(
                ScheduleCell.schedule_item_id.in_([item.id for item in items])
            )
        ).scalars()
        for cell in cells:
            cells_by_item_id[cell.schedule_item_id][cell.schedule_column_id] = cell.value

    return ScheduleView(
        revision=schedule.revision if schedule else _DEFAULT_REVISION,
        frozen_row_count=schedule.frozen_row_count if schedule else _DEFAULT_FROZEN_ROW_COUNT,
        frozen_column_count=(
            schedule.frozen_column_count if schedule else _DEFAULT_FROZEN_COLUMN_COUNT
        ),
        columns=columns,
        items=items,
        cells_by_item_id=cells_by_item_id,
    )


def validate_item_fields(
    *,
    title: str,
    planned_start_date: dt.date,
    planned_end_date: dt.date,
    status: ScheduleItemStatus,
    actual_start_date: dt.date | None,
    actual_end_date: dt.date | None,
    today: dt.date,
) -> None:
    """作業項目1行分の検証（本書6.2）。スケジュール画面の一括保存（`save_schedule`）と、
    単位4で追加する日次報告・SC-07からの状況・実績日の更新で共通に使う（6.1）。
    """
    if not title.strip():
        raise ValidationError("Title must not be blank")
    if planned_start_date > planned_end_date:
        raise ValidationError("planned_start_date must not be after planned_end_date")

    if status == ScheduleItemStatus.NOT_STARTED:
        if actual_start_date is not None or actual_end_date is not None:
            raise ValidationError("NOT_STARTED items cannot have actual dates")
    elif status == ScheduleItemStatus.IN_PROGRESS:
        if actual_start_date is None:
            raise ValidationError("IN_PROGRESS items require actual_start_date")
        if actual_end_date is not None:
            raise ValidationError("IN_PROGRESS items cannot have actual_end_date")
    elif status == ScheduleItemStatus.DONE:
        if actual_start_date is None or actual_end_date is None:
            raise ValidationError("DONE items require both actual_start_date and actual_end_date")
    elif status == ScheduleItemStatus.CANCELLED and (
        actual_start_date is None and actual_end_date is not None
    ):
        raise ValidationError("CANCELLED items cannot have only actual_end_date")

    if (
        actual_start_date is not None
        and actual_end_date is not None
        and actual_start_date > actual_end_date
    ):
        raise ValidationError("actual_start_date must not be after actual_end_date")
    if actual_start_date is not None and actual_start_date > today:
        raise ValidationError("actual_start_date must not be in the future")
    if actual_end_date is not None and actual_end_date > today:
        raise ValidationError("actual_end_date must not be in the future")


def _validate_columns(
    columns: list[ScheduleColumnInput], existing_columns: dict[int, ScheduleColumn]
) -> None:
    seen_names: set[str] = set()
    seen_temp_keys: set[str] = set()
    for column_input in columns:
        name = column_input.name
        if not name.strip():
            raise ValidationError("Column name must not be blank")
        if name in seen_names:
            raise ValidationError(f'Duplicate column name "{name}"')
        seen_names.add(name)

        if column_input.id is not None and column_input.id not in existing_columns:
            # 他の目標に属する場合と、存在しないIDの場合を区別しない（他の目標が存在する
            # ことの手掛かりを与えない。material_service._resolve_subjectsの考え方と同じ）。
            raise ValidationError(
                f"Cannot update schedule column(id={column_input.id}) "
                "that belongs to a different goal"
            )
        if column_input.temp_key is not None:
            if column_input.temp_key in seen_temp_keys:
                raise ValidationError(f'Duplicate temp_key "{column_input.temp_key}"')
            seen_temp_keys.add(column_input.temp_key)


def _validate_items(
    items: list[ScheduleItemInput], existing_items: dict[int, ScheduleItem], today: dt.date
) -> None:
    for item_input in items:
        if item_input.id is not None and item_input.id not in existing_items:
            raise ValidationError(
                f"Cannot update schedule item(id={item_input.id}) that belongs to a different goal"
            )
        validate_item_fields(
            title=item_input.title,
            planned_start_date=item_input.planned_start_date,
            planned_end_date=item_input.planned_end_date,
            status=item_input.status,
            actual_start_date=item_input.actual_start_date,
            actual_end_date=item_input.actual_end_date,
            today=today,
        )


def _validate_cells(items: list[ScheduleItemInput], columns: list[ScheduleColumnInput]) -> None:
    valid_keys = {_column_key(c.id, c.temp_key) for c in columns}
    for item_input in items:
        seen_keys: set[_ColumnKey] = set()
        for cell_input in item_input.cells:
            key = _column_key(cell_input.column_id, cell_input.column_temp_key)
            if key not in valid_keys:
                raise ValidationError(
                    "Cell references a column that is not included in this request"
                )
            if key in seen_keys:
                raise ValidationError("Duplicate cell for the same column in one item")
            seen_keys.add(key)


def _apply_columns(
    session: Session,
    goal: Goal,
    columns: list[ScheduleColumnInput],
    existing_columns: dict[int, ScheduleColumn],
) -> dict[_ColumnKey, ScheduleColumn]:
    submitted_ids = {c.id for c in columns if c.id is not None}
    for column_id, column in existing_columns.items():
        if column_id not in submitted_ids:
            session.delete(column)

    resolved: dict[_ColumnKey, ScheduleColumn] = {}
    for index, column_input in enumerate(columns):
        if column_input.id is not None:
            column = existing_columns[column_input.id]
            column.name = column_input.name
            column.display_order = index
        else:
            column = ScheduleColumn(goal_id=goal.id, name=column_input.name, display_order=index)
            session.add(column)
        resolved[_column_key(column_input.id, column_input.temp_key)] = column

    session.flush()  # 新規列にIDを振る（セルのFK解決に使う）。
    return resolved


def _apply_items(
    session: Session,
    goal: Goal,
    items: list[ScheduleItemInput],
    existing_items: dict[int, ScheduleItem],
) -> list[tuple[ScheduleItem, ScheduleItemInput]]:
    submitted_ids = {i.id for i in items if i.id is not None}
    for item_id, item in existing_items.items():
        if item_id not in submitted_ids:
            session.delete(item)

    pairs: list[tuple[ScheduleItem, ScheduleItemInput, bool, tuple | None]] = []
    for index, item_input in enumerate(items):
        if item_input.id is not None:
            item = existing_items[item_input.id]
            previous = (item.status, item.actual_start_date, item.actual_end_date)
            is_new = False
        else:
            item = ScheduleItem(goal_id=goal.id)
            session.add(item)
            previous = None
            is_new = True

        item.title = item_input.title
        item.description = item_input.description
        item.planned_start_date = item_input.planned_start_date
        item.planned_end_date = item_input.planned_end_date
        item.status = item_input.status
        item.actual_start_date = item_input.actual_start_date
        item.actual_end_date = item_input.actual_end_date
        item.display_order = index
        pairs.append((item, item_input, is_new, previous))

    session.flush()  # 新規行にIDを振る（historyとセルのFKに使う）。

    now = utcnow()
    for item, _item_input, is_new, previous in pairs:
        current = (item.status, item.actual_start_date, item.actual_end_date)
        if is_new or previous != current:
            session.add(
                ScheduleItemHistory(
                    schedule_item_id=item.id,
                    source=ScheduleUpdateSource.SCHEDULE_SCREEN,
                    record_date=None,
                    status=item.status,
                    actual_start_date=item.actual_start_date,
                    actual_end_date=item.actual_end_date,
                    changed_at=now,
                )
            )
    return [(item, item_input) for item, item_input, _is_new, _previous in pairs]


def _apply_cells(
    session: Session,
    items: list[tuple[ScheduleItem, ScheduleItemInput]],
    columns: list[ScheduleColumnInput],
    resolved_columns: dict[_ColumnKey, ScheduleColumn],
) -> None:
    item_ids = [item.id for item, _ in items]
    existing_cells_by_item: dict[int, dict[int, ScheduleCell]] = defaultdict(dict)
    if item_ids:
        for cell in session.execute(
            select(ScheduleCell).where(ScheduleCell.schedule_item_id.in_(item_ids))
        ).scalars():
            existing_cells_by_item[cell.schedule_item_id][cell.schedule_column_id] = cell

    for item, item_input in items:
        values_by_key = {
            _column_key(cell.column_id, cell.column_temp_key): cell.value
            for cell in item_input.cells
        }
        existing_cells = existing_cells_by_item.get(item.id, {})
        for column_input in columns:
            key = _column_key(column_input.id, column_input.temp_key)
            column = resolved_columns[key]
            value = values_by_key.get(key, "")
            existing_cell = existing_cells.get(column.id)
            if not value.strip():
                if existing_cell is not None:
                    session.delete(existing_cell)
                continue
            if existing_cell is not None:
                existing_cell.value = value
            else:
                session.add(
                    ScheduleCell(
                        schedule_item_id=item.id, schedule_column_id=column.id, value=value
                    )
                )


def save_schedule(
    session: Session, goal: Goal, payload: ScheduleSaveRequest, today: dt.date
) -> ScheduleView:
    """PUT /goals/{goal_id}/schedule（本書8.1）。

    revision不一致は409（`ScheduleRevisionConflictError`）、所有者検証・上限・フィールド
    検証のいずれかに反する場合は400（`ValidationError`）とし、いずれも1件も変更を
    加えずに拒否する（検証を適用より先にすべて終える）。
    """
    goal_service.ensure_goal_editable(goal)

    schedule = _get_goal_schedule(session, goal.id)
    current_revision = schedule.revision if schedule else _DEFAULT_REVISION
    if payload.revision != current_revision:
        raise ScheduleRevisionConflictError(goal.id, payload.revision, current_revision)

    max_columns = setting_reader.get_int(session, SCHEDULE_MAX_CUSTOM_COLUMNS)
    max_items = setting_reader.get_int(session, SCHEDULE_MAX_ITEMS)
    if len(payload.columns) > max_columns:
        raise ValidationError(f"Too many custom columns (max {max_columns})")
    if len(payload.items) > max_items:
        raise ValidationError(f"Too many items (max {max_items})")

    existing_columns = {
        column.id: column
        for column in session.execute(
            select(ScheduleColumn).where(ScheduleColumn.goal_id == goal.id)
        ).scalars()
    }
    existing_items = {
        item.id: item
        for item in session.execute(
            select(ScheduleItem).where(ScheduleItem.goal_id == goal.id)
        ).scalars()
    }

    # --- 検証（適用前にすべて終える） ---
    _validate_columns(payload.columns, existing_columns)
    _validate_items(payload.items, existing_items, today)
    _validate_cells(payload.items, payload.columns)

    # --- 適用 ---
    resolved_columns = _apply_columns(session, goal, payload.columns, existing_columns)
    resolved_items = _apply_items(session, goal, payload.items, existing_items)
    _apply_cells(session, resolved_items, payload.columns, resolved_columns)

    if schedule is None:
        schedule = GoalSchedule(goal_id=goal.id, revision=1)
        session.add(schedule)
    else:
        schedule.revision += 1

    session.flush()
    return get_schedule_view(session, goal)


def update_view_setting(
    session: Session, goal: Goal, frozen_row_count: int, frozen_column_count: int
) -> GoalSchedule:
    """PUT /goals/{goal_id}/schedule/view-setting（本書8章、D-24・D-25）。revisionは変えない。

    有効範囲（0〜現在の行数／0〜既定7列+現在の追加列数）を超える値は、範囲内へ収める
    （固定行数・列数は表示上の設定であり、範囲外の値を保存しても実害は無いが、現在の
    実データに収まらない値を残さないため。仕様に影響しない実装詳細、本書15.1手順5）。
    """
    goal_service.ensure_goal_editable(goal)
    schedule = _get_goal_schedule(session, goal.id)

    item_count = session.scalar(
        select(func.count()).select_from(ScheduleItem).where(ScheduleItem.goal_id == goal.id)
    )
    column_count = session.scalar(
        select(func.count()).select_from(ScheduleColumn).where(ScheduleColumn.goal_id == goal.id)
    )
    clamped_row_count = max(0, min(frozen_row_count, item_count))
    clamped_column_count = max(0, min(frozen_column_count, _DEFAULT_COLUMN_COUNT + column_count))

    if schedule is None:
        schedule = GoalSchedule(
            goal_id=goal.id,
            revision=_DEFAULT_REVISION,
            frozen_row_count=clamped_row_count,
            frozen_column_count=clamped_column_count,
        )
        session.add(schedule)
    else:
        schedule.frozen_row_count = clamped_row_count
        schedule.frozen_column_count = clamped_column_count

    session.flush()
    return schedule
