"""公開アカウント（データモデル3章 publish_account）。1アカウント=1利用者（D-16）。"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PublishAccount(TimestampMixin, Base):
    __tablename__ = "publish_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)

    #: ログイン試行回数制限（D-17）。失敗ごとに増加し、成功時に0へ戻す。
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: ロック解除時刻（この時刻までログイン拒否）。ロックしていなければNULL。
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
