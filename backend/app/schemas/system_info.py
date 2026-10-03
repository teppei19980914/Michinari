"""システム情報のレスポンススキーマ（仕様書6.14 SC-15）。読み取り専用のため更新スキーマはない。"""

from __future__ import annotations

from pydantic import BaseModel


class LibraryInfoRead(BaseModel):
    name: str
    version: str


class SystemInfoRead(BaseModel):
    app_version: str
    python_version: str
    built_at: str | None
    backend_libraries: list[LibraryInfoRead]
    frontend_libraries: list[LibraryInfoRead]
