"""振り返り（テーマ累積）のAPIスキーマ（仕様書6.1.3、データ構造編5.6）。"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.constants.enums import RecapSourceKind
from app.constants.recap import RECAP_THEME_NAME_MAX_LENGTH


class RecapThemeSummaryRead(BaseModel):
    id: int
    name: str
    entry_count: int
    updated_at: dt.datetime


class RecapThemeEntryRead(BaseModel):
    source_kind: RecapSourceKind
    record_date: dt.date
    text: str


class RecapThemeDetailRead(BaseModel):
    id: int
    goal_id: int
    name: str
    body: str
    updated_at: dt.datetime
    entries: list[RecapThemeEntryRead]


class RecapThemeRename(BaseModel):
    name: str = Field(min_length=1, max_length=RECAP_THEME_NAME_MAX_LENGTH)


class RecapThemeMerge(BaseModel):
    target_theme_id: int = Field(gt=0)
