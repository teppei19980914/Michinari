"""daily_goal_diary: split diary_body/diary_learned by goal (data structure doc 5.4, logic/prompt doc L-04)

Revision ID: 9a1c3e7d5b2f
Revises: f3a1b8c6d9e2
Create Date: 2026-08-30 00:00:00.000000

"""

from datetime import UTC, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9a1c3e7d5b2f"
down_revision: Union[str, Sequence[str], None] = "f3a1b8c6d9e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "daily_goal_diary",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("daily_record_id", sa.Integer(), nullable=False),
        sa.Column("goal_id", sa.Integer(), nullable=True),
        sa.Column("diary_body", sa.Text(), nullable=True),
        sa.Column("diary_learned", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["daily_record_id"], ["daily_record.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["goal_id"], ["goal.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("daily_record_id", "goal_id", name="uq_daily_goal_diary_record_goal"),
    )

    _backfill_diary_entries()

    with op.batch_alter_table("daily_record", schema=None) as batch_op:
        batch_op.drop_column("diary_body")
        batch_op.drop_column("diary_learned")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("daily_record", schema=None) as batch_op:
        batch_op.add_column(sa.Column("diary_learned", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("diary_body", sa.Text(), nullable=True))

    _restore_diary_columns()

    op.drop_table("daily_goal_diary")


def _backfill_diary_entries() -> None:
    """既存の daily_record.diary_body/diary_learned を daily_goal_diary へ複製する
    （設計書ロジック・プロンプト編 未決事項L-04）。

    帰属先の決定方法:
    1. その日の study_log が紐づく教材の goal_id（複数目標にまたがる場合は全てへ複製）
    2. study_logが1件も無い日は、その日付時点で活動中と推定できる目標
       （start_date <= record_date かつ closed_at が未設定または record_date より後）
    3. 1・2いずれも該当なしの場合は goal_id=NULL で1件だけ保存し、データを失わない
    """
    bind = op.get_bind()
    now = datetime.now(UTC)

    daily_record = sa.table(
        "daily_record",
        sa.column("id", sa.Integer),
        sa.column("record_date", sa.Date),
        sa.column("diary_body", sa.Text),
        sa.column("diary_learned", sa.Text),
    )
    study_log = sa.table(
        "study_log",
        sa.column("daily_record_id", sa.Integer),
        sa.column("material_id", sa.Integer),
    )
    material = sa.table(
        "material",
        sa.column("id", sa.Integer),
        sa.column("goal_id", sa.Integer),
    )
    goal = sa.table(
        "goal",
        sa.column("id", sa.Integer),
        sa.column("start_date", sa.Date),
        sa.column("closed_at", sa.DateTime),
    )
    daily_goal_diary = sa.table(
        "daily_goal_diary",
        sa.column("daily_record_id", sa.Integer),
        sa.column("goal_id", sa.Integer),
        sa.column("diary_body", sa.Text),
        sa.column("diary_learned", sa.Text),
        sa.column("created_at", sa.DateTime),
    )

    records = bind.execute(
        sa.select(
            daily_record.c.id,
            daily_record.c.record_date,
            daily_record.c.diary_body,
            daily_record.c.diary_learned,
        ).where(
            sa.or_(daily_record.c.diary_body.isnot(None), daily_record.c.diary_learned.isnot(None))
        )
    ).fetchall()

    for record in records:
        goal_ids = (
            bind.execute(
                sa.select(material.c.goal_id)
                .distinct()
                .select_from(study_log.join(material, study_log.c.material_id == material.c.id))
                .where(study_log.c.daily_record_id == record.id)
            )
            .scalars()
            .all()
        )

        if not goal_ids:
            goal_ids = (
                bind.execute(
                    sa.select(goal.c.id).where(
                        goal.c.start_date <= record.record_date,
                        sa.or_(goal.c.closed_at.is_(None), goal.c.closed_at > record.record_date),
                    )
                )
                .scalars()
                .all()
            )

        target_goal_ids: list[int | None] = list(goal_ids) if goal_ids else [None]

        for goal_id in target_goal_ids:
            bind.execute(
                daily_goal_diary.insert().values(
                    daily_record_id=record.id,
                    goal_id=goal_id,
                    diary_body=record.diary_body,
                    diary_learned=record.diary_learned,
                    created_at=now,
                )
            )


def _restore_diary_columns() -> None:
    """downgrade用: daily_goal_diaryの内容をdaily_recordへ1件へ戻す（簡易実装）。

    複数目標に複製済みの行は最初の1件のみを採用する（目標横断だった前提の完全な復元は
    不可能なため、downgradeは開発時のロールバック用途に限定する）。
    """
    bind = op.get_bind()

    daily_record = sa.table(
        "daily_record",
        sa.column("id", sa.Integer),
        sa.column("diary_body", sa.Text),
        sa.column("diary_learned", sa.Text),
    )
    daily_goal_diary = sa.table(
        "daily_goal_diary",
        sa.column("id", sa.Integer),
        sa.column("daily_record_id", sa.Integer),
        sa.column("diary_body", sa.Text),
        sa.column("diary_learned", sa.Text),
    )

    rows = bind.execute(
        sa.select(
            daily_goal_diary.c.daily_record_id,
            daily_goal_diary.c.diary_body,
            daily_goal_diary.c.diary_learned,
        ).order_by(daily_goal_diary.c.daily_record_id, daily_goal_diary.c.id)
    ).fetchall()

    seen: set[int] = set()
    for row in rows:
        if row.daily_record_id in seen:
            continue
        seen.add(row.daily_record_id)
        bind.execute(
            daily_record.update()
            .where(daily_record.c.id == row.daily_record_id)
            .values(diary_body=row.diary_body, diary_learned=row.diary_learned)
        )
