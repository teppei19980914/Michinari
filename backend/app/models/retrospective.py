"""総括レポート／読了レポート／定期報告モデル（設計書 データ構造編 5.4
「goal_retrospective（総括レポート／読了レポート／定期報告）」）。

EXAM（総括レポート）・READING（読了レポート）では、再生成を許容するため goal に対して
複数レコードを持てる（period_type・period_keyは常にNULL）。匿名化版は別レコード。

WORK（月次報告／半期評価）では新規テーブルを設けず本テーブルを流用するが、EXAM/READING
と異なり「1期間（period_type・period_key）につき1行のみ」を保つ（is_anonymized=falseの
行に限る）。再生成・利用者編集はいずれも既存行への上書きとして扱う（サービス層でupsert、
Phase21以降で実装）。(goal_id, period_type, period_key, is_anonymized) にUNIQUE制約を
持たせるが、EXAM/READINGの行はperiod_type・period_keyが共にNULLであり、標準SQLの
NULL比較（NULL同士は等しいとみなされない）によりこの制約の対象外となる（従来どおり
無制限に再生成できる。データ構造編5.4「制約」参照）。
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.enums import RetrospectivePeriodType
from app.models.base import Base, utcnow

if TYPE_CHECKING:  # pragma: no cover (型チェック専用、実行時には到達しない)
    from app.models.goal import Goal


class GoalRetrospective(Base):
    """目標の総括レポート／読了レポート／月次報告／半期評価（ナレッジエクスポートの元データ）。

    period_type以下の9列（period_type・period_key・target_goal_text・business_summary・
    achievement_score・achievement_reflection・next_goal_text・report_notes・edited_at）は
    WORKの月次報告・半期評価でのみ使用し、EXAM/READINGでは常にNULLのまま用いない。
    """

    __tablename__ = "goal_retrospective"
    __table_args__ = (
        Index("ix_goal_retrospective_goal_generated", "goal_id", "generated_at"),
        UniqueConstraint(
            "goal_id",
            "period_type",
            "period_key",
            "is_anonymized",
            name="uq_goal_retrospective_goal_period_anonymized",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goal.id", ondelete="CASCADE"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_anonymized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    period_type: Mapped[RetrospectivePeriodType | None] = mapped_column(
        Enum(RetrospectivePeriodType, native_enum=False, validate_strings=True),
        nullable=True,
    )
    period_key: Mapped[str | None] = mapped_column(String, nullable=True)
    target_goal_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    achievement_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    achievement_reflection: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_goal_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    goal: Mapped["Goal"] = relationship(back_populates="retrospectives")
