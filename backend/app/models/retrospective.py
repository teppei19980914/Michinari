"""総括レポートモデル（設計書 データ構造編 5.4）。

再生成を許容するため goal に対して複数レコードを持てる。匿名化版は別レコード。
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow

if TYPE_CHECKING:  # pragma: no cover (型チェック専用、実行時には到達しない)
    from app.models.goal import Goal


class GoalRetrospective(Base):
    """目標の総括レポート（合否要因分析・ナレッジエクスポートの元データ）。"""

    __tablename__ = "goal_retrospective"
    __table_args__ = (Index("ix_goal_retrospective_goal_generated", "goal_id", "generated_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goal.id", ondelete="CASCADE"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_anonymized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    goal: Mapped["Goal"] = relationship(back_populates="retrospectives")
