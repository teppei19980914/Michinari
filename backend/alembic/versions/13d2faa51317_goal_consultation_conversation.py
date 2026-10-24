"""goal_consultation_conversation: 目標相談チャットの「会話」単位を新設する（開発Todo v1.2 W6）

利用者が会話を自由に作成できる方式を採用した（確認事項③、2026-10-24利用者確認）。既存の
`goal_consultation_log`には会話の概念が無い行が既にあるため、`goal_id`ごとに1件の移行用会話
（`title`は空文字、`created_at`はその目標の最も古いログの`created_at`）を生成し、既存の全ログを
そこへ割り当ててから`conversation_id`をNOT NULL化する（CODING_RULES.md「DBマイグレーションの
テスト」対象。既存データが無い場合は移行用会話が1件も作られないだけで、以後は空のまま）。

Revision ID: 13d2faa51317
Revises: c7fbb21cc857
Create Date: 2026-10-24 10:33:43.130647

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '13d2faa51317'
down_revision: Union[str, Sequence[str], None] = 'c7fbb21cc857'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: 既存ログをgoal_idごとに1件の移行用会話へ割り当てる（§0 W6）。
_BACKFILL_CONVERSATIONS_SQL = """
    INSERT INTO goal_consultation_conversation (goal_id, title, created_at)
    SELECT goal_id, '', MIN(created_at)
    FROM goal_consultation_log
    GROUP BY goal_id
"""

_BACKFILL_LOG_CONVERSATION_ID_SQL = """
    UPDATE goal_consultation_log
    SET conversation_id = (
        SELECT c.id FROM goal_consultation_conversation c
        WHERE c.goal_id = goal_consultation_log.goal_id
    )
    WHERE conversation_id IS NULL
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "goal_consultation_conversation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("goal_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["goal_id"], ["goal.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_goal_consultation_conversation_goal_id",
        "goal_consultation_conversation",
        ["goal_id"],
        unique=False,
    )

    with op.batch_alter_table("goal_consultation_log", schema=None) as batch_op:
        batch_op.add_column(sa.Column("conversation_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_goal_consultation_log_conversation_id_goal_consultation_conversation",
            "goal_consultation_conversation",
            ["conversation_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(
            "ix_goal_consultation_log_conversation_id", ["conversation_id"]
        )

    op.execute(_BACKFILL_CONVERSATIONS_SQL)
    op.execute(_BACKFILL_LOG_CONVERSATION_ID_SQL)

    with op.batch_alter_table("goal_consultation_log", schema=None) as batch_op:
        batch_op.alter_column(
            "conversation_id", existing_type=sa.Integer(), nullable=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("goal_consultation_log", schema=None) as batch_op:
        batch_op.drop_index("ix_goal_consultation_log_conversation_id")
        batch_op.drop_constraint(
            "fk_goal_consultation_log_conversation_id_goal_consultation_conversation",
            type_="foreignkey",
        )
        batch_op.drop_column("conversation_id")

    op.drop_index(
        "ix_goal_consultation_conversation_goal_id",
        table_name="goal_consultation_conversation",
    )
    op.drop_table("goal_consultation_conversation")
