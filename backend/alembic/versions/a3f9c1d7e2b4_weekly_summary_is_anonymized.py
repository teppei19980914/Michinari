"""weekly_summary: add is_anonymized column (data structure doc 7.3)

Revision ID: a3f9c1d7e2b4
Revises: d2f4e604b336
Create Date: 2026-08-25 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a3f9c1d7e2b4"
down_revision: Union[str, Sequence[str], None] = "d2f4e604b336"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("weekly_summary", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_anonymized", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.drop_constraint("uq_weekly_summary_goal_week", type_="unique")
        batch_op.create_unique_constraint(
            "uq_weekly_summary_goal_week", ["goal_id", "week_start_date", "is_anonymized"]
        )
        batch_op.alter_column("is_anonymized", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("weekly_summary", schema=None) as batch_op:
        batch_op.drop_constraint("uq_weekly_summary_goal_week", type_="unique")
        batch_op.create_unique_constraint(
            "uq_weekly_summary_goal_week", ["goal_id", "week_start_date"]
        )
        batch_op.drop_column("is_anonymized")
