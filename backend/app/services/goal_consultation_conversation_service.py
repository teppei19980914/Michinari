"""目標相談チャットの「会話」単位の作成・一覧・削除（S11、開発Todo v1.2 W6・W7）。

質疑そのものの処理（`goal_consultation_service_common.py`）・相談履歴の往復単位の保存
（`goal_consultation_log_service.py`）とは責務を分ける（CODING_RULES.md単一責任）。
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.goal import Goal, GoalConsultationConversation
from app.services.exceptions import NotFoundError


@dataclass(frozen=True)
class GoalConsultationConversationEntry:
    """会話一覧表示用の1件（API層でRead schemaへ変換する）。"""

    id: int
    title: str
    created_at: dt.datetime


def _to_entry(row: GoalConsultationConversation) -> GoalConsultationConversationEntry:
    return GoalConsultationConversationEntry(
        id=row.id, title=row.title, created_at=row.created_at
    )


def create(session: Session, goal: Goal, title: str) -> GoalConsultationConversationEntry:
    """新しい会話を開始する（利用者が自由に複数作成できる方式、確認事項③）。

    AI通信を伴わない単純な書き込みのため`serialize_writes()`は使わない
    （CODING_RULES.md「AI通信とトランザクション」の対象はAI呼び出し前後の書き込みのみ）。
    """
    row = GoalConsultationConversation(goal_id=goal.id, title=title)
    session.add(row)
    session.commit()
    return _to_entry(row)


def list_for_goal(session: Session, goal: Goal) -> list[GoalConsultationConversationEntry]:
    """この目標の会話一覧を、作成日時の古い順（同時刻はid昇順でタイブレーク、
    CODING_RULES.md「タイムスタンプでの並び替え」）に返す。
    """
    rows = (
        session.query(GoalConsultationConversation)
        .filter(GoalConsultationConversation.goal_id == goal.id)
        .order_by(GoalConsultationConversation.created_at, GoalConsultationConversation.id)
        .all()
    )
    return [_to_entry(row) for row in rows]


def get_for_goal(
    session: Session, goal: Goal, conversation_id: int
) -> GoalConsultationConversation:
    """この目標に属する会話を1件取得する。`goal_id`が一致しない場合はNotFoundError
    （他目標の会話へ不正にアクセスできないようにする）。
    """
    row = (
        session.query(GoalConsultationConversation)
        .filter(
            GoalConsultationConversation.id == conversation_id,
            GoalConsultationConversation.goal_id == goal.id,
        )
        .first()
    )
    if row is None:
        raise NotFoundError("GoalConsultationConversation", conversation_id)
    return row


def delete(session: Session, goal: Goal, conversation_id: int) -> None:
    """会話を削除する（所属する相談履歴もDB側`ondelete="CASCADE"`で連鎖削除される）。"""
    row = get_for_goal(session, goal, conversation_id)
    session.delete(row)
    session.flush()
