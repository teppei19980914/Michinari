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
from app.constants.enums import GoalStatus, ScheduleItemStatus
from app.models.schedule import ScheduleCell, ScheduleColumn, ScheduleItem, ScheduleItemHistory
from app.schemas.schedule import (
    ScheduleCellInput,
    ScheduleColumnInput,
    ScheduleItemInput,
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
