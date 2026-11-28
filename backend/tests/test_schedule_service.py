"""schedule_service のテスト（開発Todo_スケジュール・ガントチャート_v1.1 第6章・第7章・
第8章、単位2）。

検証ルールの全分岐（6.2）・差分更新（行IDを維持すること、8.1）・revisionの楽観ロック
（D-07）・認可境界（他目標の行・列ID、8.1）・固定設定のクランプを検証する。
API層を経由した結合テスト（SQLi/XSSペイロードの往復・404/409等）はtest_api_schedule.py、
Alembicマイグレーションのupgrade/downgradeはtest_migration_data.pyを参照。
"""

import datetime as dt

import pytest

from app.constants.app_setting_keys import (
    SCHEDULE_CELL_VALUE_MAX_CHARS,
    SCHEDULE_COLUMN_NAME_MAX_CHARS,
    SCHEDULE_ITEM_DESCRIPTION_MAX_CHARS,
    SCHEDULE_ITEM_TITLE_MAX_CHARS,
    SCHEDULE_MAX_CUSTOM_COLUMNS,
    SCHEDULE_MAX_ITEMS,
)
from app.constants.enums import GoalCategory, GoalStatus, ScheduleItemStatus, ScheduleUpdateSource
from app.models.schedule import (
    GoalSchedule,
    ScheduleCell,
    ScheduleColumn,
    ScheduleItem,
    ScheduleItemHistory,
)
from app.schemas.schedule import (
    ScheduleCellInput,
    ScheduleColumnInput,
    ScheduleItemInput,
    ScheduleItemUpdateInput,
    ScheduleSaveRequest,
)
from app.services import schedule_service
from app.services.exceptions import (
    InvalidStateTransitionError,
    ScheduleRevisionConflictError,
    ValidationError,
)
from tests import schedule_helpers

_TODAY = dt.date(2026, 6, 15)


def _item(
    *,
    id: int | None = None,
    title: str = "第1章",
    planned_start_date: dt.date = dt.date(2026, 6, 1),
    planned_end_date: dt.date = dt.date(2026, 6, 10),
    status: ScheduleItemStatus = ScheduleItemStatus.NOT_STARTED,
    actual_start_date: dt.date | None = None,
    actual_end_date: dt.date | None = None,
    cells: list[ScheduleCellInput] | None = None,
) -> ScheduleItemInput:
    return ScheduleItemInput(
        id=id,
        title=title,
        planned_start_date=planned_start_date,
        planned_end_date=planned_end_date,
        status=status,
        actual_start_date=actual_start_date,
        actual_end_date=actual_end_date,
        cells=cells or [],
    )


# ---------------------------------------------------------------------------
# validate_item_fields（6.2の全分岐）
# ---------------------------------------------------------------------------


def test_validate_item_fields_accepts_minimal_not_started_item():
    schedule_service.validate_item_fields(
        title="第1章",
        planned_start_date=dt.date(2026, 6, 1),
        planned_end_date=dt.date(2026, 6, 10),
        status=ScheduleItemStatus.NOT_STARTED,
        actual_start_date=None,
        actual_end_date=None,
        today=_TODAY,
    )


def test_validate_item_fields_rejects_blank_title():
    with pytest.raises(ValidationError):
        schedule_service.validate_item_fields(
            title="   ",
            planned_start_date=dt.date(2026, 6, 1),
            planned_end_date=dt.date(2026, 6, 10),
            status=ScheduleItemStatus.NOT_STARTED,
            actual_start_date=None,
            actual_end_date=None,
            today=_TODAY,
        )


def test_validate_item_fields_rejects_planned_start_after_end():
    with pytest.raises(ValidationError):
        schedule_service.validate_item_fields(
            title="第1章",
            planned_start_date=dt.date(2026, 6, 10),
            planned_end_date=dt.date(2026, 6, 1),
            status=ScheduleItemStatus.NOT_STARTED,
            actual_start_date=None,
            actual_end_date=None,
            today=_TODAY,
        )


def test_validate_item_fields_rejects_not_started_with_actual_start_date():
    with pytest.raises(ValidationError):
        schedule_service.validate_item_fields(
            title="第1章",
            planned_start_date=dt.date(2026, 6, 1),
            planned_end_date=dt.date(2026, 6, 10),
            status=ScheduleItemStatus.NOT_STARTED,
            actual_start_date=dt.date(2026, 6, 1),
            actual_end_date=None,
            today=_TODAY,
        )


def test_validate_item_fields_in_progress_requires_actual_start_date():
    with pytest.raises(ValidationError):
        schedule_service.validate_item_fields(
            title="第1章",
            planned_start_date=dt.date(2026, 6, 1),
            planned_end_date=dt.date(2026, 6, 10),
            status=ScheduleItemStatus.IN_PROGRESS,
            actual_start_date=None,
            actual_end_date=None,
            today=_TODAY,
        )


def test_validate_item_fields_in_progress_rejects_actual_end_date():
    with pytest.raises(ValidationError):
        schedule_service.validate_item_fields(
            title="第1章",
            planned_start_date=dt.date(2026, 6, 1),
            planned_end_date=dt.date(2026, 6, 10),
            status=ScheduleItemStatus.IN_PROGRESS,
            actual_start_date=dt.date(2026, 6, 1),
            actual_end_date=dt.date(2026, 6, 2),
            today=_TODAY,
        )


def test_validate_item_fields_in_progress_accepts_actual_start_date_only():
    schedule_service.validate_item_fields(
        title="第1章",
        planned_start_date=dt.date(2026, 6, 1),
        planned_end_date=dt.date(2026, 6, 10),
        status=ScheduleItemStatus.IN_PROGRESS,
        actual_start_date=dt.date(2026, 6, 1),
        actual_end_date=None,
        today=_TODAY,
    )


def test_validate_item_fields_done_requires_both_actual_dates():
    with pytest.raises(ValidationError):
        schedule_service.validate_item_fields(
            title="第1章",
            planned_start_date=dt.date(2026, 6, 1),
            planned_end_date=dt.date(2026, 6, 10),
            status=ScheduleItemStatus.DONE,
            actual_start_date=dt.date(2026, 6, 1),
            actual_end_date=None,
            today=_TODAY,
        )


def test_validate_item_fields_done_accepts_both_actual_dates():
    schedule_service.validate_item_fields(
        title="第1章",
        planned_start_date=dt.date(2026, 6, 1),
        planned_end_date=dt.date(2026, 6, 10),
        status=ScheduleItemStatus.DONE,
        actual_start_date=dt.date(2026, 6, 1),
        actual_end_date=dt.date(2026, 6, 2),
        today=_TODAY,
    )


def test_validate_item_fields_cancelled_rejects_actual_end_date_only():
    with pytest.raises(ValidationError):
        schedule_service.validate_item_fields(
            title="第1章",
            planned_start_date=dt.date(2026, 6, 1),
            planned_end_date=dt.date(2026, 6, 10),
            status=ScheduleItemStatus.CANCELLED,
            actual_start_date=None,
            actual_end_date=dt.date(2026, 6, 2),
            today=_TODAY,
        )


def test_validate_item_fields_cancelled_accepts_no_actual_dates():
    schedule_service.validate_item_fields(
        title="第1章",
        planned_start_date=dt.date(2026, 6, 1),
        planned_end_date=dt.date(2026, 6, 10),
        status=ScheduleItemStatus.CANCELLED,
        actual_start_date=None,
        actual_end_date=None,
        today=_TODAY,
    )


def test_validate_item_fields_rejects_actual_start_after_actual_end():
    with pytest.raises(ValidationError):
        schedule_service.validate_item_fields(
            title="第1章",
            planned_start_date=dt.date(2026, 6, 1),
            planned_end_date=dt.date(2026, 6, 10),
            status=ScheduleItemStatus.DONE,
            actual_start_date=dt.date(2026, 6, 5),
            actual_end_date=dt.date(2026, 6, 4),
            today=_TODAY,
        )


def test_validate_item_fields_rejects_actual_start_date_in_future():
    with pytest.raises(ValidationError):
        schedule_service.validate_item_fields(
            title="第1章",
            planned_start_date=dt.date(2026, 6, 1),
            planned_end_date=dt.date(2026, 6, 10),
            status=ScheduleItemStatus.IN_PROGRESS,
            actual_start_date=_TODAY + dt.timedelta(days=1),
            actual_end_date=None,
            today=_TODAY,
        )


def test_validate_item_fields_rejects_actual_end_date_in_future():
    with pytest.raises(ValidationError):
        schedule_service.validate_item_fields(
            title="第1章",
            planned_start_date=dt.date(2026, 6, 1),
            planned_end_date=dt.date(2026, 6, 10),
            status=ScheduleItemStatus.DONE,
            actual_start_date=dt.date(2026, 6, 1),
            actual_end_date=_TODAY + dt.timedelta(days=1),
            today=_TODAY,
        )


def test_validate_item_fields_accepts_actual_date_equal_to_today():
    schedule_service.validate_item_fields(
        title="第1章",
        planned_start_date=dt.date(2026, 6, 1),
        planned_end_date=dt.date(2026, 6, 10),
        status=ScheduleItemStatus.IN_PROGRESS,
        actual_start_date=_TODAY,
        actual_end_date=None,
        today=_TODAY,
    )


# ---------------------------------------------------------------------------
# get_schedule_view（既定値、D-24・revisionの既定0）
# ---------------------------------------------------------------------------


def test_get_schedule_view_returns_defaults_when_no_schedule_row_exists(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    view = schedule_service.get_schedule_view(seeded_session, goal)
    assert view.revision == 0
    assert view.frozen_row_count == 0
    assert view.frozen_column_count == 1
    assert view.columns == []
    assert view.items == []


# ---------------------------------------------------------------------------
# save_schedule（差分更新・revision・認可境界・上限・重複）
# ---------------------------------------------------------------------------


def test_save_schedule_creates_items_and_columns_and_bumps_revision(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    request = ScheduleSaveRequest(
        revision=0,
        columns=[ScheduleColumnInput(temp_key="c1", name="担当")],
        items=[
            _item(
                title="第1章",
                cells=[ScheduleCellInput(column_temp_key="c1", value="自分")],
            )
        ],
    )

    view = schedule_service.save_schedule(seeded_session, goal, request, _TODAY)

    assert view.revision == 1
    assert [c.name for c in view.columns] == ["担当"]
    assert [i.title for i in view.items] == ["第1章"]
    item_id = view.items[0].id
    column_id = view.columns[0].id
    assert view.cells_by_item_id[item_id][column_id] == "自分"
    # 作成時にも履歴が1件残ること（本書7.1「行の作成時...にだけ1行追加する」）。
    histories = seeded_session.query(ScheduleItemHistory).all()
    assert len(histories) == 1
    assert histories[0].schedule_item_id == item_id


def test_save_schedule_preserves_item_id_on_update_diff(seeded_session):
    """行IDを維持する差分更新であること（全件の削除・再作成をしない、D-06）を固定する。"""
    goal = schedule_helpers.make_goal(seeded_session)
    first = schedule_service.save_schedule(
        seeded_session, goal, ScheduleSaveRequest(revision=0, items=[_item(title="第1章")]), _TODAY
    )
    item_id = first.items[0].id

    second = schedule_service.save_schedule(
        seeded_session,
        goal,
        ScheduleSaveRequest(revision=1, items=[_item(id=item_id, title="第1章（改訂）")]),
        _TODAY,
    )

    assert second.items[0].id == item_id
    assert second.items[0].title == "第1章（改訂）"
    assert second.revision == 2


def test_save_schedule_deletes_items_not_resent(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    first = schedule_service.save_schedule(
        seeded_session,
        goal,
        ScheduleSaveRequest(revision=0, items=[_item(title="第1章"), _item(title="第2章")]),
        _TODAY,
    )
    kept_id = first.items[0].id

    second = schedule_service.save_schedule(
        seeded_session,
        goal,
        ScheduleSaveRequest(revision=1, items=[_item(id=kept_id, title="第1章")]),
        _TODAY,
    )

    assert [i.id for i in second.items] == [kept_id]
    assert seeded_session.query(ScheduleItem).count() == 1


def test_save_schedule_only_adds_history_when_status_or_actual_dates_change(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    first = schedule_service.save_schedule(
        seeded_session, goal, ScheduleSaveRequest(revision=0, items=[_item(title="第1章")]), _TODAY
    )
    item_id = first.items[0].id

    # 作業内容（履歴の対象外）だけを変えても履歴は増えない。
    schedule_service.save_schedule(
        seeded_session,
        goal,
        ScheduleSaveRequest(revision=1, items=[_item(id=item_id, title="第1章（改訂）")]),
        _TODAY,
    )
    assert seeded_session.query(ScheduleItemHistory).count() == 1

    # 状況を変えると履歴が増える。
    schedule_service.save_schedule(
        seeded_session,
        goal,
        ScheduleSaveRequest(
            revision=2,
            items=[
                _item(
                    id=item_id,
                    title="第1章（改訂）",
                    status=ScheduleItemStatus.IN_PROGRESS,
                    actual_start_date=_TODAY,
                )
            ],
        ),
        _TODAY,
    )
    assert seeded_session.query(ScheduleItemHistory).count() == 2


def test_save_schedule_clears_cell_when_value_is_blank(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    first = schedule_service.save_schedule(
        seeded_session,
        goal,
        ScheduleSaveRequest(
            revision=0,
            columns=[ScheduleColumnInput(temp_key="c1", name="担当")],
            items=[
                _item(title="第1章", cells=[ScheduleCellInput(column_temp_key="c1", value="自分")])
            ],
        ),
        _TODAY,
    )
    item_id = first.items[0].id
    column_id = first.columns[0].id
    assert seeded_session.query(ScheduleCell).count() == 1

    schedule_service.save_schedule(
        seeded_session,
        goal,
        ScheduleSaveRequest(
            revision=1,
            columns=[ScheduleColumnInput(id=column_id, name="担当")],
            items=[
                _item(
                    id=item_id,
                    title="第1章",
                    cells=[ScheduleCellInput(column_id=column_id, value="")],
                )
            ],
        ),
        _TODAY,
    )

    assert seeded_session.query(ScheduleCell).count() == 0


def test_save_schedule_rejects_mismatched_revision(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    with pytest.raises(ScheduleRevisionConflictError):
        schedule_service.save_schedule(
            seeded_session, goal, ScheduleSaveRequest(revision=5, items=[]), _TODAY
        )


def test_save_schedule_rejects_item_id_from_another_goal(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session, "目標A")
    other_goal = schedule_helpers.make_goal(seeded_session, "目標B")
    other = schedule_service.save_schedule(
        seeded_session,
        other_goal,
        ScheduleSaveRequest(revision=0, items=[_item(title="他目標の行")]),
        _TODAY,
    )
    other_item_id = other.items[0].id

    with pytest.raises(ValidationError):
        schedule_service.save_schedule(
            seeded_session,
            goal,
            ScheduleSaveRequest(revision=0, items=[_item(id=other_item_id, title="乗っ取り")]),
            _TODAY,
        )
    # 検証で拒否した場合、対象の目標には何も反映されないこと。
    assert seeded_session.query(ScheduleItem).filter_by(goal_id=goal.id).count() == 0


def test_save_schedule_rejects_column_id_from_another_goal(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session, "目標A")
    other_goal = schedule_helpers.make_goal(seeded_session, "目標B")
    other = schedule_service.save_schedule(
        seeded_session,
        other_goal,
        ScheduleSaveRequest(
            revision=0, columns=[ScheduleColumnInput(temp_key="c1", name="他目標の列")]
        ),
        _TODAY,
    )
    other_column_id = other.columns[0].id

    with pytest.raises(ValidationError):
        schedule_service.save_schedule(
            seeded_session,
            goal,
            ScheduleSaveRequest(
                revision=0, columns=[ScheduleColumnInput(id=other_column_id, name="乗っ取り")]
            ),
            _TODAY,
        )
    # 検証で拒否した場合、どちらの目標の列も変化しないこと（認可境界レビュー指摘）。
    assert seeded_session.query(ScheduleColumn).filter_by(goal_id=goal.id).count() == 0
    unchanged = seeded_session.get(ScheduleColumn, other_column_id)
    assert unchanged.name == "他目標の列"


def test_save_schedule_rejects_cell_referencing_another_goals_real_column(seeded_session):
    """セル経由で他目標の実在する列IDを直接参照しても拒否されること（columns配列に
    含めず、cellsだけに書く迂回を想定した認可境界テスト）。"""
    goal = schedule_helpers.make_goal(seeded_session, "目標A")
    other_goal = schedule_helpers.make_goal(seeded_session, "目標B")
    other = schedule_service.save_schedule(
        seeded_session,
        other_goal,
        ScheduleSaveRequest(
            revision=0, columns=[ScheduleColumnInput(temp_key="c1", name="他目標の列")]
        ),
        _TODAY,
    )
    other_column_id = other.columns[0].id

    with pytest.raises(ValidationError):
        schedule_service.save_schedule(
            seeded_session,
            goal,
            ScheduleSaveRequest(
                revision=0,
                items=[
                    _item(
                        title="第1章",
                        cells=[ScheduleCellInput(column_id=other_column_id, value="乗っ取り")],
                    )
                ],
            ),
            _TODAY,
        )
    assert seeded_session.query(ScheduleItem).filter_by(goal_id=goal.id).count() == 0
    assert seeded_session.query(ScheduleCell).count() == 0


def test_save_schedule_rejects_duplicate_item_id_in_request(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    first = schedule_service.save_schedule(
        seeded_session, goal, ScheduleSaveRequest(revision=0, items=[_item(title="第1章")]), _TODAY
    )
    item_id = first.items[0].id

    with pytest.raises(ValidationError):
        schedule_service.save_schedule(
            seeded_session,
            goal,
            ScheduleSaveRequest(
                revision=1,
                items=[
                    _item(id=item_id, title="第1章（改訂A）"),
                    _item(id=item_id, title="第1章（改訂B）"),
                ],
            ),
            _TODAY,
        )


def test_validate_item_fields_cancelled_accepts_actual_start_date_only():
    """中止：実績開始日のみは許容される（実績終了日だけの入力のみが不可、6.2）。"""
    schedule_service.validate_item_fields(
        title="第1章",
        planned_start_date=dt.date(2026, 6, 1),
        planned_end_date=dt.date(2026, 6, 10),
        status=ScheduleItemStatus.CANCELLED,
        actual_start_date=dt.date(2026, 6, 5),
        actual_end_date=None,
        today=_TODAY,
    )


def test_save_schedule_rejects_title_exceeding_max_chars(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    schedule_helpers.set_setting(seeded_session, SCHEDULE_ITEM_TITLE_MAX_CHARS, "5")
    with pytest.raises(ValidationError):
        schedule_service.save_schedule(
            seeded_session,
            goal,
            ScheduleSaveRequest(revision=0, items=[_item(title="123456")]),
            _TODAY,
        )


def test_save_schedule_rejects_description_exceeding_max_chars(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    schedule_helpers.set_setting(seeded_session, SCHEDULE_ITEM_DESCRIPTION_MAX_CHARS, "3")
    with pytest.raises(ValidationError):
        schedule_service.save_schedule(
            seeded_session,
            goal,
            ScheduleSaveRequest(
                revision=0,
                items=[
                    ScheduleItemInput(
                        title="第1章",
                        description="1234",
                        planned_start_date=dt.date(2026, 6, 1),
                        planned_end_date=dt.date(2026, 6, 10),
                    )
                ],
            ),
            _TODAY,
        )


def test_save_schedule_rejects_column_name_exceeding_max_chars(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    schedule_helpers.set_setting(seeded_session, SCHEDULE_COLUMN_NAME_MAX_CHARS, "3")
    with pytest.raises(ValidationError):
        schedule_service.save_schedule(
            seeded_session,
            goal,
            ScheduleSaveRequest(
                revision=0, columns=[ScheduleColumnInput(temp_key="c1", name="1234")]
            ),
            _TODAY,
        )


def test_save_schedule_rejects_cell_value_exceeding_max_chars(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    schedule_helpers.set_setting(seeded_session, SCHEDULE_CELL_VALUE_MAX_CHARS, "3")
    with pytest.raises(ValidationError):
        schedule_service.save_schedule(
            seeded_session,
            goal,
            ScheduleSaveRequest(
                revision=0,
                columns=[ScheduleColumnInput(temp_key="c1", name="担当")],
                items=[
                    _item(
                        title="第1章",
                        cells=[ScheduleCellInput(column_temp_key="c1", value="1234")],
                    )
                ],
            ),
            _TODAY,
        )


def test_save_schedule_rejects_cell_referencing_column_not_in_request(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    with pytest.raises(ValidationError):
        schedule_service.save_schedule(
            seeded_session,
            goal,
            ScheduleSaveRequest(
                revision=0,
                items=[
                    _item(
                        title="第1章",
                        cells=[ScheduleCellInput(column_id=999, value="未知の列")],
                    )
                ],
            ),
            _TODAY,
        )


def test_save_schedule_rejects_blank_column_name(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    with pytest.raises(ValidationError):
        schedule_service.save_schedule(
            seeded_session,
            goal,
            ScheduleSaveRequest(
                revision=0, columns=[ScheduleColumnInput(temp_key="c1", name="   ")]
            ),
            _TODAY,
        )


def test_save_schedule_rejects_duplicate_temp_key(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    with pytest.raises(ValidationError):
        schedule_service.save_schedule(
            seeded_session,
            goal,
            ScheduleSaveRequest(
                revision=0,
                columns=[
                    ScheduleColumnInput(temp_key="c1", name="担当"),
                    ScheduleColumnInput(temp_key="c1", name="優先度"),
                ],
            ),
            _TODAY,
        )


def test_save_schedule_rejects_duplicate_cell_for_same_column(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    with pytest.raises(ValidationError):
        schedule_service.save_schedule(
            seeded_session,
            goal,
            ScheduleSaveRequest(
                revision=0,
                columns=[ScheduleColumnInput(temp_key="c1", name="担当")],
                items=[
                    _item(
                        title="第1章",
                        cells=[
                            ScheduleCellInput(column_temp_key="c1", value="A"),
                            ScheduleCellInput(column_temp_key="c1", value="B"),
                        ],
                    )
                ],
            ),
            _TODAY,
        )


def test_save_schedule_deletes_columns_not_resent(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    first = schedule_service.save_schedule(
        seeded_session,
        goal,
        ScheduleSaveRequest(revision=0, columns=[ScheduleColumnInput(temp_key="c1", name="担当")]),
        _TODAY,
    )
    assert seeded_session.query(ScheduleColumn).count() == 1

    second = schedule_service.save_schedule(
        seeded_session, goal, ScheduleSaveRequest(revision=first.revision, columns=[]), _TODAY
    )

    assert second.columns == []
    assert seeded_session.query(ScheduleColumn).count() == 0


def test_save_schedule_updates_existing_cell_value(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    first = schedule_service.save_schedule(
        seeded_session,
        goal,
        ScheduleSaveRequest(
            revision=0,
            columns=[ScheduleColumnInput(temp_key="c1", name="担当")],
            items=[
                _item(title="第1章", cells=[ScheduleCellInput(column_temp_key="c1", value="自分")])
            ],
        ),
        _TODAY,
    )
    item_id = first.items[0].id
    column_id = first.columns[0].id

    second = schedule_service.save_schedule(
        seeded_session,
        goal,
        ScheduleSaveRequest(
            revision=first.revision,
            columns=[ScheduleColumnInput(id=column_id, name="担当")],
            items=[
                _item(
                    id=item_id,
                    title="第1章",
                    cells=[ScheduleCellInput(column_id=column_id, value="他の人")],
                )
            ],
        ),
        _TODAY,
    )

    assert second.cells_by_item_id[item_id][column_id] == "他の人"


def test_save_schedule_leaves_cell_absent_when_blank_from_the_start(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    view = schedule_service.save_schedule(
        seeded_session,
        goal,
        ScheduleSaveRequest(
            revision=0,
            columns=[ScheduleColumnInput(temp_key="c1", name="担当")],
            items=[_item(title="第1章", cells=[ScheduleCellInput(column_temp_key="c1", value="")])],
        ),
        _TODAY,
    )

    item_id = view.items[0].id
    assert view.cells_by_item_id[item_id] == {}
    assert seeded_session.query(ScheduleCell).count() == 0


def test_save_schedule_rejects_duplicate_column_name(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    with pytest.raises(ValidationError):
        schedule_service.save_schedule(
            seeded_session,
            goal,
            ScheduleSaveRequest(
                revision=0,
                columns=[
                    ScheduleColumnInput(temp_key="c1", name="担当"),
                    ScheduleColumnInput(temp_key="c2", name="担当"),
                ],
            ),
            _TODAY,
        )


def test_save_schedule_rejects_too_many_custom_columns(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    schedule_helpers.set_setting(seeded_session, SCHEDULE_MAX_CUSTOM_COLUMNS, "1")
    with pytest.raises(ValidationError):
        schedule_service.save_schedule(
            seeded_session,
            goal,
            ScheduleSaveRequest(
                revision=0,
                columns=[
                    ScheduleColumnInput(temp_key="c1", name="担当"),
                    ScheduleColumnInput(temp_key="c2", name="優先度"),
                ],
            ),
            _TODAY,
        )


def test_save_schedule_rejects_too_many_items(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    schedule_helpers.set_setting(seeded_session, SCHEDULE_MAX_ITEMS, "1")
    with pytest.raises(ValidationError):
        schedule_service.save_schedule(
            seeded_session,
            goal,
            ScheduleSaveRequest(revision=0, items=[_item(title="第1章"), _item(title="第2章")]),
            _TODAY,
        )


def test_save_schedule_rejects_closed_goal(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session, status=GoalStatus.CLOSED_WITH_RESULT)
    with pytest.raises(InvalidStateTransitionError):
        schedule_service.save_schedule(
            seeded_session, goal, ScheduleSaveRequest(revision=0, items=[]), _TODAY
        )


# ---------------------------------------------------------------------------
# update_view_setting（D-24・D-25、revisionは変えない）
# ---------------------------------------------------------------------------


def test_update_view_setting_does_not_change_revision(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    view = schedule_service.save_schedule(
        seeded_session, goal, ScheduleSaveRequest(revision=0, items=[_item(title="第1章")]), _TODAY
    )
    assert view.revision == 1

    schedule = schedule_service.update_view_setting(seeded_session, goal, 1, 2)

    assert schedule.revision == 1
    assert schedule.frozen_row_count == 1
    assert schedule.frozen_column_count == 2


def test_update_view_setting_clamps_to_current_row_and_column_counts(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    schedule_service.save_schedule(
        seeded_session, goal, ScheduleSaveRequest(revision=0, items=[_item(title="第1章")]), _TODAY
    )

    schedule = schedule_service.update_view_setting(seeded_session, goal, 50, 50)

    assert schedule.frozen_row_count == 1  # 現在の行数(1)に収まる
    assert schedule.frozen_column_count == 7  # 既定7列、追加列0の合計に収まる


def test_update_view_setting_creates_row_when_none_exists(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    schedule = schedule_service.update_view_setting(seeded_session, goal, 0, 1)
    assert schedule.revision == 0
    assert schedule.frozen_row_count == 0
    assert schedule.frozen_column_count == 1


def test_update_view_setting_rejects_closed_goal(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session, status=GoalStatus.CLOSED_WITH_RESULT)
    with pytest.raises(InvalidStateTransitionError):
        schedule_service.update_view_setting(seeded_session, goal, 0, 1)


# --- list_schedule_items_for_report / apply_report_schedule_item_updates（単位4） ---


def _save_item(
    session,
    goal,
    *,
    title: str = "第1章",
    planned_start_date: dt.date = dt.date(2026, 6, 1),
    planned_end_date: dt.date = dt.date(2026, 6, 10),
    status: ScheduleItemStatus = ScheduleItemStatus.NOT_STARTED,
    actual_start_date: dt.date | None = None,
    actual_end_date: dt.date | None = None,
):
    view = schedule_service.save_schedule(
        session,
        goal,
        ScheduleSaveRequest(
            revision=0,
            items=[
                _item(
                    title=title,
                    planned_start_date=planned_start_date,
                    planned_end_date=planned_end_date,
                    status=status,
                    actual_start_date=actual_start_date,
                    actual_end_date=actual_end_date,
                )
            ],
        ),
        _TODAY,
    )
    return view.items[0].id


def test_list_schedule_items_for_report_returns_empty_when_no_active_goals(seeded_session):
    schedule_helpers.make_goal(seeded_session, status=GoalStatus.DRAFT)
    assert schedule_service.list_schedule_items_for_report(seeded_session, _TODAY) == []


def test_list_schedule_items_for_report_excludes_inactive_goal(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session, status=GoalStatus.PAUSED)
    _save_item(
        seeded_session, goal, status=ScheduleItemStatus.IN_PROGRESS, actual_start_date=_TODAY
    )

    assert schedule_service.list_schedule_items_for_report(seeded_session, _TODAY) == []


def test_list_schedule_items_for_report_excludes_done_and_cancelled_items(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    _save_item(
        seeded_session,
        goal,
        title="完了行",
        status=ScheduleItemStatus.DONE,
        actual_start_date=dt.date(2026, 6, 1),
        actual_end_date=dt.date(2026, 6, 2),
    )

    assert schedule_service.list_schedule_items_for_report(seeded_session, _TODAY) == []


def test_list_schedule_items_for_report_excludes_goal_with_no_eligible_items(seeded_session):
    """ACTIVEな目標でも、対象になる行が1件も無ければ応答に含めない（D-38）。"""
    goal = schedule_helpers.make_goal(seeded_session)
    _save_item(seeded_session, goal, status=ScheduleItemStatus.CANCELLED)

    assert schedule_service.list_schedule_items_for_report(seeded_session, _TODAY) == []


def test_list_schedule_items_for_report_includes_goal_metadata_and_multiple_categories(
    seeded_session,
):
    exam_goal = schedule_helpers.make_goal(seeded_session, "資格目標", category=GoalCategory.EXAM)
    reading_goal = schedule_helpers.make_goal(
        seeded_session, "読書目標", category=GoalCategory.READING
    )
    _save_item(
        seeded_session, exam_goal, status=ScheduleItemStatus.IN_PROGRESS, actual_start_date=_TODAY
    )
    _save_item(
        seeded_session,
        reading_goal,
        status=ScheduleItemStatus.IN_PROGRESS,
        actual_start_date=_TODAY,
    )

    result = schedule_service.list_schedule_items_for_report(seeded_session, _TODAY)

    assert {goal.goal_id: goal.goal_category for goal in result} == {
        exam_goal.id: GoalCategory.EXAM,
        reading_goal.id: GoalCategory.READING,
    }
    assert {goal.goal_id: goal.goal_name for goal in result} == {
        exam_goal.id: "資格目標",
        reading_goal.id: "読書目標",
    }


@pytest.mark.parametrize(
    ("status", "planned_start_date", "planned_end_date", "expected"),
    [
        # 報告対象日が予定期間内（D-33条件1）。
        (ScheduleItemStatus.NOT_STARTED, dt.date(2026, 6, 10), dt.date(2026, 6, 20), True),
        # 進行中（D-33条件2、予定期間外でも表示する）。
        (ScheduleItemStatus.IN_PROGRESS, dt.date(2026, 1, 1), dt.date(2026, 1, 5), True),
        # 未着手で予定終了日を過ぎている（D-33条件3）。
        (ScheduleItemStatus.NOT_STARTED, dt.date(2026, 1, 1), dt.date(2026, 1, 5), True),
        # 未着手で予定期間がまだ先（いずれにも当たらない）。
        (ScheduleItemStatus.NOT_STARTED, dt.date(2026, 7, 1), dt.date(2026, 7, 10), False),
    ],
)
def test_list_schedule_items_for_report_default_visible_follows_d33(
    seeded_session, status, planned_start_date, planned_end_date, expected
):
    goal = schedule_helpers.make_goal(seeded_session)
    actual_start = _TODAY if status == ScheduleItemStatus.IN_PROGRESS else None
    _save_item(
        seeded_session,
        goal,
        status=status,
        planned_start_date=planned_start_date,
        planned_end_date=planned_end_date,
        actual_start_date=actual_start,
    )

    result = schedule_service.list_schedule_items_for_report(seeded_session, _TODAY)

    assert result[0].items[0].default_visible is expected


# --- list_schedule_items_updated_on（確定済みの種別向け、軽微な修正3） ---


def test_list_schedule_items_updated_on_returns_empty_when_nothing_recorded(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    _save_item(seeded_session, goal)

    assert schedule_service.list_schedule_items_updated_on(seeded_session, _TODAY) == []


def test_list_schedule_items_updated_on_ignores_schedule_screen_edits(seeded_session):
    """スケジュール画面での編集はrecord_date=NULLのため対象にならない（本書7.1）。"""
    goal = schedule_helpers.make_goal(seeded_session)
    _save_item(
        seeded_session, goal, status=ScheduleItemStatus.IN_PROGRESS, actual_start_date=_TODAY
    )

    assert schedule_service.list_schedule_items_updated_on(seeded_session, _TODAY) == []


def test_list_schedule_items_updated_on_includes_completed_items(seeded_session):
    """軽微な修正3：ライブ表示（list_schedule_items_for_report）と異なり、完了にした行も
    その日に更新していれば表示される。"""
    goal = schedule_helpers.make_goal(seeded_session)
    item_id = _save_item(seeded_session, goal)
    schedule_service.apply_report_schedule_item_updates(
        seeded_session,
        [
            ScheduleItemUpdateInput(
                schedule_item_id=item_id,
                status=ScheduleItemStatus.DONE,
                actual_start_date=dt.date(2026, 6, 1),
                actual_end_date=_TODAY,
            )
        ],
        category=GoalCategory.EXAM,
        target_date=_TODAY,
        today=_TODAY,
        source=ScheduleUpdateSource.DAILY_REPORT,
    )

    result = schedule_service.list_schedule_items_updated_on(seeded_session, _TODAY)

    assert len(result) == 1
    assert result[0].goal_id == goal.id
    assert result[0].items[0].status == ScheduleItemStatus.DONE
    assert result[0].items[0].actual_end_date == _TODAY
    assert result[0].items[0].default_visible is True


def test_list_schedule_items_updated_on_includes_items_of_an_inactive_goal(seeded_session):
    """ライブ表示はACTIVEな目標のみだが、本関数は過去の確定内容をそのまま示すため
    現在PAUSED・CLOSEDな目標の行も含める。"""
    goal = schedule_helpers.make_goal(seeded_session)
    item_id = _save_item(seeded_session, goal)
    schedule_service.apply_report_schedule_item_updates(
        seeded_session,
        [
            ScheduleItemUpdateInput(
                schedule_item_id=item_id,
                status=ScheduleItemStatus.IN_PROGRESS,
                actual_start_date=_TODAY,
            )
        ],
        category=GoalCategory.EXAM,
        target_date=_TODAY,
        today=_TODAY,
        source=ScheduleUpdateSource.DAILY_REPORT,
    )
    goal.status = GoalStatus.PAUSED
    seeded_session.flush()

    result = schedule_service.list_schedule_items_updated_on(seeded_session, _TODAY)

    assert [goal_items.goal_id for goal_items in result] == [goal.id]


def test_list_schedule_items_updated_on_uses_the_latest_value_for_the_same_day(seeded_session):
    """同じ行が同日に複数回更新された場合は、最後に記録された値のみを使う。"""
    goal = schedule_helpers.make_goal(seeded_session)
    item_id = _save_item(seeded_session, goal)
    schedule_service.apply_report_schedule_item_updates(
        seeded_session,
        [
            ScheduleItemUpdateInput(
                schedule_item_id=item_id,
                status=ScheduleItemStatus.IN_PROGRESS,
                actual_start_date=_TODAY,
            )
        ],
        category=GoalCategory.EXAM,
        target_date=_TODAY,
        today=_TODAY,
        source=ScheduleUpdateSource.PROGRESS_ONLY,
    )
    schedule_service.apply_report_schedule_item_updates(
        seeded_session,
        [
            ScheduleItemUpdateInput(
                schedule_item_id=item_id,
                status=ScheduleItemStatus.DONE,
                actual_start_date=_TODAY,
                actual_end_date=_TODAY,
            )
        ],
        category=GoalCategory.EXAM,
        target_date=_TODAY,
        today=_TODAY,
        source=ScheduleUpdateSource.DAILY_REPORT,
    )

    result = schedule_service.list_schedule_items_updated_on(seeded_session, _TODAY)

    assert len(result[0].items) == 1
    assert result[0].items[0].status == ScheduleItemStatus.DONE


def test_list_schedule_items_updated_on_keeps_the_row_with_the_latest_changed_at(seeded_session):
    """「最後に記録された値」はchanged_atで判定する。先に挿入された行の方がchanged_atが
    新しい場合（通常は起こらないが、挿入順とchanged_atの順が食い違う場合の判定を固定する）、
    後から読み取った行で上書きしない。"""
    goal = schedule_helpers.make_goal(seeded_session)
    item_id = _save_item(seeded_session, goal)
    newer = ScheduleItemHistory(
        schedule_item_id=item_id,
        source=ScheduleUpdateSource.DAILY_REPORT,
        record_date=_TODAY,
        status=ScheduleItemStatus.DONE,
        actual_start_date=_TODAY,
        actual_end_date=_TODAY,
        changed_at=dt.datetime(2026, 6, 15, 12, 0, tzinfo=dt.UTC),
    )
    older = ScheduleItemHistory(
        schedule_item_id=item_id,
        source=ScheduleUpdateSource.DAILY_REPORT,
        record_date=_TODAY,
        status=ScheduleItemStatus.IN_PROGRESS,
        actual_start_date=_TODAY,
        changed_at=dt.datetime(2026, 6, 15, 9, 0, tzinfo=dt.UTC),
    )
    seeded_session.add_all([newer, older])
    seeded_session.flush()

    result = schedule_service.list_schedule_items_updated_on(seeded_session, _TODAY)

    assert len(result[0].items) == 1
    assert result[0].items[0].status == ScheduleItemStatus.DONE


def test_list_schedule_items_updated_on_ignores_other_dates(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    item_id = _save_item(seeded_session, goal)
    other_date = _TODAY - dt.timedelta(days=1)
    schedule_service.apply_report_schedule_item_updates(
        seeded_session,
        [
            ScheduleItemUpdateInput(
                schedule_item_id=item_id,
                status=ScheduleItemStatus.IN_PROGRESS,
                actual_start_date=other_date,
            )
        ],
        category=GoalCategory.EXAM,
        target_date=other_date,
        today=_TODAY,
        source=ScheduleUpdateSource.DAILY_REPORT,
    )

    assert schedule_service.list_schedule_items_updated_on(seeded_session, _TODAY) == []
    assert len(schedule_service.list_schedule_items_updated_on(seeded_session, other_date)) == 1


def test_apply_report_schedule_item_updates_noop_when_empty(seeded_session):
    # 例外を投げず、問い合わせも行わないことを確認する（空配列の早期return）。
    schedule_service.apply_report_schedule_item_updates(
        seeded_session,
        [],
        category=GoalCategory.EXAM,
        target_date=_TODAY,
        today=_TODAY,
        source=ScheduleUpdateSource.DAILY_REPORT,
    )


def test_apply_report_schedule_item_updates_rejects_duplicate_ids(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    item_id = _save_item(seeded_session, goal)

    with pytest.raises(ValidationError):
        schedule_service.apply_report_schedule_item_updates(
            seeded_session,
            [
                ScheduleItemUpdateInput(
                    schedule_item_id=item_id,
                    status=ScheduleItemStatus.IN_PROGRESS,
                    actual_start_date=_TODAY,
                ),
                ScheduleItemUpdateInput(
                    schedule_item_id=item_id, status=ScheduleItemStatus.NOT_STARTED
                ),
            ],
            category=None,
            target_date=_TODAY,
            today=_TODAY,
            source=ScheduleUpdateSource.PROGRESS_ONLY,
        )


def test_apply_report_schedule_item_updates_rejects_unknown_id(seeded_session):
    with pytest.raises(ValidationError):
        schedule_service.apply_report_schedule_item_updates(
            seeded_session,
            [ScheduleItemUpdateInput(schedule_item_id=9999, status=ScheduleItemStatus.NOT_STARTED)],
            category=None,
            target_date=_TODAY,
            today=_TODAY,
            source=ScheduleUpdateSource.PROGRESS_ONLY,
        )


def test_apply_report_schedule_item_updates_rejects_item_from_different_category(seeded_session):
    reading_goal = schedule_helpers.make_goal(seeded_session, category=GoalCategory.READING)
    item_id = _save_item(seeded_session, reading_goal)

    with pytest.raises(ValidationError):
        schedule_service.apply_report_schedule_item_updates(
            seeded_session,
            [
                ScheduleItemUpdateInput(
                    schedule_item_id=item_id, status=ScheduleItemStatus.NOT_STARTED
                )
            ],
            category=GoalCategory.EXAM,
            target_date=_TODAY,
            today=_TODAY,
            source=ScheduleUpdateSource.DAILY_REPORT,
        )


def test_apply_report_schedule_item_updates_accepts_any_category_when_none(seeded_session):
    """progress API（category=None）はEXAM以外の行も受け付ける（D-36）。"""
    work_goal = schedule_helpers.make_goal(seeded_session, category=GoalCategory.WORK)
    item_id = _save_item(seeded_session, work_goal)

    schedule_service.apply_report_schedule_item_updates(
        seeded_session,
        [
            ScheduleItemUpdateInput(
                schedule_item_id=item_id,
                status=ScheduleItemStatus.IN_PROGRESS,
                actual_start_date=_TODAY,
            )
        ],
        category=None,
        target_date=_TODAY,
        today=_TODAY,
        source=ScheduleUpdateSource.PROGRESS_ONLY,
    )

    assert seeded_session.get(ScheduleItem, item_id).status == ScheduleItemStatus.IN_PROGRESS


def test_apply_report_schedule_item_updates_rejects_item_of_inactive_goal(seeded_session):
    goal = schedule_helpers.make_goal(seeded_session)
    item_id = _save_item(seeded_session, goal)
    goal.status = GoalStatus.PAUSED
    seeded_session.flush()

    with pytest.raises(InvalidStateTransitionError):
        schedule_service.apply_report_schedule_item_updates(
            seeded_session,
            [
                ScheduleItemUpdateInput(
                    schedule_item_id=item_id, status=ScheduleItemStatus.NOT_STARTED
                )
            ],
            category=GoalCategory.EXAM,
            target_date=_TODAY,
            today=_TODAY,
            source=ScheduleUpdateSource.DAILY_REPORT,
        )


def test_apply_report_schedule_item_updates_rejects_item_of_closed_goal(seeded_session):
    """D-04「終了した目標」（CLOSED_WITH_RESULT/CLOSED_WITHOUT_RESULT）の行を拒否する
    （独立レビューで、PAUSEDのみでCLOSED系を明示確認していないと指摘されたため追加）。"""
    goal = schedule_helpers.make_goal(seeded_session)
    item_id = _save_item(seeded_session, goal)
    goal.status = GoalStatus.CLOSED_WITH_RESULT
    seeded_session.flush()

    with pytest.raises(InvalidStateTransitionError):
        schedule_service.apply_report_schedule_item_updates(
            seeded_session,
            [
                ScheduleItemUpdateInput(
                    schedule_item_id=item_id, status=ScheduleItemStatus.NOT_STARTED
                )
            ],
            category=GoalCategory.EXAM,
            target_date=_TODAY,
            today=_TODAY,
            source=ScheduleUpdateSource.DAILY_REPORT,
        )


def test_apply_report_schedule_item_updates_rejects_invalid_field_combination(seeded_session):
    """6.2の検証（validate_item_fields）をそのまま再利用していることの確認
    （IN_PROGRESSはactual_start_date必須）。"""
    goal = schedule_helpers.make_goal(seeded_session)
    item_id = _save_item(seeded_session, goal)

    with pytest.raises(ValidationError):
        schedule_service.apply_report_schedule_item_updates(
            seeded_session,
            [
                ScheduleItemUpdateInput(
                    schedule_item_id=item_id, status=ScheduleItemStatus.IN_PROGRESS
                )
            ],
            category=GoalCategory.EXAM,
            target_date=_TODAY,
            today=_TODAY,
            source=ScheduleUpdateSource.DAILY_REPORT,
        )


def test_apply_report_schedule_item_updates_applies_values_adds_history_and_creates_schedule_row(
    seeded_session,
):
    goal = schedule_helpers.make_goal(seeded_session)
    item_id = _save_item(seeded_session, goal)
    history_count_before = seeded_session.query(ScheduleItemHistory).count()

    schedule_service.apply_report_schedule_item_updates(
        seeded_session,
        [
            ScheduleItemUpdateInput(
                schedule_item_id=item_id,
                status=ScheduleItemStatus.DONE,
                actual_start_date=dt.date(2026, 6, 1),
                actual_end_date=_TODAY,
            )
        ],
        category=GoalCategory.EXAM,
        target_date=_TODAY,
        today=_TODAY,
        source=ScheduleUpdateSource.DAILY_REPORT,
    )

    item = seeded_session.get(ScheduleItem, item_id)
    assert item.status == ScheduleItemStatus.DONE
    assert item.actual_end_date == _TODAY
    histories = (
        seeded_session.query(ScheduleItemHistory)
        .filter(ScheduleItemHistory.schedule_item_id == item_id)
        .order_by(ScheduleItemHistory.id)
        .all()
    )
    assert len(histories) == history_count_before + 1
    assert histories[-1].source == ScheduleUpdateSource.DAILY_REPORT
    assert histories[-1].record_date == _TODAY
    # _save_item経由の作成時にGoalScheduleは既にrevision=1で存在するため、本更新で2へ進む。
    schedule = seeded_session.query(GoalSchedule).filter(GoalSchedule.goal_id == goal.id).one()
    assert schedule.revision == 2


def test_apply_report_schedule_item_updates_creates_goal_schedule_row_when_absent(seeded_session):
    """スケジュール画面を一度も保存していない目標（GoalSchedule行が無い）に対しても、
    revision=1で新規作成する（save_scheduleの初期化と同じ、単位4開発Todo2章補足3）。"""
    goal = schedule_helpers.make_goal(seeded_session)
    item_id = _save_item(seeded_session, goal)
    seeded_session.query(GoalSchedule).filter(GoalSchedule.goal_id == goal.id).delete()
    seeded_session.flush()

    schedule_service.apply_report_schedule_item_updates(
        seeded_session,
        [
            ScheduleItemUpdateInput(
                schedule_item_id=item_id,
                status=ScheduleItemStatus.IN_PROGRESS,
                actual_start_date=_TODAY,
            )
        ],
        category=GoalCategory.EXAM,
        target_date=_TODAY,
        today=_TODAY,
        source=ScheduleUpdateSource.DAILY_REPORT,
    )

    schedule = seeded_session.query(GoalSchedule).filter(GoalSchedule.goal_id == goal.id).one()
    assert schedule.revision == 1


def test_apply_report_schedule_item_updates_skips_history_and_revision_when_unchanged(
    seeded_session,
):
    goal = schedule_helpers.make_goal(seeded_session)
    item_id = _save_item(seeded_session, goal, status=ScheduleItemStatus.NOT_STARTED)
    schedule_before = (
        seeded_session.query(GoalSchedule).filter(GoalSchedule.goal_id == goal.id).one()
    )
    revision_before = schedule_before.revision
    history_count_before = seeded_session.query(ScheduleItemHistory).count()

    schedule_service.apply_report_schedule_item_updates(
        seeded_session,
        [ScheduleItemUpdateInput(schedule_item_id=item_id, status=ScheduleItemStatus.NOT_STARTED)],
        category=GoalCategory.EXAM,
        target_date=_TODAY,
        today=_TODAY,
        source=ScheduleUpdateSource.DAILY_REPORT,
    )

    assert seeded_session.query(ScheduleItemHistory).count() == history_count_before
    schedule_after = (
        seeded_session.query(GoalSchedule).filter(GoalSchedule.goal_id == goal.id).one()
    )
    assert schedule_after.revision == revision_before


def test_apply_report_schedule_item_updates_overwrites_with_latest_input_when_called_twice(
    seeded_session,
):
    """同じ日に繰り返し更新した場合は、最新の入力で上書きする（D-37）。"""
    goal = schedule_helpers.make_goal(seeded_session)
    item_id = _save_item(seeded_session, goal)

    schedule_service.apply_report_schedule_item_updates(
        seeded_session,
        [
            ScheduleItemUpdateInput(
                schedule_item_id=item_id,
                status=ScheduleItemStatus.IN_PROGRESS,
                actual_start_date=_TODAY,
            )
        ],
        category=None,
        target_date=_TODAY,
        today=_TODAY,
        source=ScheduleUpdateSource.PROGRESS_ONLY,
    )
    schedule_service.apply_report_schedule_item_updates(
        seeded_session,
        [
            ScheduleItemUpdateInput(
                schedule_item_id=item_id,
                status=ScheduleItemStatus.DONE,
                actual_start_date=_TODAY,
                actual_end_date=_TODAY,
            )
        ],
        category=None,
        target_date=_TODAY,
        today=_TODAY,
        source=ScheduleUpdateSource.PROGRESS_ONLY,
    )

    item = seeded_session.get(ScheduleItem, item_id)
    assert item.status == ScheduleItemStatus.DONE
    assert item.actual_end_date == _TODAY


class TestComputeDelayKind:
    """13.2の遅れの判定（単位5、ガントの遅れの印D-18もこの関数の結果を使う）。
    2種類の条件の境界（本日＝予定日、本日＝予定日＋1日）を検証する（13.10）。
    """

    def _item(self, **kwargs) -> ScheduleItem:
        defaults = dict(
            id=1,
            goal_id=1,
            title="作業項目A",
            planned_start_date=dt.date(2026, 11, 10),
            planned_end_date=dt.date(2026, 11, 20),
            status=ScheduleItemStatus.NOT_STARTED,
            actual_start_date=None,
            actual_end_date=None,
            display_order=0,
        )
        defaults.update(kwargs)
        return ScheduleItem(**defaults)

    def test_not_started_is_not_delayed_on_the_planned_end_date(self):
        """開始の遅れの影響を避けるため、予定開始日=予定終了日の単日タスクで終了日単体の
        境界を検証する。"""
        item = self._item(
            planned_start_date=dt.date(2026, 11, 20), planned_end_date=dt.date(2026, 11, 20)
        )
        assert schedule_service.compute_delay_kind(item, dt.date(2026, 11, 20)) is None

    def test_not_started_has_end_delay_the_day_after_the_planned_end_date(self):
        item = self._item(
            planned_start_date=dt.date(2026, 11, 20), planned_end_date=dt.date(2026, 11, 20)
        )
        assert (
            schedule_service.compute_delay_kind(item, dt.date(2026, 11, 21))
            == schedule_service.ScheduleDelayKind.END_DELAY
        )

    def test_not_started_is_not_delayed_on_the_planned_start_date(self):
        item = self._item(planned_end_date=dt.date(2026, 12, 31))
        assert schedule_service.compute_delay_kind(item, dt.date(2026, 11, 10)) is None

    def test_not_started_has_start_delay_the_day_after_the_planned_start_date(self):
        item = self._item(planned_end_date=dt.date(2026, 12, 31))
        assert (
            schedule_service.compute_delay_kind(item, dt.date(2026, 11, 11))
            == schedule_service.ScheduleDelayKind.START_DELAY
        )

    def test_end_delay_takes_priority_over_start_delay(self):
        """予定終了日も過ぎている場合はEND_DELAYを優先する（本書14章補足4）。"""
        item = self._item()
        assert (
            schedule_service.compute_delay_kind(item, dt.date(2026, 12, 1))
            == schedule_service.ScheduleDelayKind.END_DELAY
        )

    def test_in_progress_is_not_delayed_on_the_planned_end_date(self):
        item = self._item(
            status=ScheduleItemStatus.IN_PROGRESS, actual_start_date=dt.date(2026, 11, 10)
        )
        assert schedule_service.compute_delay_kind(item, dt.date(2026, 11, 20)) is None

    def test_in_progress_has_end_delay_the_day_after_the_planned_end_date(self):
        item = self._item(
            status=ScheduleItemStatus.IN_PROGRESS, actual_start_date=dt.date(2026, 11, 10)
        )
        assert (
            schedule_service.compute_delay_kind(item, dt.date(2026, 11, 21))
            == schedule_service.ScheduleDelayKind.END_DELAY
        )

    def test_in_progress_never_has_start_delay(self):
        """進行中の行は既に着手済みのため開始の遅れは対象外（13.2は未着手のみ）。"""
        item = self._item(
            status=ScheduleItemStatus.IN_PROGRESS, actual_start_date=dt.date(2026, 11, 15)
        )
        assert schedule_service.compute_delay_kind(item, dt.date(2026, 11, 15)) is None

    def test_done_item_is_never_delayed(self):
        item = self._item(
            status=ScheduleItemStatus.DONE,
            actual_start_date=dt.date(2026, 11, 10),
            actual_end_date=dt.date(2026, 11, 25),
        )
        assert schedule_service.compute_delay_kind(item, dt.date(2026, 12, 1)) is None

    def test_cancelled_item_is_never_delayed(self):
        item = self._item(status=ScheduleItemStatus.CANCELLED)
        assert schedule_service.compute_delay_kind(item, dt.date(2026, 12, 1)) is None
