"""ブラウザセッション（データモデル3章 publish_session）。

主キー自体がセッショントークンのハッシュ（SHA-256）であり、Cookieには平文トークンのみを
格納する（データ構造編と同じ「ハッシュ保存・平文は一度だけ返す」方針、D-19と同系）。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin


class PublishSession(CreatedAtMixin, Base):
    __tablename__ = "publish_session"

    #: セッショントークン（Cookie値）のSHA-256ハッシュ（16進64文字）。
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("publish_account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: CSRFトークン（D-18）。ログイン応答で一度だけ返し、以後は状態変更リクエストの
    #: `X-CSRF-Token`ヘッダと照合する。
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
