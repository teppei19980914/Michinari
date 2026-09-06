"""goal: add archived_at column (data structure doc 5.3, requirements R-61〜R-63)

Revision ID: f3a1b8c6d9e2
Revises: 2b8b04b91e47
Create Date: 2026-08-30 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f3a1b8c6d9e2"
down_revision: Union[str, Sequence[str], None] = "2b8b04b91e47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("goal", schema=None) as batch_op:
        batch_op.add_column(sa.Column("archived_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("goal", schema=None) as batch_op:
        batch_op.drop_column("archived_at")
