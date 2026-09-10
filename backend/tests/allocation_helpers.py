"""リソース配分（goal_slot_allocation）をテストから組み立てるための共通処理。

リソース配分がスロット単位の分数になったことで（実装フェーズ分割計画書Phase28〜29）、
「この目標が全スロットの時間を使える」状態を作るのに複数テーブルの操作が必要になった。
各テストファイルへ同じ組み立てを書き写すのを避けるためここへ集約する
（CLAUDE.md DRYの原則）。
"""

from sqlalchemy.orm import Session

from app.models.resource import GoalSlotAllocation, ResourceSlot
from app.services import slot_service


def allocate(session: Session, goal_id: int, slot_id: int, minutes: int) -> GoalSlotAllocation:
    """1スロット分の配分を作成する。"""
    allocation = GoalSlotAllocation(goal_id=goal_id, slot_id=slot_id, minutes=minutes)
    session.add(allocation)
    session.flush()
    return allocation


def allocate_full(session: Session, goal_id: int, *slots: ResourceSlot) -> None:
    """指定スロット（省略時は全スロット）の連続時間を丸ごとその目標へ配分する。

    比率方式における `resource_ratio=1.0`（全時間を1目標が占有）に相当する状態を作る。
    """
    targets = list(slots) or session.query(ResourceSlot).all()
    for slot in targets:
        allocate(session, goal_id, slot.id, slot_service.slot_duration_minutes(slot))
