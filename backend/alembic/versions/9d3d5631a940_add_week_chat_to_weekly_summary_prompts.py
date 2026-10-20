"""add week chat to weekly summary prompts

Revision ID: 9d3d5631a940
Revises: 0ad4f28cd909
Create Date: 2026-10-20 18:32:44.982456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d3d5631a940'
down_revision: Union[str, Sequence[str], None] = '0ad4f28cd909'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
