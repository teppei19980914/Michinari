"""リソーススロット系モデル（設計書 データ構造編 5.2）。"""

from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.enums import Environment
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:  # pragma: no cover (型チェック専用、実行時には到達しない)
    from app.models.goal import Goal


class ResourceSlot(TimestampMixin, Base):
    """時間スロット。連続時間は end_time - start_time として算出し保存しない。"""

    __tablename__ = "resource_slot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    environment: Mapped[Environment] = mapped_column(
        Enum(Environment, native_enum=False, validate_strings=True), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)

    weekdays: Mapped[list["ResourceSlotWeekday"]] = relationship(
        back_populates="slot", cascade="all, delete-orphan"
    )
    allocations: Mapped[list["GoalSlotAllocation"]] = relationship(
        back_populates="slot", cascade="all, delete-orphan"
    )


class ResourceSlotWeekday(Base):
    """スロットの適用曜日。0=月曜〜6=日曜。"""

    __tablename__ = "resource_slot_weekday"

    slot_id: Mapped[int] = mapped_column(
        ForeignKey("resource_slot.id", ondelete="CASCADE"), primary_key=True
    )
    weekday: Mapped[int] = mapped_column(Integer, primary_key=True)

    slot: Mapped["ResourceSlot"] = relationship(back_populates="weekdays")


class GoalSlotAllocation(TimestampMixin, Base):
    """目標へのスロット配分（データ構造編5.2）。

    上限はスロット単位で判定する（あるスロットについて、ACTIVEな目標のminutesの合計が
    そのスロットの連続時間を超えないこと。要件定義書R-07）。category=WORKの目標は
    この合計計算・入力の対象外とする（R-74）が、category=READINGは対象に含める（R-64）。
    配分0分のスロットは行を持たない（行の非存在と minutes=0 を同義とする）。
    """

    __tablename__ = "goal_slot_allocation"

    goal_id: Mapped[int] = mapped_column(
        ForeignKey("goal.id", ondelete="CASCADE"), primary_key=True
    )
    slot_id: Mapped[int] = mapped_column(
        ForeignKey("resource_slot.id", ondelete="CASCADE"), primary_key=True
    )
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    goal: Mapped["Goal"] = relationship(back_populates="slot_allocations")
    slot: Mapped["ResourceSlot"] = relationship(back_populates="allocations")
