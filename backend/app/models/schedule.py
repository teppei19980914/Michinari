"""スケジュール・ガントチャート機能のモデル
（開発Todo_スケジュール・ガントチャート_v1.1 第7章、単位2）。

GoalSchedule: 目標ごとに1行。固定の行数・列数と楽観ロック用のrevisionを持つ（D-07・D-24）。
ScheduleItem: 作業項目（既定7列、D-08）。
ScheduleColumn: 追加列の定義（テキスト型のみ、MVP。D-12）。
ScheduleCell: 追加列の値（schedule_item×schedule_columnの複合PK。値が空になった場合は
行ごと削除する想定のため、valueはNOT NULLのまま=空文字列を保存しない、本書7.1）。
ScheduleItemHistory: 状況・実績日の更新履歴（更新元を問わず記録、D-39）。

ScheduleCell・ScheduleItemHistoryは参照用のFK列のみ持ち、VocabAnswerLogと同じく
ORM上のrelationshipは持たない（DB側のON DELETE CASCADEに委ねる）。Goalからの
schedule・schedule_items・schedule_columnsの3つのrelationshipは、本書7.3の指示により
明示的にcascade="all, delete-orphan"で追加する（goal.py側）。
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.enums import ScheduleColumnType, ScheduleItemStatus, ScheduleUpdateSource
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:  # pragma: no cover (型チェック専用、実行時には到達しない)
    from app.models.goal import Goal


class GoalSchedule(TimestampMixin, Base):
    """目標ごとのスケジュール設定（本書7.1）。行が存在しない目標は、固定は作業項目列のみ・
    revisionは0の既定値として扱う（サービス層で解決、行自体は保存時に遅延作成する）。
    """

    __tablename__ = "goal_schedule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(
        ForeignKey("goal.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: 見出し行は常に固定するため、ここで数えるのはデータ行（本書7.1）。
    frozen_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: 既定値1（作業項目列、D-24）。
    frozen_column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    goal: Mapped["Goal"] = relationship(back_populates="schedule")


class ScheduleItem(TimestampMixin, Base):
    """作業項目（本書7.1の既定7列）。"""

    __tablename__ = "schedule_item"
    __table_args__ = (Index("ix_schedule_item_goal_id", "goal_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goal.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    planned_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    planned_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ScheduleItemStatus] = mapped_column(
        Enum(ScheduleItemStatus, native_enum=False, validate_strings=True),
        nullable=False,
        default=ScheduleItemStatus.NOT_STARTED,
    )
    actual_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    goal: Mapped["Goal"] = relationship(back_populates="schedule_items")


class ScheduleColumn(TimestampMixin, Base):
    """追加列の定義（本書7.1、D-12）。"""

    __tablename__ = "schedule_column"
    __table_args__ = (Index("ix_schedule_column_goal_id", "goal_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goal.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    column_type: Mapped[ScheduleColumnType] = mapped_column(
        Enum(ScheduleColumnType, native_enum=False, validate_strings=True),
        nullable=False,
        default=ScheduleColumnType.TEXT,
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    goal: Mapped["Goal"] = relationship(back_populates="schedule_columns")


class ScheduleCell(Base):
    """追加列の値（本書7.1）。空になった場合はサービス層が行ごと削除する。"""

    __tablename__ = "schedule_cell"

    schedule_item_id: Mapped[int] = mapped_column(
        ForeignKey("schedule_item.id", ondelete="CASCADE"), primary_key=True
    )
    schedule_column_id: Mapped[int] = mapped_column(
        ForeignKey("schedule_column.id", ondelete="CASCADE"), primary_key=True
    )
    value: Mapped[str] = mapped_column(Text, nullable=False)


class ScheduleItemHistory(Base):
    """状況・実績日の更新履歴（本書7.1、D-39）。行の作成時と、状況・実績開始日・実績終了日の
    いずれかが変わったときにだけサービス層が1行追加する。
    """

    __tablename__ = "schedule_item_history"
    __table_args__ = (Index("ix_schedule_item_history_schedule_item_id", "schedule_item_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_item_id: Mapped[int] = mapped_column(
        ForeignKey("schedule_item.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[ScheduleUpdateSource] = mapped_column(
        Enum(ScheduleUpdateSource, native_enum=False, validate_strings=True), nullable=False
    )
    #: 日次報告・SC-07は報告対象日、スケジュール画面ではNULL（本書7.1）。
    record_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[ScheduleItemStatus] = mapped_column(
        Enum(ScheduleItemStatus, native_enum=False, validate_strings=True), nullable=False
    )
    actual_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
