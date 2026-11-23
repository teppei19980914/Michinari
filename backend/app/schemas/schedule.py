"""スケジュール・ガントチャート機能のリクエスト/レスポンススキーマ
（開発Todo_スケジュール・ガントチャート_v1.1 第7章・第8章、単位2）。
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, model_validator

from app.constants.enums import ScheduleItemStatus


class ScheduleCellInput(BaseModel):
    """追加列1件分の値（PUT /goals/{goal_id}/schedule）。column_idかcolumn_temp_keyの
    どちらか一方のみを指定する（新規列はcolumn_temp_keyで対応付ける、本書8.1）。
    """

    column_id: int | None = None
    column_temp_key: str | None = None
    value: str = ""

    @model_validator(mode="after")
    def _check_exactly_one_column_reference(self) -> ScheduleCellInput:
        if (self.column_id is None) == (self.column_temp_key is None):
            raise ValueError("Exactly one of column_id or column_temp_key must be set")
        return self


class ScheduleItemInput(BaseModel):
    """作業項目1行分（PUT /goals/{goal_id}/schedule）。idが無ければ新規作成する。"""

    id: int | None = None
    title: str = Field(min_length=1)
    description: str | None = None
    planned_start_date: dt.date
    planned_end_date: dt.date
    status: ScheduleItemStatus = ScheduleItemStatus.NOT_STARTED
    actual_start_date: dt.date | None = None
    actual_end_date: dt.date | None = None
    cells: list[ScheduleCellInput] = Field(default_factory=list)


class ScheduleColumnInput(BaseModel):
    """追加列1件分の定義（PUT /goals/{goal_id}/schedule）。idかtemp_keyのどちらか一方のみ
    を指定する（既存列はid、新規列はtemp_key、本書8.1）。
    """

    id: int | None = None
    temp_key: str | None = None
    name: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_exactly_one_reference(self) -> ScheduleColumnInput:
        if (self.id is None) == (self.temp_key is None):
            raise ValueError("Exactly one of id or temp_key must be set")
        return self


class ScheduleSaveRequest(BaseModel):
    """PUT /goals/{goal_id}/schedule のリクエスト本体（本書8.1）。"""

    revision: int = Field(ge=0)
    columns: list[ScheduleColumnInput] = Field(default_factory=list)
    items: list[ScheduleItemInput] = Field(default_factory=list)


class ScheduleCellRead(BaseModel):
    column_id: int
    value: str


class ScheduleItemRead(BaseModel):
    id: int
    title: str
    description: str | None
    planned_start_date: dt.date
    planned_end_date: dt.date
    status: ScheduleItemStatus
    actual_start_date: dt.date | None
    actual_end_date: dt.date | None
    display_order: int
    cells: list[ScheduleCellRead]


class ScheduleColumnRead(BaseModel):
    id: int
    name: str
    display_order: int


class ScheduleRead(BaseModel):
    """GET /goals/{goal_id}/schedule の応答（本書8章）。

    max_items・max_custom_columns・gantt_day_width_min_rem・gantt_day_width_max_rem は
    画面側が必要とする内部パラメータ（app_setting、設定画面には表示しない）を読み取り専用
    フィールドとして渡す。単語帳機能の前例（VocabDeckRead.session_default_questions/
    session_max_questions、設計書データ構造編1.1改75）に倣う（単位3、開発Todo第2章食い違い2）。
    """

    revision: int
    frozen_row_count: int
    frozen_column_count: int
    today: dt.date
    max_items: int
    max_custom_columns: int
    gantt_day_width_min_rem: float
    gantt_day_width_max_rem: float
    columns: list[ScheduleColumnRead]
    items: list[ScheduleItemRead]


class ScheduleViewSettingUpdate(BaseModel):
    """PUT /goals/{goal_id}/schedule/view-setting のリクエスト（本書8章、D-24・D-25）。

    revisionは変えない（固定の設定の変更は版数に数えない、本書7.1）。見出し行は常に固定
    するため、ここで数えるのはデータ行・既定7列＋追加列（本書7.1・D-24）。
    """

    frozen_row_count: int = Field(ge=0)
    frozen_column_count: int = Field(ge=0)


class ScheduleViewSettingRead(BaseModel):
    frozen_row_count: int
    frozen_column_count: int
