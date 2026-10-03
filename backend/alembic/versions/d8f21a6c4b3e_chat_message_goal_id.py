"""chat_message: add goal_id column (data structure doc 5.4, logic/prompt doc L-07, Phase26)

Revision ID: d8f21a6c4b3e
Revises: 7c2e5a1d9f4b
Create Date: 2026-09-06 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d8f21a6c4b3e"
down_revision: Union[str, Sequence[str], None] = "7c2e5a1d9f4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    日次フィードバックのAI対話（DAILY_FEEDBACK/DAILY_FEEDBACK_READING/DAILY_FEEDBACK_WORK）を
    カテゴリ単位の共有スレッドから目標単位へ分離するための列追加（未決事項L-07の解消方針転換）。
    既存行はどの目標宛てだったか技術的に判別不能なためgoal_id=NULLのまま引き継ぐ（daily_message
    のc7d391a6f0e5マイグレーションと同じ安全弁）。分析タブ「成長記述」で利用者が手動で
    目標を割り当てられるようにする（PATCH /analytics/growth-descriptions/{id}）。
    """
    with op.batch_alter_table("chat_message", schema=None) as batch_op:
        batch_op.add_column(sa.Column("goal_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_chat_message_goal_id_goal", "goal", ["goal_id"], ["id"], ondelete="CASCADE"
        )
        batch_op.create_index("ix_chat_message_goal_id", ["goal_id"])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("chat_message", schema=None) as batch_op:
        batch_op.drop_index("ix_chat_message_goal_id")
        batch_op.drop_constraint("fk_chat_message_goal_id_goal", type_="foreignkey")
        batch_op.drop_column("goal_id")
