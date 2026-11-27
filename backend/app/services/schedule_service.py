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
import enum
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.constants.app_setting_keys import (
    SCHEDULE_CELL_VALUE_MAX_CHARS,
    SCHEDULE_COLUMN_NAME_MAX_CHARS,
    SCHEDULE_ITEM_DESCRIPTION_MAX_CHARS,
    SCHEDULE_ITEM_TITLE_MAX_CHARS,
    SCHEDULE_MAX_CUSTOM_COLUMNS,
    SCHEDULE_MAX_ITEMS,
)
from app.constants.enums import GoalCategory, GoalStatus, ScheduleItemStatus, ScheduleUpdateSource
from app.constants.goal_transitions import GoalOperation
from app.models.base import utcnow
from app.models.goal import Goal
from app.models.schedule import (
    GoalSchedule,
    ScheduleCell,
    ScheduleColumn,
    ScheduleItem,
    ScheduleItemHistory,
)
from app.schemas.schedule import (
    ScheduleColumnInput,
    ScheduleItemInput,
    ScheduleItemUpdateInput,
    ScheduleSaveRequest,
)
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


class ScheduleDelayKind(enum.StrEnum):
    """遅れの種類（本書13.2、単位5）。DB・APIには永続化しない内部専用の値。

    ガントの遅れの印（D-18）と、13.2のAI呼び出しの契機判定（遅れのある目標だけを対象とする）
    の両方がこの関数の結果を共有する（CLAUDE.md DRYの原則、単位3引き継ぎ事項）。
    """

    #: 状況が未着手または進行中で、本日が予定終了日を過ぎている（13.2「終了の遅れ」）。
    END_DELAY = "END_DELAY"
    #: 状況が未着手で、本日が予定開始日を過ぎている（13.2「開始の遅れ」）。
    #: 終了の遅れの条件も満たす場合はEND_DELAYを優先する（予定終了日を過ぎていれば予定開始日も
    #: 必ず過ぎているため、END_DELAYの方が実情を表す、本書14章補足4）。
    START_DELAY = "START_DELAY"


def compute_delay_kind(item: ScheduleItem, today: dt.date) -> ScheduleDelayKind | None:
    """1行分の遅れの種類を判定する（本書13.2、終了した行〈DONE・CANCELLED〉は対象外）。"""
    if item.status not in (ScheduleItemStatus.NOT_STARTED, ScheduleItemStatus.IN_PROGRESS):
        return None
    if today > item.planned_end_date:
        return ScheduleDelayKind.END_DELAY
    if item.status == ScheduleItemStatus.NOT_STARTED and today > item.planned_start_date:
        return ScheduleDelayKind.START_DELAY
    return None


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


def _check_owned_by_goal(
    entity_id: int | None, existing: dict[int, object], entity_label: str
) -> None:
    """送信されたIDが対象の目標に属することを確認する（8.1「所有者の検証」）。

    他の目標に属する場合と、存在しないIDの場合を区別しない（他の目標が存在することの
    手掛かりを与えない。material_service._resolve_subjectsの考え方と同じ）。
    """
    if entity_id is not None and entity_id not in existing:
        raise ValidationError(
            f"Cannot update {entity_label}(id={entity_id}) that belongs to a different goal"
        )


def _validate_columns(
    session: Session,
    columns: list[ScheduleColumnInput],
    existing_columns: dict[int, ScheduleColumn],
) -> None:
    name_max_chars = setting_reader.get_int(session, SCHEDULE_COLUMN_NAME_MAX_CHARS)
    seen_names: set[str] = set()
    seen_temp_keys: set[str] = set()
    for column_input in columns:
        name = column_input.name
        if not name.strip():
            raise ValidationError("Column name must not be blank")
        if len(name) > name_max_chars:
            raise ValidationError(f"Column name must be {name_max_chars} characters or fewer")
        # 利用者が入力した列名自体はメッセージへ埋め込まない（ログ・応答への混入を防ぐ、
        # app/api/errors.pyの「メッセージは自由入力文字列を含まない」という前提を保つ）。
        if name in seen_names:
            raise ValidationError("Duplicate column name in request")
        seen_names.add(name)

        _check_owned_by_goal(column_input.id, existing_columns, "schedule column")
        if column_input.temp_key is not None:
            if column_input.temp_key in seen_temp_keys:
                raise ValidationError("Duplicate temp_key in request")
            seen_temp_keys.add(column_input.temp_key)


def _validate_items(
    session: Session,
    items: list[ScheduleItemInput],
    existing_items: dict[int, ScheduleItem],
    today: dt.date,
) -> None:
    title_max_chars = setting_reader.get_int(session, SCHEDULE_ITEM_TITLE_MAX_CHARS)
    description_max_chars = setting_reader.get_int(session, SCHEDULE_ITEM_DESCRIPTION_MAX_CHARS)
    seen_ids: set[int] = set()
    for item_input in items:
        _check_owned_by_goal(item_input.id, existing_items, "schedule item")
        if item_input.id is not None:
            if item_input.id in seen_ids:
                raise ValidationError("Duplicate item id in request")
            seen_ids.add(item_input.id)
        if len(item_input.title) > title_max_chars:
            raise ValidationError(f"title must be {title_max_chars} characters or fewer")
        if (
            item_input.description is not None
            and len(item_input.description) > description_max_chars
        ):
            raise ValidationError(
                f"description must be {description_max_chars} characters or fewer"
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


def _validate_cells(
    session: Session, items: list[ScheduleItemInput], columns: list[ScheduleColumnInput]
) -> None:
    value_max_chars = setting_reader.get_int(session, SCHEDULE_CELL_VALUE_MAX_CHARS)
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
            if len(cell_input.value) > value_max_chars:
                raise ValidationError(f"Cell value must be {value_max_chars} characters or fewer")


def _delete_not_resubmitted(
    session: Session, existing: dict[int, object], submitted_ids: set[int]
) -> None:
    """送られてこなかった既存の行・列を削除する（8.1の差分ルール、DRYの原則）。"""
    for entity_id, entity in existing.items():
        if entity_id not in submitted_ids:
            session.delete(entity)


def _apply_columns(
    session: Session,
    goal: Goal,
    columns: list[ScheduleColumnInput],
    existing_columns: dict[int, ScheduleColumn],
) -> dict[_ColumnKey, ScheduleColumn]:
    _delete_not_resubmitted(session, existing_columns, {c.id for c in columns if c.id is not None})

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
    _delete_not_resubmitted(session, existing_items, {i.id for i in items if i.id is not None})

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
    _validate_columns(session, payload.columns, existing_columns)
    _validate_items(session, payload.items, existing_items, today)
    _validate_cells(session, payload.items, payload.columns)

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


@dataclass(frozen=True)
class ScheduleItemForReport:
    """`GET /records/{target_date}/schedule-items`の1行分（本書4章・D-32・D-33、単位4）。"""

    id: int
    title: str
    planned_start_date: dt.date
    planned_end_date: dt.date
    status: ScheduleItemStatus
    actual_start_date: dt.date | None
    actual_end_date: dt.date | None
    default_visible: bool


@dataclass(frozen=True)
class GoalScheduleItemsForReport:
    """`GET /records/{target_date}/schedule-items`の1目標分（本書4章、単位4）。"""

    goal_id: int
    goal_name: str
    goal_category: GoalCategory
    items: list[ScheduleItemForReport]


def _is_default_visible_for_report(item: ScheduleItem, target_date: dt.date) -> bool:
    """D-33の3条件（報告対象日が予定期間内／進行中／予定終了日を過ぎた未完了）のいずれかに
    該当するかを返す。該当しない行は「すべて表示」でのみ表示する。"""
    if item.planned_start_date <= target_date <= item.planned_end_date:
        return True
    if item.status == ScheduleItemStatus.IN_PROGRESS:
        return True
    if item.status == ScheduleItemStatus.NOT_STARTED and target_date > item.planned_end_date:
        return True
    return False


def list_schedule_items_for_report(
    session: Session, target_date: dt.date
) -> list[GoalScheduleItemsForReport]:
    """`GET /records/{target_date}/schedule-items`（本書4章、単位4）。

    対象はACTIVEな目標のみ（既存のノルマ・日記・読書書籍・業務案件と同じ絞り込み、
    単位4開発Todo2章補足1）。完了・中止の行はそもそも応答に含めない（12章補足7、
    「すべて表示」でも表示されないため）。作業項目が1件も対象にならない目標は
    応答に含めない（D-38）。
    """
    goals = list(session.execute(select(Goal).where(Goal.status == GoalStatus.ACTIVE)).scalars())
    if not goals:
        return []

    items = session.execute(
        select(ScheduleItem)
        .where(
            ScheduleItem.goal_id.in_([goal.id for goal in goals]),
            ScheduleItem.status.not_in([ScheduleItemStatus.DONE, ScheduleItemStatus.CANCELLED]),
        )
        .order_by(ScheduleItem.goal_id, ScheduleItem.display_order)
    ).scalars()

    items_by_goal: dict[int, list[ScheduleItemForReport]] = defaultdict(list)
    for item in items:
        items_by_goal[item.goal_id].append(
            ScheduleItemForReport(
                id=item.id,
                title=item.title,
                planned_start_date=item.planned_start_date,
                planned_end_date=item.planned_end_date,
                status=item.status,
                actual_start_date=item.actual_start_date,
                actual_end_date=item.actual_end_date,
                default_visible=_is_default_visible_for_report(item, target_date),
            )
        )

    return [
        GoalScheduleItemsForReport(
            goal_id=goal.id,
            goal_name=goal.name,
            goal_category=goal.category,
            items=items_by_goal[goal.id],
        )
        for goal in goals
        if goal.id in items_by_goal
    ]


def list_schedule_items_updated_on(
    session: Session, target_date: dt.date
) -> list[GoalScheduleItemsForReport]:
    """`GET /records/{target_date}/schedule-items-history`（本書4章「確定済みの種別：
    入力欄を出さず、その日に更新した内容を読み取り専用で表示する」、軽微な修正3
    開発Todo_スケジュール・ガントチャート_検証修正_v1.0.md）。

    `apply_report_schedule_item_updates`が値の変化があった場合だけ書く
    `schedule_item_history`（record_date=報告対象日）から、その日に実際に更新された行を
    返す。`list_schedule_items_for_report`（ライブの現在値、ACTIVEな目標のみ、完了・中止は
    除外）とは異なり、完了・中止になった行や、現在はACTIVEでない目標の行も含める
    （過去に確定した内容をそのまま示すため）。同じ行が同日に複数回更新された場合は、
    最後に記録された値のみを使う。表示・絞り込みの区別が無いため`default_visible`は常に
    `True`とする（呼び出し元はこの値でフィルタしない）。
    """
    history_rows = list(
        session.execute(
            select(ScheduleItemHistory).where(ScheduleItemHistory.record_date == target_date)
        ).scalars()
    )
    if not history_rows:
        return []

    latest_by_item_id: dict[int, ScheduleItemHistory] = {}
    for row in history_rows:
        current = latest_by_item_id.get(row.schedule_item_id)
        if current is None or (row.changed_at, row.id) > (current.changed_at, current.id):
            latest_by_item_id[row.schedule_item_id] = row

    items = {
        item.id: item
        for item in session.execute(
            select(ScheduleItem)
            .options(joinedload(ScheduleItem.goal))
            .where(ScheduleItem.id.in_(latest_by_item_id.keys()))
        ).scalars()
    }

    goal_by_id: dict[int, Goal] = {}
    ordered_items_by_goal: dict[int, list[tuple[int, ScheduleItemForReport]]] = defaultdict(list)
    for schedule_item_id, history in latest_by_item_id.items():
        item = items.get(schedule_item_id)
        if item is None:  # pragma: no cover - ON DELETE CASCADEで通常到達しない
            continue
        goal_by_id[item.goal_id] = item.goal
        ordered_items_by_goal[item.goal_id].append(
            (
                item.display_order,
                ScheduleItemForReport(
                    id=item.id,
                    title=item.title,
                    planned_start_date=item.planned_start_date,
                    planned_end_date=item.planned_end_date,
                    status=history.status,
                    actual_start_date=history.actual_start_date,
                    actual_end_date=history.actual_end_date,
                    default_visible=True,
                ),
            )
        )

    return [
        GoalScheduleItemsForReport(
            goal_id=goal.id,
            goal_name=goal.name,
            goal_category=goal.category,
            items=[entry for _order, entry in sorted(ordered_items_by_goal[goal.id])],
        )
        for goal in sorted(goal_by_id.values(), key=lambda g: g.id)
    ]


def apply_report_schedule_item_updates(
    session: Session,
    updates: list[ScheduleItemUpdateInput],
    *,
    category: GoalCategory | None,
    target_date: dt.date,
    today: dt.date,
    source: ScheduleUpdateSource,
) -> None:
    """日次報告・進捗のみ登録からの作業項目の更新（本書4章・第8章、単位4）。

    実績と同じトランザクションで適用する（呼び出し側が本関数の後にcommitする）。
    `save_schedule`と同じ「検証を適用より先にすべて終える」方針（8.1）とし、1件でも
    不正な更新があれば何も適用せずに例外を投げる（呼び出し元のcommit前のため、実績の
    保存もまとめてロールバックされる）。`category`を指定した場合（確定API3本）は、
    その種別の目標に属する行だけを受け付ける（D-35）。Noneの場合（progress API）は
    ACTIVEな目標であれば種別を問わない（D-36）。行の所有者検証は単位2の
    `_check_owned_by_goal`と同じく、存在しないIDと他の目標に属するIDを区別しない。
    """
    if not updates:
        return

    ids = [update.schedule_item_id for update in updates]
    if len(set(ids)) != len(ids):
        raise ValidationError("Duplicate schedule item id in request")

    items = {
        item.id: item
        for item in session.execute(
            select(ScheduleItem)
            .options(joinedload(ScheduleItem.goal))
            .where(ScheduleItem.id.in_(ids))
        ).scalars()
    }

    for update in updates:
        item = items.get(update.schedule_item_id)
        if item is None or (category is not None and item.goal.category != category):
            raise ValidationError(
                f"Cannot update schedule item(id={update.schedule_item_id}) "
                "that belongs to a different goal"
            )
        goal_service.ensure_operation_allowed(item.goal, GoalOperation.RECORD)
        validate_item_fields(
            title=item.title,
            planned_start_date=item.planned_start_date,
            planned_end_date=item.planned_end_date,
            status=update.status,
            actual_start_date=update.actual_start_date,
            actual_end_date=update.actual_end_date,
            today=today,
        )

    now = utcnow()
    touched_goal_ids: set[int] = set()
    for update in updates:
        item = items[update.schedule_item_id]
        previous = (item.status, item.actual_start_date, item.actual_end_date)
        item.status = update.status
        item.actual_start_date = update.actual_start_date
        item.actual_end_date = update.actual_end_date
        if previous != (item.status, item.actual_start_date, item.actual_end_date):
            session.add(
                ScheduleItemHistory(
                    schedule_item_id=item.id,
                    source=source,
                    record_date=target_date,
                    status=item.status,
                    actual_start_date=item.actual_start_date,
                    actual_end_date=item.actual_end_date,
                    changed_at=now,
                )
            )
            touched_goal_ids.add(item.goal_id)

    session.flush()
    _bump_schedule_revisions(session, touched_goal_ids)


def bump_schedule_revision(session: Session, goal_id: int) -> None:
    """目標1件分のrevisionを1増やす（公開版、単位5の判断API〈承認でrevisionが変わる、13.7〉
    から呼ぶ。実装は`_bump_schedule_revisions`に集約する、CLAUDE.md DRYの原則）。
    """
    _bump_schedule_revisions(session, {goal_id})


def _bump_schedule_revisions(session: Session, goal_ids: set[int]) -> None:
    """対象の目標ごとにrevisionを1増やす（7.1「更新元を問わない」、単位4開発Todo2章補足3）。
    `GoalSchedule`が存在しない目標はrevision=1で新規作成する（`save_schedule`の初期化と同じ）。
    """
    if not goal_ids:
        return
    schedules = {
        schedule.goal_id: schedule
        for schedule in session.execute(
            select(GoalSchedule).where(GoalSchedule.goal_id.in_(goal_ids))
        ).scalars()
    }
    for goal_id in goal_ids:
        schedule = schedules.get(goal_id)
        if schedule is None:
            session.add(GoalSchedule(goal_id=goal_id, revision=1))
        else:
            schedule.revision += 1
    session.flush()
