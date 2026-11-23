"""schemas.schedule のモデル検証（開発Todo_スケジュール・ガントチャート_v1.1 第8.1章）。

idかtemp_key（列）・column_idかcolumn_temp_key（セル）はどちらか一方のみを要求する
（新規列は仮キーで対応付ける）。「どちらも無い」ケースはtest_schedule_service.pyの
各種テストが通常の入力経路で網羅しているため、ここでは「両方ある」異常系のみを確認する。
"""

import datetime as dt

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.schemas.schedule import ScheduleCellInput, ScheduleColumnInput, ScheduleItemInput


def test_schedule_column_input_rejects_both_id_and_temp_key():
    with pytest.raises(PydanticValidationError):
        ScheduleColumnInput(id=1, temp_key="c1", name="担当")


def test_schedule_cell_input_rejects_both_column_id_and_column_temp_key():
    with pytest.raises(PydanticValidationError):
        ScheduleCellInput(column_id=1, column_temp_key="c1", value="自分")


def test_schedule_item_input_defaults_status_to_not_started():
    item = ScheduleItemInput(
        title="第1章",
        planned_start_date=dt.date(2026, 1, 1),
        planned_end_date=dt.date(2026, 1, 5),
    )
    assert item.status.value == "NOT_STARTED"
