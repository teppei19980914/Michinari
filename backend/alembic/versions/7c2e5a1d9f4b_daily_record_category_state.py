"""daily_record.record_state/reported_atをカテゴリ別（EXAM/READING/WORK）の
6列（exam_record_state/exam_reported_at/reading_record_state/reading_reported_at/
work_record_state/work_reported_at）へ分割する（要件変更2026-09-05: 資格勉強の確定が
読書・仕事の確定まで巻き込んでしまう不具合の是正、実装フェーズ分割計画書外の追加要望）。

旧モデルは日付単位でしか確定状態を持たなかったため、過去データを完全には復元できない。
「そのカテゴリに該当するログ／日記／AI対話が1件でも存在する場合のみ」旧値を引き継ぐ
ベストエフォートの移行とする（該当が無ければ、そのカテゴリはその日一度も操作していない
ものとしてNULLのままにする。record_service.aggregate_record_stateのNULL＝未着手という
定義に合わせる）。

Revision ID: 7c2e5a1d9f4b
Revises: e1f4a9c3b6d8
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c2e5a1d9f4b'
down_revision: Union[str, Sequence[str], None] = 'e1f4a9c3b6d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RECORD_STATE_ENUM = sa.Enum('PROGRESS_ONLY', 'REPORTED', name='recordstate', native_enum=False)

_BACKFILL_SQL = """
    UPDATE daily_record
    SET
        exam_record_state = CASE WHEN (
            EXISTS(SELECT 1 FROM study_log WHERE study_log.daily_record_id = daily_record.id)
            OR EXISTS(
                SELECT 1 FROM daily_goal_diary
                WHERE daily_goal_diary.daily_record_id = daily_record.id
            )
            OR EXISTS(
                SELECT 1 FROM chat_message
                WHERE chat_message.daily_record_id = daily_record.id
                AND chat_message.purpose = 'DAILY_FEEDBACK'
            )
        ) THEN daily_record.record_state ELSE NULL END,
        exam_reported_at = CASE WHEN (
            daily_record.record_state = 'REPORTED'
            AND (
                EXISTS(SELECT 1 FROM study_log WHERE study_log.daily_record_id = daily_record.id)
                OR EXISTS(
                    SELECT 1 FROM daily_goal_diary
                    WHERE daily_goal_diary.daily_record_id = daily_record.id
                )
                OR EXISTS(
                    SELECT 1 FROM chat_message
                    WHERE chat_message.daily_record_id = daily_record.id
                    AND chat_message.purpose = 'DAILY_FEEDBACK'
                )
            )
        ) THEN daily_record.reported_at ELSE NULL END,
        reading_record_state = CASE WHEN (
            EXISTS(
                SELECT 1 FROM reading_log WHERE reading_log.daily_record_id = daily_record.id
            )
            OR EXISTS(
                SELECT 1 FROM chat_message
                WHERE chat_message.daily_record_id = daily_record.id
                AND chat_message.purpose = 'DAILY_FEEDBACK_READING'
            )
        ) THEN daily_record.record_state ELSE NULL END,
        reading_reported_at = CASE WHEN (
            daily_record.record_state = 'REPORTED'
            AND (
                EXISTS(
                    SELECT 1 FROM reading_log WHERE reading_log.daily_record_id = daily_record.id
                )
                OR EXISTS(
                    SELECT 1 FROM chat_message
                    WHERE chat_message.daily_record_id = daily_record.id
                    AND chat_message.purpose = 'DAILY_FEEDBACK_READING'
                )
            )
        ) THEN daily_record.reported_at ELSE NULL END,
        work_record_state = CASE WHEN (
            EXISTS(SELECT 1 FROM work_log WHERE work_log.daily_record_id = daily_record.id)
            OR EXISTS(
                SELECT 1 FROM chat_message
                WHERE chat_message.daily_record_id = daily_record.id
                AND chat_message.purpose = 'DAILY_FEEDBACK_WORK'
            )
        ) THEN daily_record.record_state ELSE NULL END,
        work_reported_at = CASE WHEN (
            daily_record.record_state = 'REPORTED'
            AND (
                EXISTS(SELECT 1 FROM work_log WHERE work_log.daily_record_id = daily_record.id)
                OR EXISTS(
                    SELECT 1 FROM chat_message
                    WHERE chat_message.daily_record_id = daily_record.id
                    AND chat_message.purpose = 'DAILY_FEEDBACK_WORK'
                )
            )
        ) THEN daily_record.reported_at ELSE NULL END
"""

_DOWNGRADE_BACKFILL_SQL = """
    UPDATE daily_record
    SET
        record_state = CASE
            WHEN (
                (exam_record_state IS NOT NULL
                    OR reading_record_state IS NOT NULL
                    OR work_record_state IS NOT NULL)
                AND (exam_record_state IS NULL OR exam_record_state = 'REPORTED')
                AND (reading_record_state IS NULL OR reading_record_state = 'REPORTED')
                AND (work_record_state IS NULL OR work_record_state = 'REPORTED')
            ) THEN 'REPORTED'
            ELSE 'PROGRESS_ONLY'
        END,
        reported_at = COALESCE(exam_reported_at, reading_reported_at, work_reported_at)
"""


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('daily_record', schema=None) as batch_op:
        batch_op.add_column(sa.Column('exam_record_state', _RECORD_STATE_ENUM, nullable=True))
        batch_op.add_column(sa.Column('exam_reported_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('reading_record_state', _RECORD_STATE_ENUM, nullable=True))
        batch_op.add_column(sa.Column('reading_reported_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('work_record_state', _RECORD_STATE_ENUM, nullable=True))
        batch_op.add_column(sa.Column('work_reported_at', sa.DateTime(), nullable=True))

    op.get_bind().execute(sa.text(_BACKFILL_SQL))

    with op.batch_alter_table('daily_record', schema=None) as batch_op:
        batch_op.drop_column('record_state')
        batch_op.drop_column('reported_at')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('daily_record', schema=None) as batch_op:
        batch_op.add_column(sa.Column('record_state', _RECORD_STATE_ENUM, nullable=True))
        batch_op.add_column(sa.Column('reported_at', sa.DateTime(), nullable=True))

    op.get_bind().execute(sa.text(_DOWNGRADE_BACKFILL_SQL))

    with op.batch_alter_table('daily_record', schema=None) as batch_op:
        batch_op.alter_column('record_state', nullable=False)
        batch_op.drop_column('exam_record_state')
        batch_op.drop_column('exam_reported_at')
        batch_op.drop_column('reading_record_state')
        batch_op.drop_column('reading_reported_at')
        batch_op.drop_column('work_record_state')
        batch_op.drop_column('work_reported_at')
