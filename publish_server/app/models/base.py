"""SQLAlchemy 宣言的ベースと共通Mixin（publish_server独自。backendとは別実装、D-24と同じ方針）。"""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class UpdatedAtMixin:
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class TimestampMixin(CreatedAtMixin, UpdatedAtMixin):
    pass
