"""公開APIトークン（データモデル3章 publish_api_token）。

ローカルアプリ（単位4）がアップロードAPIを呼ぶ際に使う。平文トークンはDBへ保存しない
（発行時に一度だけ呼び出し元へ返す。D-19）。保存は`token_hash`のみ（SHA-256ハッシュ）。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin


class PublishApiToken(CreatedAtMixin, Base):
    __tablename__ = "publish_api_token"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("publish_account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
