"""daily_message: generate independently per goal (data structure doc 5.5, logic/prompt doc L-04)

Revision ID: c7d391a6f0e5
Revises: b4c8e2f19a3d
Create Date: 2026-08-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d391a6f0e5'
down_revision: Union[str, Sequence[str], None] = 'b4c8e2f19a3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    daily_message.target_date の単独UNIQUE制約は、SQLite上では名前を持たない
    インラインUNIQUE（sa.UniqueConstraint('target_date')、initial_schema）として
    作成されているため、batch_alter_table の drop_constraint で名前指定して
    落とすことができない。そのため、テーブルを丸ごと作り直す方式を取る
    （テーブル名変更 → 新スキーマで作成 → データ移送 → 旧テーブル削除）。
    daily_messageを参照する他テーブルは無いため、この方式でFK破損は起きない。
    """
    op.rename_table('daily_message', 'daily_message_old')

    op.create_table(
        'daily_message',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('target_date', sa.Date(), nullable=False),
        sa.Column('goal_id', sa.Integer(), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['goal_id'], ['goal.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('target_date', 'goal_id', name='uq_daily_message_date_goal'),
    )

    bind = op.get_bind()
    old_table = sa.table(
        'daily_message_old',
        sa.column('id', sa.Integer),
        sa.column('target_date', sa.Date),
        sa.column('body', sa.Text),
        sa.column('generated_at', sa.DateTime),
    )
    new_table = sa.table(
        'daily_message',
        sa.column('id', sa.Integer),
        sa.column('target_date', sa.Date),
        sa.column('goal_id', sa.Integer),
        sa.column('body', sa.Text),
        sa.column('generated_at', sa.DateTime),
    )
    # 既存行は目標ごとの生成に切り替える前の「目標横断メッセージ」であり、特定の目標が
    # 書いたと偽ることになるため複製しない。goal_id=NULLのまま引き継ぐ（安全弁、L-04）。
    rows = bind.execute(
        sa.select(
            old_table.c.id, old_table.c.target_date, old_table.c.body, old_table.c.generated_at
        )
    ).fetchall()
    for row in rows:
        bind.execute(
            new_table.insert().values(
                id=row.id,
                target_date=row.target_date,
                goal_id=None,
                body=row.body,
                generated_at=row.generated_at,
            )
        )

    op.drop_table('daily_message_old')


def downgrade() -> None:
    """Downgrade schema.

    目標ごとに複数行あるうちの1件（goal_id=NULLの行があればそれ、無ければ最小id）だけを
    残し、単一目標横断メッセージだったスキーマへ戻す（開発時のロールバック限定、他の
    データ移行と同様に非可逆）。
    """
    op.rename_table('daily_message', 'daily_message_new')

    op.create_table(
        'daily_message',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('target_date', sa.Date(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('target_date'),
    )

    bind = op.get_bind()
    new_table = sa.table(
        'daily_message_new',
        sa.column('id', sa.Integer),
        sa.column('target_date', sa.Date),
        sa.column('goal_id', sa.Integer),
        sa.column('body', sa.Text),
        sa.column('generated_at', sa.DateTime),
    )
    old_table = sa.table(
        'daily_message',
        sa.column('id', sa.Integer),
        sa.column('target_date', sa.Date),
        sa.column('body', sa.Text),
        sa.column('generated_at', sa.DateTime),
    )

    rows = bind.execute(
        sa.select(
            new_table.c.id,
            new_table.c.target_date,
            new_table.c.goal_id,
            new_table.c.body,
            new_table.c.generated_at,
        ).order_by(new_table.c.target_date, new_table.c.goal_id.is_(None).desc(), new_table.c.id)
    ).fetchall()

    seen: set = set()
    for row in rows:
        if row.target_date in seen:
            continue
        seen.add(row.target_date)
        bind.execute(
            old_table.insert().values(
                target_date=row.target_date, body=row.body, generated_at=row.generated_at
            )
        )

    op.drop_table('daily_message_new')
