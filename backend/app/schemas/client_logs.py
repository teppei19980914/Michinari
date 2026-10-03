"""フロントエンドのエラー報告スキーマ（Phase40 診断ログ出力・トレース強化）。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

#: 1回の送信で受け付ける文字数の上限。巨大なペイロードによるログ肥大化・簡易的な
#: サービス妨害を防ぐ（脅威モデル: D対策）。超過はFastAPIの標準検証で自動的に400へ落ちる。
_MAX_TEXT_LENGTH = 4000
_MAX_PATH_LENGTH = 500


class ClientLogRequest(BaseModel):
    level: Literal["error"]
    message: str = Field(max_length=_MAX_TEXT_LENGTH)
    stack: str | None = Field(default=None, max_length=_MAX_TEXT_LENGTH)
    component_stack: str | None = Field(default=None, max_length=_MAX_TEXT_LENGTH)
    path: str = Field(max_length=_MAX_PATH_LENGTH)
