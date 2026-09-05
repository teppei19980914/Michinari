"""記録系モデル（設計書 データ構造編 5.4）。

daily_record は日付単位で一意（目標単位ではない）。確定状態はカテゴリ（EXAM/READING/WORK）
ごとに独立して持つ（資格勉強を確定しても読書・仕事は引き続き入力・確定できる、仕様変更
2026-09-05）。不変性（確定後の更新拒否）はサービス層のガードとして実装し、ここでは
データ構造のみを定義する。
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
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

from app.constants.enums import AiPurpose, ChatRole, ExamResultType, RecordState
from app.models.base import Base, CreatedAtMixin, TimestampMixin, utcnow

if TYPE_CHECKING:  # pragma: no cover (型チェック専用、実行時には到達しない)
    from app.models.book import Book
    from app.models.goal import ExamSubject, Goal
    from app.models.material import Material
    from app.models.work import WorkAssignment


class DailyRecord(CreatedAtMixin, Base):
    """日次記録。1日1レコード（複数目標が同時進行しても分割しない）。

    確定状態（*_record_state/*_reported_at）はカテゴリ別に3組持つ。NULLはそのカテゴリを
    その日一度も操作していないことを表す（登録・確定のいずれの対象にもなっていない）。
    3カテゴリ横断の単一状態が必要な箇所（カレンダー・ダッシュボード等）は
    record_service.aggregate_record_state で都度算出し、列としては保持しない。
    """

    __tablename__ = "daily_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    exam_record_state: Mapped[RecordState | None] = mapped_column(
        Enum(RecordState, native_enum=False, validate_strings=True), nullable=True
    )
    exam_reported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reading_record_state: Mapped[RecordState | None] = mapped_column(
        Enum(RecordState, native_enum=False, validate_strings=True), nullable=True
    )
    reading_reported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    work_record_state: Mapped[RecordState | None] = mapped_column(
        Enum(RecordState, native_enum=False, validate_strings=True), nullable=True
    )
    work_reported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    study_logs: Mapped[list["StudyLog"]] = relationship(
        back_populates="daily_record", cascade="all, delete-orphan"
    )
    reading_logs: Mapped[list["ReadingLog"]] = relationship(
        back_populates="daily_record", cascade="all, delete-orphan"
    )
    work_logs: Mapped[list["WorkLog"]] = relationship(
        back_populates="daily_record", cascade="all, delete-orphan"
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="daily_record", cascade="all, delete-orphan"
    )
    comments: Mapped[list["RecordComment"]] = relationship(
        back_populates="daily_record", cascade="all, delete-orphan"
    )
    diary_entries: Mapped[list["DailyGoalDiary"]] = relationship(
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


class ReadingLog(CreatedAtMixin, Base):
    """読書記録。study_logの読書版（定量実績ではなく想起した内容を自由記述で保持する）。"""

    __tablename__ = "reading_log"
    __table_args__ = (
        UniqueConstraint("book_id", "daily_record_id", name="uq_reading_log_book_record"),
        Index("ix_reading_log_daily_record_id", "daily_record_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    daily_record_id: Mapped[int] = mapped_column(
        ForeignKey("daily_record.id", ondelete="CASCADE"), nullable=False
    )
    book_id: Mapped[int] = mapped_column(ForeignKey("book.id"), nullable=False)
    recall_body: Mapped[str] = mapped_column(Text, nullable=False)
    pages_read: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_page: Mapped[int | None] = mapped_column(Integer, nullable=True)

    daily_record: Mapped["DailyRecord"] = relationship(back_populates="reading_logs")
    book: Mapped["Book"] = relationship(back_populates="reading_logs")


class WorkLog(CreatedAtMixin, Base):
    """業務記録。study_logの仕事版（定量実績ではなく当日の業務内容を自由記述1本で保持する。
    人間関係・成果・学び等をタグ分けした個別列は持たない。要件定義書6.11本文）。
    """

    __tablename__ = "work_log"
    __table_args__ = (
        UniqueConstraint(
            "work_assignment_id", "daily_record_id", name="uq_work_log_assignment_record"
        ),
        Index("ix_work_log_daily_record_id", "daily_record_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    daily_record_id: Mapped[int] = mapped_column(
        ForeignKey("daily_record.id", ondelete="CASCADE"), nullable=False
    )
    work_assignment_id: Mapped[int] = mapped_column(
        ForeignKey("work_assignment.id"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    daily_record: Mapped["DailyRecord"] = relationship(back_populates="work_logs")
    work_assignment: Mapped["WorkAssignment"] = relationship(back_populates="work_logs")


class ChatMessage(CreatedAtMixin, Base):
    """AI対話。文脈維持は sequence 順の全文注入で行う（ロジック・プロンプト編 16.3.1）。

    purpose は同一日次記録に複数のAI用途（資格試験のDAILY_FEEDBACK、読書のDAILY_FEEDBACK_
    READING）が混在しうるようになったため追加した（Phase16）。対話履歴（{{conversation_
    history}}）への注入時はpurposeで絞り込み、用途間の文脈混入を防ぐ。sequenceは日次記録
    全体で共有する採番とし、表示上の時系列順序は用途を問わず一貫させる。
    """

    __tablename__ = "chat_message"
    __table_args__ = (Index("ix_chat_message_record_sequence", "daily_record_id", "sequence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    daily_record_id: Mapped[int] = mapped_column(
        ForeignKey("daily_record.id", ondelete="CASCADE"), nullable=False
    )
    purpose: Mapped[AiPurpose] = mapped_column(
        Enum(AiPurpose, native_enum=False, validate_strings=True),
        nullable=False,
        default=AiPurpose.DAILY_FEEDBACK,
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


class DailyGoalDiary(CreatedAtMixin, Base):
    """日記（目標別）。1日1レコードの daily_record に対し、目標ごとに0〜1件持つ。

    goal_id は歴史データ移行時の安全弁としてNULLを許容する（複数目標にまたがり
    帰属先を機械的に特定できなかった日記を失わずに残すため。設計書ロジック・
    プロンプト編 未決事項L-04）。
    """

    __tablename__ = "daily_goal_diary"
    __table_args__ = (
        UniqueConstraint("daily_record_id", "goal_id", name="uq_daily_goal_diary_record_goal"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    daily_record_id: Mapped[int] = mapped_column(
        ForeignKey("daily_record.id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[int | None] = mapped_column(
        ForeignKey("goal.id", ondelete="CASCADE"), nullable=True
    )
    diary_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    diary_learned: Mapped[str | None] = mapped_column(Text, nullable=True)

    daily_record: Mapped["DailyRecord"] = relationship(back_populates="diary_entries")
    goal: Mapped["Goal | None"] = relationship(back_populates="diary_entries")


class WeeklySummary(Base):
    """週次要約。goal_id + week_start_date + is_anonymized で一意。

    is_anonymized列は設計書データ構造編7.3「匿名化版の週次要約...は、それぞれ別レコードとして
    保持する。元の版は削除しない」を満たすために追加した（同5.4の初版テーブル定義には
    無かったが、5.4はエクスポート機能着手前の定義であり7.3の要件を反映していなかったための
    後発追加。goal_retrospectiveは初版からis_anonymizedを持ち別レコードを許容しており、
    本テーブルもそれに揃える。実装フェーズ分割計画書Phase10）。
    """

    __tablename__ = "weekly_summary"
    __table_args__ = (
        UniqueConstraint(
            "goal_id", "week_start_date", "is_anonymized", name="uq_weekly_summary_goal_week"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goal.id", ondelete="CASCADE"), nullable=False)
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    week_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    summary_body: Mapped[str] = mapped_column(Text, nullable=False)
    is_anonymized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    goal: Mapped["Goal"] = relationship(back_populates="weekly_summaries")


class DailyMessage(Base):
    """今日の一言。目標ごとに独立して生成する（1日1目標につき1件、複数目標が同時進行
    していても他目標の情報を混ぜない。未決事項L-04関連）。ACTIVEな目標が1件も無い日は
    goal_id=NULLの1件のみ生成する。goal_id=NULLの行は、目標別生成に変更する前（過去）の
    目標横断メッセージとしても残りうる。
    """

    __tablename__ = "daily_message"
    __table_args__ = (
        UniqueConstraint("target_date", "goal_id", name="uq_daily_message_date_goal"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    goal_id: Mapped[int | None] = mapped_column(
        ForeignKey("goal.id", ondelete="CASCADE"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    goal: Mapped["Goal | None"] = relationship(back_populates="daily_messages")


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
