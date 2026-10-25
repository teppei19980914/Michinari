"""attachment_tables: 添付ファイル機能の新規3テーブル（開発Todo_添付ファイル機能_v1.0）。

attachment（goal非依存の共通プール）・chat_message_attachment・goal_consultation_log_attachment
を新設する。いずれも新規create_tableのみで既存データ移行は発生しない（CODING_RULES.md
「DBマイグレーションのテスト」の対象外）。

Revision ID: c02c4e8b1cf1
Revises: 6f982ca649bb
Create Date: 2026-10-25 14:32:39.020309

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c02c4e8b1cf1'
down_revision: Union[str, Sequence[str], None] = '6f982ca649bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "attachment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "chat_message_attachment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_message_id", sa.Integer(), nullable=False),
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["chat_message_id"], ["chat_message.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chat_message_id", "attachment_id", name="uq_chat_message_attachment"
        ),
    )
    op.create_index(
        "ix_chat_message_attachment_attachment_id",
        "chat_message_attachment",
        ["attachment_id"],
        unique=False,
    )

    op.create_table(
        "goal_consultation_log_attachment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("goal_consultation_log_id", sa.Integer(), nullable=False),
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["goal_consultation_log_id"], ["goal_consultation_log.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "goal_consultation_log_id",
            "attachment_id",
            name="uq_goal_consultation_log_attachment",
        ),
    )
    op.create_index(
        "ix_goal_consultation_log_attachment_attachment_id",
        "goal_consultation_log_attachment",
        ["attachment_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_goal_consultation_log_attachment_attachment_id",
        table_name="goal_consultation_log_attachment",
    )
    op.drop_table("goal_consultation_log_attachment")

    op.drop_index(
        "ix_chat_message_attachment_attachment_id", table_name="chat_message_attachment"
    )
    op.drop_table("chat_message_attachment")

    op.drop_table("attachment")
