"""振り返りセクション（テーマ別・週またぎ累積）のモデル（資格試験・読書の日次報告を
関連テーマごとに体系化し、理解の振り返りに使う。仕様書・設計書への反映は別途行う）。

RecapEntry: 分類対象とした1件の報告（資格試験の日記・読書の想起記録）への参照。報告本文は
持たず、振り返りの生成時に元の報告を読み直す（利用者が後から修正した内容を反映するため）。
RecapTheme: goal単位のテーマと、その累積本文。テーマ名は同一goal内で一意。
RecapThemeLink: テーマと報告の対応（1報告は複数テーマに属しうる）。
"""

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.enums import RecapSourceKind
from app.models.base import Base, CreatedAtMixin, TimestampMixin


class RecapEntry(CreatedAtMixin, Base):
    __tablename__ = "recap_entry"
    __table_args__ = (
        UniqueConstraint("source_kind", "source_id", name="uq_recap_entry_source"),
        Index("ix_recap_entry_goal_id", "goal_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goal.id", ondelete="CASCADE"), nullable=False)
    source_kind: Mapped[RecapSourceKind] = mapped_column(
        Enum(RecapSourceKind, native_enum=False, validate_strings=True), nullable=False
    )
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    classified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RecapTheme(TimestampMixin, Base):
    __tablename__ = "recap_theme"
    __table_args__ = (UniqueConstraint("goal_id", "name", name="uq_recap_theme_goal_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goal.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")


class RecapThemeLink(Base):
    __tablename__ = "recap_theme_link"
    __table_args__ = (
        UniqueConstraint("theme_id", "entry_id", name="uq_recap_theme_link_pair"),
        Index("ix_recap_theme_link_entry_id", "entry_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theme_id: Mapped[int] = mapped_column(
        ForeignKey("recap_theme.id", ondelete="CASCADE"), nullable=False
    )
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("recap_entry.id", ondelete="CASCADE"), nullable=False
    )
