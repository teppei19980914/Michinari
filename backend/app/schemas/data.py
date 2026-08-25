"""データ管理（バックアップ）のレスポンススキーマ（仕様書6.12 SC-12）。"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class BackupRead(BaseModel):
    id: str
    created_at: dt.datetime
    size_bytes: int
