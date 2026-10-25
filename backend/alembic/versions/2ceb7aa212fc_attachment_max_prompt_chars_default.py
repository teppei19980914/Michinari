"""attachment_max_prompt_chars_default: 添付ファイル機能導入にあわせ ai.max_prompt_chars の
既定値を30000から50000へ引き上げる（開発Todo_添付ファイル機能_v1.0 A5・P9）。

app_settingには`prompt_template.is_customized`のようなカスタマイズ済みフラグが無いため、
「現在値が旧既定値(30000)のままの行のみ」を更新する値一致ヒューリスティックで、利用者が
独自の値へ変更済みの行には触れない。50000への引き上げは上限を緩める方向のみのため、
このヒューリスティックで取り残される側（独自に30000へ変更していた行が誤って更新される
ケース）が起きても実害は小さい。

Revision ID: 2ceb7aa212fc
Revises: c02c4e8b1cf1
Create Date: 2026-10-25 14:33:37.351149

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ceb7aa212fc'
down_revision: Union[str, Sequence[str], None] = 'c02c4e8b1cf1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_DEFAULT = "30000"
_NEW_DEFAULT = "50000"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        sa.text(
            "UPDATE app_setting SET value = :new_value "
            "WHERE key = 'ai.max_prompt_chars' AND value = :old_value"
        ).bindparams(new_value=_NEW_DEFAULT, old_value=_OLD_DEFAULT)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        sa.text(
            "UPDATE app_setting SET value = :old_value "
            "WHERE key = 'ai.max_prompt_chars' AND value = :new_value"
        ).bindparams(old_value=_OLD_DEFAULT, new_value=_NEW_DEFAULT)
    )
