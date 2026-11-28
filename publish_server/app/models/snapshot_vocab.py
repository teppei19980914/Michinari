"""公開単語帳デッキスナップショット（データモデル3章 published_vocab_deck、D-01・D-23）。

`cards_json`はローカルの`vocab_card`相当の内容（カード種類別フィールド流用規則を踏襲）を
JSON化したスナップショット。アップロード（`PUT /publish/vocab/{local_deck_id}`）は
`(account_id, local_deck_id)`単位のupsert（単位2設計、published_gantt_snapshotと同じ方式）。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class PublishedVocabDeck(Base):
    __tablename__ = "published_vocab_deck"
    __table_args__ = (
        UniqueConstraint("account_id", "local_deck_id", name="uq_published_vocab_account_deck"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("publish_account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: ローカル側`vocab_deck.id`（D-23により外部キー制約は張らない）。
    local_deck_id: Mapped[int] = mapped_column(Integer, nullable=False)
    deck_name: Mapped[str] = mapped_column(String(2000), nullable=False)
    cards_json: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
