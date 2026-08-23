"""リソーススロット系モデル（設計書 データ構造編 5.2）。"""

from datetime import time

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.enums import Environment
from app.models.base import Base, TimestampMixin


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


class ResourceSlotWeekday(Base):
    """スロットの適用曜日。0=月曜〜6=日曜。"""

    __tablename__ = "resource_slot_weekday"

    slot_id: Mapped[int] = mapped_column(
        ForeignKey("resource_slot.id", ondelete="CASCADE"), primary_key=True
    )
    weekday: Mapped[int] = mapped_column(Integer, primary_key=True)

    slot: Mapped["ResourceSlot"] = relationship(back_populates="weekdays")
