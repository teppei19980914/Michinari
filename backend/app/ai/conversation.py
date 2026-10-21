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

import logging

from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.ai.exceptions import AiError
from app.constants.app_setting_keys import AI_FOLDER_PREFIX
from app.constants.enums import ConversationScope
from app.database import serialize_writes
from app.models.ai import AiConversation
from app.models.goal import Goal
from app.services import setting_reader

logger = logging.getLogger(__name__)


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
    folder_name: str | None = None,
) -> AiConversation:
    """会話を取得または新規作成する（16.3手順1〜3）。

    既存の場合はAI基盤への問い合わせを行わない（会話識別子の取得はローカル保存値を用いる、
    16.1「一覧取得APIを毎回呼ばない」）。

    新規作成時は、AI応答を待つ前に会話行をコミットする。AI基盤との通信中に書き込み
    トランザクションを保持すると、SQLiteの書き込みロックを他の生成処理（月次報告・起動時
    バッチ等）が取れず「database is locked」で失敗するため（CODING_RULES.md「AI通信と
    トランザクション」）。呼び出し元は、この時点で未確定の業務書き込みを残さないこと。
    """
    existing = _find_existing(session, goal=goal, scope=scope, scope_key=scope_key)
    if existing is not None:
        return existing

    if folder_name is None:
        folder_prefix = setting_reader.get_str(session, AI_FOLDER_PREFIX)
        folder_name = f"{folder_prefix}_{goal.name}" if goal is not None else folder_prefix
    chat_uid = ai_client.create_chat_in_folder_by_name(
        session, assistant_uid=assistant_uid, folder_name=folder_name, title=title
    )

    if not chat_uid:
        raise AiError("Failed to create conversation")

    conversation = AiConversation(
        goal_id=goal.id if goal else None,
        scope=scope,
        scope_key=scope_key,
        conversation_uid=chat_uid,
        folder_uid=None,
        last_parent_order=0,
    )
    session.add(conversation)
    with serialize_writes():
        session.commit()
    return conversation


def discard_conversation(
    session: Session, conversation: AiConversation, *, folder_name: str
) -> None:
    """質問ごとに使い捨てる会話を削除し、一覧で削除を確認する。失敗しても呼び出し元の
    戻り値（既に得られた回答）は失わない。

    ヘルプAIアシスタント・目標相談チャットで共通の後始末処理（CODING_RULES.md DRYの原則。
    元はヘルプ側にのみ実装されていた、S09で抽出）。開発キットの削除の戻り値は信頼しない
    （NewtonX利用ナレッジ3.2）ため、削除後にフォルダのチャット一覧で残っていないかを
    確認する。残っていた場合はログに残し、会話行は削除する（利用者の画面には影響させない）。

    呼び出し元の`finally`から呼ばれる想定のため、ここで例外を外へ出すと、既に得られた
    回答そのものが失われる（`finally`内の例外が呼び出し元の正常な戻り値を上書きするため）。
    SQLiteの書き込みロック競合等の後始末自体の失敗でこれが起きないよう、ここでは例外を
    外へ出さない。
    """
    try:
        chat_uid = conversation.conversation_uid
        try:
            ai_client.delete_chat(session, chat_uid=chat_uid)
            remains = ai_client.chat_listed_in_folder(
                session, folder_name=folder_name, chat_uid=chat_uid
            )
        except AiError:
            remains = True
        if remains:
            logger.warning("質問ごとのチャットが削除されませんでした（chat_uid=%s）", chat_uid)
        session.delete(conversation)
        with serialize_writes():
            session.commit()
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("質問ごとのチャットの後始末に失敗しました（会話行が残存の可能性）")
