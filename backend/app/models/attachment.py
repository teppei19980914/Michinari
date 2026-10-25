"""添付ファイル系モデル（開発Todo_添付ファイル機能_v1.0）。

Attachment はgoal非依存の共通プール（A8）。同一ファイルを複数目標の日次報告・目標相談
チャットで使い回しても実体が重複しないようにするため、goal_idを持たない。PDF原本は
保存せず、抽出テキストのみを保持する（A2。backup_service.export_all_dataのJSON化で
BLOB例外が起きないようにするための設計でもある）。
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin

if TYPE_CHECKING:  # pragma: no cover (型チェック専用、実行時には到達しない)
    pass


class Attachment(CreatedAtMixin, Base):
    """添付ファイル（共通プール）。char_countは登録時に1回だけ確定する不変値のため保存する
    （都度算出ルールは日次ノルマ等の可変集計値が対象であり、不変な文字数は対象外）。
    """

    __tablename__ = "attachment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)

    chat_message_links: Mapped[list["ChatMessageAttachment"]] = relationship(
        back_populates="attachment", cascade="all, delete-orphan"
    )
    goal_consultation_log_links: Mapped[list["GoalConsultationLogAttachment"]] = relationship(
        back_populates="attachment", cascade="all, delete-orphan"
    )


class ChatMessageAttachment(Base):
    """日次報告のAI対話（chat_message）での添付ファイル利用リンク。"""

    __tablename__ = "chat_message_attachment"
    __table_args__ = (
        UniqueConstraint("chat_message_id", "attachment_id", name="uq_chat_message_attachment"),
        Index("ix_chat_message_attachment_attachment_id", "attachment_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_message_id: Mapped[int] = mapped_column(
        ForeignKey("chat_message.id", ondelete="CASCADE"), nullable=False
    )
    attachment_id: Mapped[int] = mapped_column(
        ForeignKey("attachment.id", ondelete="CASCADE"), nullable=False
    )

    attachment: Mapped["Attachment"] = relationship(back_populates="chat_message_links")


class GoalConsultationLogAttachment(Base):
    """目標相談チャットの質問（goal_consultation_log）での添付ファイル利用リンク。"""

    __tablename__ = "goal_consultation_log_attachment"
    __table_args__ = (
        UniqueConstraint(
            "goal_consultation_log_id", "attachment_id", name="uq_goal_consultation_log_attachment"
        ),
        Index(
            "ix_goal_consultation_log_attachment_attachment_id", "attachment_id"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_consultation_log_id: Mapped[int] = mapped_column(
        ForeignKey("goal_consultation_log.id", ondelete="CASCADE"), nullable=False
    )
    attachment_id: Mapped[int] = mapped_column(
        ForeignKey("attachment.id", ondelete="CASCADE"), nullable=False
    )

    attachment: Mapped["Attachment"] = relationship(back_populates="goal_consultation_log_links")
