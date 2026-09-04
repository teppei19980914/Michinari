"""add WORK goal category tables: work_assignment, work_log, and goal_retrospective
period_type/period_key/target_goal_text/business_summary/achievement_score/
achievement_reflection/next_goal_text/report_notes/edited_at columns
(data structure doc 5.1/5.3/5.4, implementation phase plan Phase 20)

goal.category は既に String 型で EXAM/READING 両対応済みのため列追加は不要
（値として WORK を許すだけ）。

goal_retrospective へ追加する9列はすべて nullable=True・server_default なし
（Phase20指示・注意点）。NOT NULL 列ではないため、b7a1021fff73/2b8b04b91e47 で
問題になった「SQLite batch mode でのテーブル再作成時に server_default が
既存行コピーの NOT NULL 制約を満たせなくなる」不具合は発生しない。

(goal_id, period_type, period_key, is_anonymized) の UNIQUE 制約は、標準 SQL の
NULL 比較（NULL 同士は等しいとみなされない）により、period_type・period_key が
共に NULL の既存 EXAM/READING 行同士を制約対象外のまま扱う（データ構造編5.4
「制約」、5.6 インデックス定義）。既存データがある状態でも安全に適用できるため
同一マイグレーション内で追加する。

Revision ID: e1f4a9c3b6d8
Revises: 9723ab049ecd
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f4a9c3b6d8'
down_revision: Union[str, Sequence[str], None] = '9723ab049ecd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'work_assignment',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('goal_id', sa.Integer(), nullable=False),
        sa.Column('client_name', sa.String(), nullable=True),
        sa.Column('expected_content', sa.Text(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['goal_id'], ['goal.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('goal_id'),
    )

    op.create_table(
        'work_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('daily_record_id', sa.Integer(), nullable=False),
        sa.Column('work_assignment_id', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['daily_record_id'], ['daily_record.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['work_assignment_id'], ['work_assignment.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'work_assignment_id', 'daily_record_id', name='uq_work_log_assignment_record'
        ),
    )
    with op.batch_alter_table('work_log', schema=None) as batch_op:
        batch_op.create_index('ix_work_log_daily_record_id', ['daily_record_id'], unique=False)

    with op.batch_alter_table('goal_retrospective', schema=None) as batch_op:
        batch_op.add_column(sa.Column('period_type', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('period_key', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('target_goal_text', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('business_summary', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('achievement_score', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('achievement_reflection', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('next_goal_text', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('report_notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('edited_at', sa.DateTime(), nullable=True))
        batch_op.create_unique_constraint(
            'uq_goal_retrospective_goal_period_anonymized',
            ['goal_id', 'period_type', 'period_key', 'is_anonymized'],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('goal_retrospective', schema=None) as batch_op:
        batch_op.drop_constraint(
            'uq_goal_retrospective_goal_period_anonymized', type_='unique'
        )
        batch_op.drop_column('edited_at')
        batch_op.drop_column('report_notes')
        batch_op.drop_column('next_goal_text')
        batch_op.drop_column('achievement_reflection')
        batch_op.drop_column('achievement_score')
        batch_op.drop_column('business_summary')
        batch_op.drop_column('target_goal_text')
        batch_op.drop_column('period_key')
        batch_op.drop_column('period_type')

    with op.batch_alter_table('work_log', schema=None) as batch_op:
        batch_op.drop_index('ix_work_log_daily_record_id')
    op.drop_table('work_log')

    op.drop_table('work_assignment')
