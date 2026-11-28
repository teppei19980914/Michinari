"""共有リンク（データモデル3章 share_link）。

D-11：MVP範囲外（API・画面は実装しない）。テーブル設計のみ単位1で先行させる
（開発Todo_Web公開_v1.0 9章「MVPの対象外」）。将来実装するまで、このテーブルへの
読み書きを行うサービス・APIは存在しない。
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin


class ShareTargetType(enum.StrEnum):
    GANTT = "GANTT"
    VOCAB = "VOCAB"
    QUIZ = "QUIZ"


class SharePermission(enum.StrEnum):
    VIEW = "VIEW"
    ANSWER = "ANSWER"


class ShareLink(CreatedAtMixin, Base):
    __tablename__ = "share_link"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("publish_account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[ShareTargetType] = mapped_column(
        Enum(ShareTargetType, native_enum=False, validate_strings=True), nullable=False
    )
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    permission: Mapped[SharePermission] = mapped_column(
        Enum(SharePermission, native_enum=False, validate_strings=True), nullable=False
    )
