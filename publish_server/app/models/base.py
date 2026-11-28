"""SQLAlchemy 宣言的ベースと共通Mixin（publish_server独自。backendとは別実装、D-24と同じ方針）。"""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """DBから読み出した時刻をUTC awareとして扱う。

    SQLite・PostgreSQLいずれも、本プロジェクトで使う`DateTime`列（`timezone=True`を
    指定していない）はコミット後に再読み込みすると`tzinfo`が失われたnaiveな値を返す
    （`utcnow()`はaware）。素朴に比較すると`TypeError: can't compare offset-naive and
    offset-aware datetimes`になるため、`utcnow()`と比較する直前に必ずこれを通す
    （保存する値は常にutcnow()由来＝UTCであることが前提）。
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


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
