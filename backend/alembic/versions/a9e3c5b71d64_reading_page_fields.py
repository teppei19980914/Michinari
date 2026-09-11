"""book.total_pages を必須化し、reading_log.pages_read を廃止する（仕様変更2026-09-11）

Revision ID: a9e3c5b71d64
Revises: f2b7c4a91d3e
Create Date: 2026-09-11 22:10:00.000000

読書の日次報告からページの入力欄を「現在ページ」1つに絞る（要件定義書R-65・R-70改訂）。

- reading_log.pages_read（読んだページ数）を削除する。利用者が毎日記憶していられない値で
  あるうえ、読書は記録・活用型の目標であり定量的な進捗管理を行わない（R-71）ため保持する
  意味がない。日次フィードバックのプロンプト（17.6）も一貫してページ数の評価を禁じている。
- book.total_pages を NOT NULL にする。進捗率（21.2）を常に算出できるようにするためで、
  「総ページ数が未入力なら進捗表示を行わない」という旧仕様を廃止する。

既存行の total_pages が NULL の場合は、その書籍に記録済みの現在ページの最大値
（1件も無ければ _FALLBACK_TOTAL_PAGES）を暫定値として補填する。総ページ数は書籍固有の
事実であってシステムが正しく推定できる値ではないため、進捗率が100%を超えない範囲で最小限
の値を置き、利用者が書籍編集で正しい値へ訂正できる状態にすることを狙いとしている。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a9e3c5b71d64"
down_revision: Union[str, Sequence[str], None] = "f2b7c4a91d3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: 現在ページの記録が1件も無い書籍へ補填する総ページ数。NOT NULL化のために値が必要だが
#: 推定の根拠が無いため、進捗率の分母として最小の1を置く（利用者による訂正が前提）。
_FALLBACK_TOTAL_PAGES = 1

_BACKFILL_TOTAL_PAGES_SQL = f"""
    UPDATE book
    SET total_pages = COALESCE(
        (
            SELECT MAX(reading_log.current_page)
            FROM reading_log
            WHERE reading_log.book_id = book.id
        ),
        {_FALLBACK_TOTAL_PAGES}
    )
    WHERE total_pages IS NULL
"""


def upgrade() -> None:
    # NOT NULL化の前にNULLを解消する。batch mode（env.pyのrender_as_batch=True）は
    # テーブルを作り直して行をコピーするため、NULLが残っていると制約違反で失敗する。
    op.execute(_BACKFILL_TOTAL_PAGES_SQL)
    with op.batch_alter_table("book", schema=None) as batch_op:
        batch_op.alter_column("total_pages", existing_type=sa.Integer(), nullable=False)
    with op.batch_alter_table("reading_log", schema=None) as batch_op:
        batch_op.drop_column("pages_read")


def downgrade() -> None:
    # 削除した pages_read の値は復元できない（NULLで再作成する）。
    with op.batch_alter_table("reading_log", schema=None) as batch_op:
        batch_op.add_column(sa.Column("pages_read", sa.Integer(), nullable=True))
    with op.batch_alter_table("book", schema=None) as batch_op:
        batch_op.alter_column("total_pages", existing_type=sa.Integer(), nullable=True)
