"""add goal.category and reading tables: book, reading_log (data structure doc 5.1/5.3/5.4)

Revision ID: b7a1021fff73
Revises: c7d391a6f0e5
Create Date: 2026-08-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7a1021fff73'
down_revision: Union[str, Sequence[str], None] = 'c7d391a6f0e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    goal.categoryのserver_defaultは意図的に残す（削除しない）。2b8b04b91e47と同じ理由：
    SQLiteはrender_as_batch=True（env.py）でカラム追加をテーブル再作成＋データコピーとして
    実行するため、同一batch_alter_table内でserver_defaultを追加後に削除すると、
    再作成後のテーブル定義からデフォルトが消えた状態でコピーが行われ、既存行に対する
    INSERT ... SELECTがNOT NULL制約違反になる。ORM層はGoalCategory.EXAMというPython側
    defaultを別途持つため、server_defaultを残しても実害はない。
    """
    with op.batch_alter_table('goal', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('category', sa.String(), nullable=False, server_default='EXAM')
        )

    op.create_table(
        'book',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('goal_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('author', sa.String(), nullable=True),
        sa.Column('total_pages', sa.Integer(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['goal_id'], ['goal.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('goal_id'),
    )

    op.create_table(
        'reading_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('daily_record_id', sa.Integer(), nullable=False),
        sa.Column('book_id', sa.Integer(), nullable=False),
        sa.Column('recall_body', sa.Text(), nullable=False),
        sa.Column('pages_read', sa.Integer(), nullable=True),
        sa.Column('current_page', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['daily_record_id'], ['daily_record.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['book_id'], ['book.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('book_id', 'daily_record_id', name='uq_reading_log_book_record'),
    )
    with op.batch_alter_table('reading_log', schema=None) as batch_op:
        batch_op.create_index('ix_reading_log_daily_record_id', ['daily_record_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('reading_log', schema=None) as batch_op:
        batch_op.drop_index('ix_reading_log_daily_record_id')
    op.drop_table('reading_log')

    op.drop_table('book')

    with op.batch_alter_table('goal', schema=None) as batch_op:
        batch_op.drop_column('category')
