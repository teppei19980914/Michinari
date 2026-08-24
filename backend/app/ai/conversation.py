"""会話とフォルダの管理（設計書 ロジック・プロンプト編16.3、データ構造編5.5 ai_conversation）。

用途と日付ごとに会話を分離する。フォルダは目標ごとに作成する（週次要約・総括レポートが
対象。日次報告・今日の一言は複数の目標にまたがりうるため goal_id=NULL とし、フォルダに
紐付けない — ai_conversationのgoal_id列がNULL許容である設計（5.5）を日次報告にも適用した
実装判断。目標が単一の場合と挙動は変わらないが、複数目標が同時にACTIVEな場合の folder 帰属が
設計書で明記されていないため、この整理で解決する）。
"""

from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.ai.exceptions import AiError
from app.constants.app_setting_keys import AI_FOLDER_PREFIX
from app.constants.enums import ConversationScope
from app.models.ai import AiConversation
from app.models.goal import Goal
from app.services import setting_reader


def _find_existing(
    session: Session, *, goal: Goal | None, scope: ConversationScope, scope_key: str
) -> AiConversation | None:
    """(goal, scope, scope_key)に一致する既存の会話を検索する。無ければNone。"""
    return (
        session.query(AiConversation)
        .filter(
            AiConversation.goal_id == (goal.id if goal else None),
            AiConversation.scope == scope,
            AiConversation.scope_key == scope_key,
        )
        .first()
    )


def ensure_conversation(
    session: Session,
    *,
    goal: Goal | None,
    scope: ConversationScope,
    scope_key: str,
    assistant_uid: str,
    title: str,
) -> AiConversation:
    """会話を取得または新規作成する（16.3手順1〜3）。

    既存の場合はAI基盤への問い合わせを行わない（会話識別子の取得はローカル保存値を用いる、
    16.1「一覧取得APIを毎回呼ばない」）。
    """
    existing = _find_existing(session, goal=goal, scope=scope, scope_key=scope_key)
    if existing is not None:
        return existing

    if goal is not None:
        folder_prefix = setting_reader.get_str(session, AI_FOLDER_PREFIX)
        folder_name = f"{folder_prefix}_{goal.name}"
        chat_uid = ai_client.create_chat_in_folder_by_name(
            session, assistant_uid=assistant_uid, folder_name=folder_name, title=title
        )
    else:
        chat_uid = ai_client.create_chat(session, assistant_uid=assistant_uid, title=title)

    if not chat_uid:
        raise AiError("会話の作成に失敗しました")

    conversation = AiConversation(
        goal_id=goal.id if goal else None,
        scope=scope,
        scope_key=scope_key,
        conversation_uid=chat_uid,
        folder_uid=None,
        last_parent_order=0,
    )
    session.add(conversation)
    session.flush()
    return conversation
