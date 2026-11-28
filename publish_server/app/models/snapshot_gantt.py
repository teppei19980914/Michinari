"""公開ガントスナップショット（データモデル3章 published_gantt_snapshot、D-01・D-05・D-23）。

`items_json`/`columns_json`/`cells_json`はローカルの`schedule_item`/`schedule_column`/
`schedule_cell`相当の内容をJSON化したスナップショット（コピー）。祝日データ自体は含めない
（D-05。公開ビューア（単位3）は`GET /holidays`相当・既存の`computeDayTypeRuns`を再利用する
前提で設計する）。

アップロード（`PUT /publish/gantt/{local_goal_id}`）は`(account_id, local_goal_id)`単位の
upsert（同一goal_idで上書き、単位2テスト観点）。`published_at`は初回公開時刻のまま変えず、
`updated_at`のみ差し替えごとに更新する。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class PublishedGanttSnapshot(Base):
    __tablename__ = "published_gantt_snapshot"
    __table_args__ = (
        UniqueConstraint("account_id", "local_goal_id", name="uq_published_gantt_account_goal"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("publish_account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: ローカル側`goal.id`（公開対象を選んだ元の目標。本サーバのDBとは別エンジンのため
    #: 外部キー制約は張らない、D-23）。
    local_goal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    goal_name: Mapped[str] = mapped_column(String(2000), nullable=False)
    items_json: Mapped[str] = mapped_column(Text, nullable=False)
    columns_json: Mapped[str] = mapped_column(Text, nullable=False)
    cells_json: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
