"""会話とフォルダの管理（設計書 ロジック・プロンプト編16.3、データ構造編5.5 ai_conversation）。

用途と日付ごとに会話を分離する（16.3手順1〜3）。フォルダは目標ごとに
"{ai.folder_prefix}_{目標名}" として作成する。日次報告は複数の目標にまたがりうるため
goal_id=NULL とする（ai_conversationのgoal_id列がNULL許容である設計、5.5）。今日の一言は
目標ごとに独立して生成するため goal=goal を渡すが、ACTIVEな目標が1件も無い日のみ
goal_id=NULL とする（未決事項L-04、daily_message_service参照）。goal_id=NULL の会話は
ai.folder_prefix が指す共通フォルダ（既定値「ミチナリ」）配下に作成する。NewtonX側で
フォルダを削除するだけでアプリ由来の会話を一括解放できるようにする運用要件のため、
goal非依存の会話も無条件でフォルダに収める。
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

    folder_prefix = setting_reader.get_str(session, AI_FOLDER_PREFIX)
    folder_name = f"{folder_prefix}_{goal.name}" if goal is not None else folder_prefix
    chat_uid = ai_client.create_chat_in_folder_by_name(
        session, assistant_uid=assistant_uid, folder_name=folder_name, title=title
    )

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
