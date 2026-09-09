"""resource allocation per slot (data structure doc 5.2/5.4, requirements R-07/R-84〜R-87)

Revision ID: f2b7c4a91d3e
Revises: c1a5f9e3d7b2
Create Date: 2026-09-09 18:10:00.000000

リソース配分を比率（goal.resource_ratio）からスロット単位の時間（goal_slot_allocation）へ
移行する。既存の比率は「比率 × 各スロットの連続時間（分）」を切り捨てた値として各スロットへ
転記するため、移行前後で配分の実質的な意味が保たれる（切り捨てにより合計がスロット容量を
超えないことも保証される）。

study_log.minutes_spent は削除せず「スロット別入力の合計」として意味を変えて存続させる。
これにより実効速度（ロジック・プロンプト編8.1）・週次集計・ナレッジエクスポートが
無改修のまま動作し、既存の実績データも変換なしで引き継がれる。
"""

import datetime as dt
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f2b7c4a91d3e"
down_revision: Union[str, Sequence[str], None] = "c1a5f9e3d7b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: 1分あたりの秒数（連続時間を分へ換算する際の除数）。
_SECONDS_PER_MINUTE = 60

#: SQLAlchemyのDateTime型がSQLiteへ書き込むのと同じ表記。生SQLで挿入する行を
#: ORM経由の行と同じ形式に揃える（Python 3.12で非推奨のdatetimeアダプタも回避できる）。
_DATETIME_STORAGE_FORMAT = "%Y-%m-%d %H:%M:%S.%f"


def _parse_time(raw: object) -> dt.time:
    """SQLiteのTIME列（文字列で格納される）を time へ変換する。

    SQLAlchemyのTime型はマイクロ秒付き（HH:MM:SS.ffffff）でも秒まででも書き込みうるため、
    両方を受け付ける。既にtimeオブジェクトの場合（他DBバックエンド）はそのまま返す。
    """
    if isinstance(raw, dt.time):
        return raw
    text = str(raw)
    for fmt in ("%H:%M:%S.%f", "%H:%M:%S", "%H:%M"):
        try:
            return dt.datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"時刻として解釈できない値です: {text!r}")


def _duration_minutes(start: object, end: object) -> int:
    """スロットの連続時間（分）。日付をまたぐスロットは想定しない（開始 < 終了を保証済み）。"""
    start_time = _parse_time(start)
    end_time = _parse_time(end)
    delta = dt.datetime.combine(dt.date.min, end_time) - dt.datetime.combine(
        dt.date.min, start_time
    )
    return int(delta.total_seconds() // _SECONDS_PER_MINUTE)


def _migrate_ratios_to_allocations(connection: sa.Connection) -> None:
    """goal.resource_ratio を goal_slot_allocation へ按分転記する。

    スロットが1件も存在しない場合、転記先が無いため配分は空のまま引き継がれる。
    比率が正の目標が残る場合は再設定が必要になるため、警告として出力する
    （実装フェーズ分割計画書Phase28）。
    """
    slots = connection.execute(
        sa.text("SELECT id, start_time, end_time FROM resource_slot")
    ).fetchall()
    goals = connection.execute(
        sa.text("SELECT id, resource_ratio FROM goal WHERE resource_ratio > 0")
    ).fetchall()
    if not goals:
        return
    if not slots:
        goal_ids = ", ".join(str(row.id) for row in goals)
        print(
            "[f2b7c4a91d3e] 時間スロットが未登録のため、リソース配分を転記できませんでした。"
            f"次の目標は配分の再設定が必要です: {goal_ids}"
        )
        return

    now = dt.datetime.now(dt.UTC).strftime(_DATETIME_STORAGE_FORMAT)
    rows = []
    for slot in slots:
        duration = _duration_minutes(slot.start_time, slot.end_time)
        for goal in goals:
            minutes = int(goal.resource_ratio * duration)
            if minutes > 0:
                rows.append(
                    {
                        "goal_id": goal.id,
                        "slot_id": slot.id,
                        "minutes": minutes,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
    if rows:
        connection.execute(
            sa.text(
                "INSERT INTO goal_slot_allocation"
                " (goal_id, slot_id, minutes, created_at, updated_at)"
                " VALUES (:goal_id, :slot_id, :minutes, :created_at, :updated_at)"
            ),
            rows,
        )


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "goal_slot_allocation",
        sa.Column("goal_id", sa.Integer(), nullable=False),
        sa.Column("slot_id", sa.Integer(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["goal_id"], ["goal.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["slot_id"], ["resource_slot.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("goal_id", "slot_id"),
    )

    op.create_table(
        "study_log_slot_time",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("study_log_id", sa.Integer(), nullable=False),
        sa.Column("slot_id", sa.Integer(), nullable=True),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["study_log_id"], ["study_log.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["slot_id"], ["resource_slot.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("study_log_id", "slot_id", name="uq_study_log_slot_time"),
    )
    with op.batch_alter_table("study_log_slot_time", schema=None) as batch_op:
        batch_op.create_index("ix_study_log_slot_time_study_log_id", ["study_log_id"], unique=False)

    op.create_table(
        "reading_log_slot_time",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reading_log_id", sa.Integer(), nullable=False),
        sa.Column("slot_id", sa.Integer(), nullable=True),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["reading_log_id"], ["reading_log.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["slot_id"], ["resource_slot.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reading_log_id", "slot_id", name="uq_reading_log_slot_time"),
    )
    with op.batch_alter_table("reading_log_slot_time", schema=None) as batch_op:
        batch_op.create_index(
            "ix_reading_log_slot_time_reading_log_id", ["reading_log_id"], unique=False
        )

    with op.batch_alter_table("reading_log", schema=None) as batch_op:
        batch_op.add_column(sa.Column("minutes_spent", sa.Integer(), nullable=True))

    _migrate_ratios_to_allocations(op.get_bind())

    with op.batch_alter_table("goal", schema=None) as batch_op:
        batch_op.drop_column("resource_ratio")


def downgrade() -> None:
    """Downgrade schema.

    resource_ratio は「配分時間の合計 ÷ 全スロットの連続時間の合計」として復元する。
    スロット構成が変わっていなければ upgrade 前の値に近い比率へ戻るが、切り捨ての影響で
    完全には一致しない（比率から分への変換が不可逆であるため）。
    """
    connection = op.get_bind()
    with op.batch_alter_table("goal", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("resource_ratio", sa.Float(), nullable=False, server_default="0")
        )

    slots = connection.execute(sa.text("SELECT start_time, end_time FROM resource_slot")).fetchall()
    total_minutes = sum(_duration_minutes(s.start_time, s.end_time) for s in slots)
    if total_minutes > 0:
        connection.execute(
            sa.text(
                "UPDATE goal SET resource_ratio = COALESCE(("
                "  SELECT SUM(a.minutes) * 1.0 / :total FROM goal_slot_allocation a"
                "  WHERE a.goal_id = goal.id"
                "), 0)"
            ),
            {"total": total_minutes},
        )

    with op.batch_alter_table("reading_log", schema=None) as batch_op:
        batch_op.drop_column("minutes_spent")

    op.drop_table("reading_log_slot_time")
    op.drop_table("study_log_slot_time")
    op.drop_table("goal_slot_allocation")
