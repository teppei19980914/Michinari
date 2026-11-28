"""ガントチャート公開API・閲覧APIのリクエスト・レスポンススキーマ（単位2）。

文字数上限はpydantic層で検証する（D-20）。値は`app/config.py`の設定（publish_server側
設定＝環境変数、D-20根拠）を使う。publish_serverは`backend/app/*`をimportしない
（D-23・D-24）ため、ステータス・列種別の値はローカル側のEnum定義を検証せずそのまま
文字列として受け取る（公開ビューアは閲覧専用で表示できればよく、意味の検証はローカル側の
責務、D-06）。
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings

_MAX_FIELD_CHARS = get_settings().max_field_chars


class GanttItemIn(BaseModel):
    #: ローカル側`schedule_item.id`。`cells`から参照するための安定キー（D-23）。
    local_item_id: int
    title: str = Field(max_length=_MAX_FIELD_CHARS)
    description: str | None = Field(default=None, max_length=_MAX_FIELD_CHARS)
    planned_start_date: date
    planned_end_date: date
    status: str = Field(max_length=_MAX_FIELD_CHARS)
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    display_order: int


class GanttColumnIn(BaseModel):
    #: ローカル側`schedule_column.id`。`cells`から参照するための安定キー（D-23）。
    local_column_id: int
    name: str = Field(max_length=_MAX_FIELD_CHARS)
    column_type: str = Field(max_length=_MAX_FIELD_CHARS)
    display_order: int


class GanttCellIn(BaseModel):
    local_item_id: int
    local_column_id: int
    value: str = Field(max_length=_MAX_FIELD_CHARS)


class GanttSnapshotUploadRequest(BaseModel):
    goal_name: str = Field(max_length=_MAX_FIELD_CHARS)
    items: list[GanttItemIn]
    columns: list[GanttColumnIn]
    cells: list[GanttCellIn]


class GanttSnapshotListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    local_goal_id: int
    goal_name: str
    updated_at: datetime


class GanttSnapshotDetail(BaseModel):
    id: int
    local_goal_id: int
    goal_name: str
    items: list[GanttItemIn]
    columns: list[GanttColumnIn]
    cells: list[GanttCellIn]
    updated_at: datetime
