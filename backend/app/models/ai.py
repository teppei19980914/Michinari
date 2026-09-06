"""AI連携系モデル（設計書 データ構造編 5.5）。

認証情報（PAT等）は本テーブル群に保存しない。開発キットの仕組みに委ねる（5.8）。
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.enums import AiPurpose, ConversationScope
from app.models.base import Base, CreatedAtMixin

if TYPE_CHECKING:  # pragma: no cover (型チェック専用、実行時には到達しない)
    from app.models.goal import Goal


class AiConversation(CreatedAtMixin, Base):
    """会話識別子。一覧取得APIを毎回呼ばないためローカルに保持する。"""

    __tablename__ = "ai_conversation"
    __table_args__ = (
        UniqueConstraint("goal_id", "scope", "scope_key", name="uq_ai_conversation_goal_scope_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int | None] = mapped_column(
        ForeignKey("goal.id", ondelete="CASCADE"), nullable=True
    )
    scope: Mapped[ConversationScope] = mapped_column(
        Enum(ConversationScope, native_enum=False, validate_strings=True), nullable=False
    )
    scope_key: Mapped[str] = mapped_column(Text, nullable=False)
    conversation_uid: Mapped[str] = mapped_column(Text, nullable=False)
    folder_uid: Mapped[str | None] = mapped_column(Text, nullable=True)
    # v0.10.5では文脈維持に使用できない（ソースコード確認済み）。将来改修時の記録として保持。
    last_parent_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    goal: Mapped["Goal | None"] = relationship(back_populates="ai_conversations")


class AiLog(CreatedAtMixin, Base):
    """AI通信ログ。送信文字数・縮退有無を記録し入力上限の実測に用いる。"""

    __tablename__ = "ai_log"
    __table_args__ = (Index("ix_ai_log_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    purpose: Mapped[AiPurpose] = mapped_column(
        Enum(AiPurpose, native_enum=False, validate_strings=True), nullable=False
    )
    conversation_uid: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_body: Mapped[str] = mapped_column(Text, nullable=False)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    was_truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
