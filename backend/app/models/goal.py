"""目標系モデル（設計書 データ構造編 5.3）。"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.enums import ExamDateType, GoalCategory, GoalStatus, PassingScoreType
from app.models.base import Base, CreatedAtMixin, TimestampMixin

if TYPE_CHECKING:  # pragma: no cover (型チェック専用、実行時には到達しない)
    from app.models.ai import AiConversation
    from app.models.book import Book
    from app.models.material import Material, MaterialSubject
    from app.models.record import ExamResult, WeeklySummary
    from app.models.retrospective import GoalRetrospective


class Goal(TimestampMixin, Base):
    """目標（試験合格または読書の完遂に向けた学習単位）。

    category（EXAM/READING）は作成後の変更を許容しない（サービス層で検証）。
    READINGの場合、exam_subject/material/load_profile/weekly_summaryは作成せず、
    resource_ratioは常に0のまま（配分プールの対象外。要件定義書R-64）とする。
    """

    __tablename__ = "goal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[GoalCategory] = mapped_column(
        Enum(GoalCategory, native_enum=False, validate_strings=True),
        nullable=False,
        default=GoalCategory.EXAM,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[GoalStatus] = mapped_column(
        Enum(GoalStatus, native_enum=False, validate_strings=True), nullable=False
    )
    resource_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    exam_subjects: Mapped[list["ExamSubject"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan"
    )
    materials: Mapped[list["Material"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan"
    )
    load_profiles: Mapped[list["LoadProfile"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan"
    )
    weekly_summaries: Mapped[list["WeeklySummary"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan"
    )
    retrospectives: Mapped[list["GoalRetrospective"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan"
    )
    ai_conversations: Mapped[list["AiConversation"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan"
    )
    book: Mapped["Book | None"] = relationship(
        back_populates="goal", cascade="all, delete-orphan", uselist=False
    )


class ExamSubject(TimestampMixin, Base):
    """試験科目。"""

    __tablename__ = "exam_subject"
    __table_args__ = (Index("ix_exam_subject_goal_id", "goal_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goal.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    exam_date_type: Mapped[ExamDateType] = mapped_column(
        Enum(ExamDateType, native_enum=False, validate_strings=True), nullable=False
    )
    exam_date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    exam_date_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    exam_date_fixed: Mapped[date | None] = mapped_column(Date, nullable=True)
    passing_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    passing_score_type: Mapped[PassingScoreType] = mapped_column(
        Enum(PassingScoreType, native_enum=False, validate_strings=True),
        nullable=False,
        default=PassingScoreType.PERCENTAGE,
    )
    passing_score_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)

    goal: Mapped["Goal"] = relationship(back_populates="exam_subjects")
    material_links: Mapped[list["MaterialSubject"]] = relationship(
        back_populates="subject", cascade="all, delete-orphan"
    )
    exam_result: Mapped["ExamResult | None"] = relationship(
        back_populates="subject", cascade="all, delete-orphan", uselist=False
    )


class LoadProfile(CreatedAtMixin, Base):
    """負荷プロファイル。未設定期間の係数は1.0（サービス層で解決）。"""

    __tablename__ = "load_profile"
    __table_args__ = (
        Index("ix_load_profile_goal_period", "goal_id", "date_from", "date_to"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goal.id", ondelete="CASCADE"), nullable=False)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    coefficient: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    goal: Mapped["Goal"] = relationship(back_populates="load_profiles")
