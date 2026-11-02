"""節目のお祝い（開発Todo_節目のお祝い_v1.0）のモデル。

GoalMilestoneAchievement: 目標が節目（連続/累計記録日数・読書の累計ページ数/読了冊数・
資格の教材1周完了/全体進捗率・仕事の記録件数/評価期間完走）に到達した事実の記録。
「いつ初めて到達したか」という一度確定したら不変の履歴であり、CLAUDE.md
「日次ノルマ・残量・現在周回の保存」禁止（毎回算出し直せる現在値の保存禁止）の対象外
（開発Todo_節目のお祝い_v1.0 §0 M2）。

celebrated_atがNULLの行は「到達済みだが未お祝い」を表し、お祝いモーダルを表示した後に
現在時刻を書き込む。既存利用者への移行時バックフィル（M9）は到達時点と祝い済み時点を
同時刻で先にINSERTすることで、新規お祝いが導入時点までの節目に遡らないようにする。
"""

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.enums import MilestoneType
from app.models.base import Base, CreatedAtMixin


class GoalMilestoneAchievement(CreatedAtMixin, Base):
    __tablename__ = "goal_milestone_achievement"
    __table_args__ = (
        UniqueConstraint(
            "goal_id", "milestone_type", "milestone_key", name="uq_goal_milestone_achievement"
        ),
        Index("ix_goal_milestone_achievement_goal_id", "goal_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goal.id", ondelete="CASCADE"), nullable=False)
    milestone_type: Mapped[MilestoneType] = mapped_column(
        Enum(MilestoneType, native_enum=False, validate_strings=True), nullable=False
    )
    #: 節目を一意に表す値（例：連続日数の閾値「7」、資格の教材1周完了の
    #: 「{material_id}:{cycle_number}」）。種別ごとの組み立て方は
    #: `milestone_service_<category>.py`が持つ。
    milestone_key: Mapped[str] = mapped_column(String(100), nullable=False)
    achieved_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    celebrated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
