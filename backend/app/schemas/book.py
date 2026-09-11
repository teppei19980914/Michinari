"""書籍のリクエスト/レスポンススキーマ（データ構造編5.3、仕様書6.2）。

BookRead の remaining_days・last_reading_date・current_streak・current_page・
progress_rate はDBに保存しない派生値（CLAUDE.md）であるため、ORMからの自動変換
(from_attributes)は使わず、API層がbook_serviceで算出した値を明示的に渡して構築する
（schemas/material.pyのMaterialReadと同じ方針）。
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


class BookCreate(BaseModel):
    """総ページ数は必須（要件定義書R-70、仕様変更2026-09-11）。進捗率（21.2）を常に
    算出できるようにするためであり、未入力を許した旧仕様は廃止した。"""

    title: str = Field(min_length=1)
    author: str | None = None
    total_pages: int = Field(ge=1)
    start_date: dt.date
    due_date: dt.date


class BookUpdate(BaseModel):
    """total_pages は author と異なり「明示的なクリア」を持たない（必須化により未設定と
    いう状態が存在しなくなったため）。よって None ＝未指定であり、番兵は author のみに使う
    （book_service.update_book のコメント参照）。"""

    title: str | None = Field(default=None, min_length=1)
    author: str | None = None
    total_pages: int | None = Field(default=None, ge=1)
    start_date: dt.date | None = None
    due_date: dt.date | None = None


class BookRead(BaseModel):
    id: int
    goal_id: int
    title: str
    author: str | None
    total_pages: int
    start_date: dt.date
    due_date: dt.date
    remaining_days: int
    last_reading_date: dt.date | None
    current_streak: int
    current_page: int | None
    progress_rate: float | None
