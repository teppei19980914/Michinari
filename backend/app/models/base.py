"""SQLAlchemy 宣言的ベースと共通Mixin。"""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class CreatedAtMixin:
    """created_at のみを持つテーブル用（技術選定書: DATETIME は UTC 保存）。"""

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class UpdatedAtMixin:
    """updated_at のみを持つテーブル用（app_setting、prompt_template）。"""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class TimestampMixin(CreatedAtMixin, UpdatedAtMixin):
    """created_at / updated_at の両方を持つテーブル用。"""
