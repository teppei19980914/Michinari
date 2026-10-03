"""recap: テーマ別・週またぎ累積の振り返り用テーブルを追加する（新規テーブルのみ）

Revision ID: 4d9e2a6b1c7f
Revises: 3c8d1f5a9e2b
Create Date: 2026-10-04 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4d9e2a6b1c7f"
down_revision: Union[str, Sequence[str], None] = "3c8d1f5a9e2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "recap_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("goal_id", sa.Integer(), nullable=False),
        sa.Column(
            "source_kind",
            sa.Enum("DIARY", "READING", name="recapsourcekind", native_enum=False),
            nullable=False,
        ),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("record_date", sa.Date(), nullable=False),
        sa.Column("classified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["goal_id"], ["goal.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_kind", "source_id", name="uq_recap_entry_source"),
    )
    op.create_index("ix_recap_entry_goal_id", "recap_entry", ["goal_id"], unique=False)
    op.create_table(
        "recap_theme",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("goal_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["goal_id"], ["goal.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("goal_id", "name", name="uq_recap_theme_goal_name"),
    )
    op.create_table(
        "recap_theme_link",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("theme_id", sa.Integer(), nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["theme_id"], ["recap_theme.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entry_id"], ["recap_entry.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("theme_id", "entry_id", name="uq_recap_theme_link_pair"),
    )
    op.create_index("ix_recap_theme_link_entry_id", "recap_theme_link", ["entry_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_recap_theme_link_entry_id", table_name="recap_theme_link")
    op.drop_table("recap_theme_link")
    op.drop_table("recap_theme")
    op.drop_index("ix_recap_entry_goal_id", table_name="recap_entry")
    op.drop_table("recap_entry")
