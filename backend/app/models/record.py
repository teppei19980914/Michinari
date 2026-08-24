"""記録系モデル（設計書 データ構造編 5.4）。

daily_record は日付単位で一意（目標単位ではない）。不変性（確定後の更新拒否）は
サービス層のガードとして実装し、ここではデータ構造のみを定義する。
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.enums import ChatRole, ExamResultType, RecordState
from app.models.base import Base, CreatedAtMixin, TimestampMixin, utcnow

if TYPE_CHECKING:  # pragma: no cover (型チェック専用、実行時には到達しない)
    from app.models.goal import ExamSubject, Goal
    from app.models.material import Material


class DailyRecord(CreatedAtMixin, Base):
    """日次記録。1日1レコード（複数目標が同時進行しても分割しない）。"""

    __tablename__ = "daily_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    record_state: Mapped[RecordState] = mapped_column(
        Enum(RecordState, native_enum=False, validate_strings=True), nullable=False
    )
    diary_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    diary_learned: Mapped[str | None] = mapped_column(Text, nullable=True)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    study_logs: Mapped[list["StudyLog"]] = relationship(
        back_populates="daily_record", cascade="all, delete-orphan"
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="daily_record", cascade="all, delete-orphan"
    )
    comments: Mapped[list["RecordComment"]] = relationship(
        back_populates="daily_record", cascade="all, delete-orphan"
    )


class StudyLog(CreatedAtMixin, Base):
    """学習実績。minutes_spent が NULL/0 の行は実効速度算出から除外する（サービス層）。"""

    __tablename__ = "study_log"
    __table_args__ = (
        UniqueConstraint("material_id", "daily_record_id", name="uq_study_log_material_record"),
        Index("ix_study_log_material_cycle", "material_id", "cycle_number"),
        Index("ix_study_log_daily_record_id", "daily_record_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    daily_record_id: Mapped[int] = mapped_column(
        ForeignKey("daily_record.id", ondelete="CASCADE"), nullable=False
    )
    material_id: Mapped[int] = mapped_column(ForeignKey("material.id"), nullable=False)
    minutes_spent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount_completed: Mapped[float] = mapped_column(Float, nullable=False)
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    quality_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    daily_record: Mapped["DailyRecord"] = relationship(back_populates="study_logs")
    material: Mapped["Material"] = relationship(back_populates="study_logs")


class ChatMessage(CreatedAtMixin, Base):
    """AI対話。文脈維持は sequence 順の全文注入で行う（ロジック・プロンプト編 16.3.1）。"""

    __tablename__ = "chat_message"
    __table_args__ = (Index("ix_chat_message_record_sequence", "daily_record_id", "sequence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    daily_record_id: Mapped[int] = mapped_column(
        ForeignKey("daily_record.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[ChatRole] = mapped_column(
        Enum(ChatRole, native_enum=False, validate_strings=True), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    daily_record: Mapped["DailyRecord"] = relationship(back_populates="chat_messages")


class RecordComment(TimestampMixin, Base):
    """コメント。日次報告本体の不変性を保ちつつ後日の補足を可能にする。"""

    __tablename__ = "record_comment"
    __table_args__ = (Index("ix_record_comment_daily_record_id", "daily_record_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    daily_record_id: Mapped[int] = mapped_column(
        ForeignKey("daily_record.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    daily_record: Mapped["DailyRecord"] = relationship(back_populates="comments")


class WeeklySummary(Base):
    """週次要約。goal_id + week_start_date で一意。"""

    __tablename__ = "weekly_summary"
    __table_args__ = (
        UniqueConstraint("goal_id", "week_start_date", name="uq_weekly_summary_goal_week"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goal.id", ondelete="CASCADE"), nullable=False)
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    week_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    summary_body: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    goal: Mapped["Goal"] = relationship(back_populates="weekly_summaries")


class DailyMessage(Base):
    """今日の一言。"""

    __tablename__ = "daily_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ExamResult(CreatedAtMixin, Base):
    """受験結果。科目に対して1対1。"""

    __tablename__ = "exam_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("exam_subject.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    taken_date: Mapped[date] = mapped_column(Date, nullable=False)
    result: Mapped[ExamResultType] = mapped_column(
        Enum(ExamResultType, native_enum=False, validate_strings=True), nullable=False
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluation: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    subject: Mapped["ExamSubject"] = relationship(back_populates="exam_result")
