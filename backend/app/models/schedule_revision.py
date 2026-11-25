"""AIによるスケジュール修正案のモデル
（開発Todo_スケジュール・ガントチャート_v1.1 第13章・13.6、単位5）。

ScheduleRevisionProposal: 修正案1件（目標ごとに未判断の修正案は常に1つ、D-65）。
ScheduleRevisionProposalItem: 修正案の行（CHANGE=変更案、WARNING=注意）。予定日の変更履歴は
このテーブルが兼ねる（schedule_item_historyは状況・実績日の履歴のまま変更しない、14章補足8）。

ScheduleRevisionProposalは状況（status）が後から変わる可変行のため、本書の他の可変テーブル
（GoalSchedule等）と同じTimestampMixinを使う（単位5開発Todo2章補足5）。
ScheduleRevisionProposalItemはdecided_at列が更新時刻の役割を兼ねるため、ScheduleCell・
ScheduleItemHistoryと同じく列挙された列のみを持つ（TimestampMixinは使わない）。
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.enums import (
    ScheduleItemStatus,
    ScheduleRevisionDecision,
    ScheduleRevisionItemKind,
    ScheduleRevisionProposalStatus,
    ScheduleRevisionTrigger,
)
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:  # pragma: no cover (型チェック専用、実行時には到達しない)
    from app.models.goal import Goal


class ScheduleRevisionProposal(TimestampMixin, Base):
    """AIによるスケジュール修正案1件（本書13.6）。"""

    __tablename__ = "schedule_revision_proposal"
    __table_args__ = (Index("ix_schedule_revision_proposal_goal_id", "goal_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goal.id", ondelete="CASCADE"), nullable=False)
    trigger: Mapped[ScheduleRevisionTrigger] = mapped_column(
        Enum(ScheduleRevisionTrigger, native_enum=False, validate_strings=True), nullable=False
    )
    #: 自動生成のきっかけとなった報告対象日（13.2の1日1回の判定に使う）。MANUALはNULL。
    record_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ScheduleRevisionProposalStatus] = mapped_column(
        Enum(ScheduleRevisionProposalStatus, native_enum=False, validate_strings=True),
        nullable=False,
        default=ScheduleRevisionProposalStatus.PENDING,
    )

    goal: Mapped["Goal"] = relationship()
    items: Mapped[list["ScheduleRevisionProposalItem"]] = relationship(
        back_populates="proposal", cascade="all, delete-orphan"
    )


class ScheduleRevisionProposalItem(Base):
    """修正案の行（本書13.6）。"""

    __tablename__ = "schedule_revision_proposal_item"
    __table_args__ = (
        Index("ix_schedule_revision_proposal_item_proposal_id", "proposal_id"),
        Index("ix_schedule_revision_proposal_item_schedule_item_id", "schedule_item_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proposal_id: Mapped[int] = mapped_column(
        ForeignKey("schedule_revision_proposal.id", ondelete="CASCADE"), nullable=False
    )
    schedule_item_id: Mapped[int] = mapped_column(
        ForeignKey("schedule_item.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[ScheduleRevisionItemKind] = mapped_column(
        Enum(ScheduleRevisionItemKind, native_enum=False, validate_strings=True), nullable=False
    )
    #: 生成時点の値（D-59の「変更前の値が現在の値と一致するか」の判定に使う）。
    before_planned_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    before_planned_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    before_status: Mapped[ScheduleItemStatus] = mapped_column(
        Enum(ScheduleItemStatus, native_enum=False, validate_strings=True), nullable=False
    )
    #: WARNINGではNULL。
    proposed_planned_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    proposed_planned_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    decision: Mapped[ScheduleRevisionDecision] = mapped_column(
        Enum(ScheduleRevisionDecision, native_enum=False, validate_strings=True),
        nullable=False,
        default=ScheduleRevisionDecision.PENDING,
    )
    #: 承認時に実際に反映した値（利用者が修正した場合はその値）。WARNING・未承認ではNULL。
    applied_planned_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    applied_planned_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    proposal: Mapped["ScheduleRevisionProposal"] = relationship(back_populates="items")
