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
    """書籍の新規登録（仕様書6.2）。総ページ数は必須とする（要件定義書R-70、仕様変更
    2026-09-11）。進捗率（ロジック・プロンプト編21.2）を常に算出できるようにするためで
    あり、未入力を許した旧仕様は廃止した。"""

    title: str = Field(min_length=1)
    author: str | None = None
    total_pages: int = Field(ge=1)
    start_date: dt.date
    due_date: dt.date


class BookUpdate(BaseModel):
    """書籍の部分更新（仕様書6.2）。None＝未指定であり、「明示的なクリア」を持つのは
    author のみとする（total_pages は必須化によりクリアという操作自体が無くなったため、
    番兵の対象から外した。constants/sentinels.py）。"""

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
