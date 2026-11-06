"""テーマ累積系機能（振り返り・復習クイズ）が共有するAI送信ヘルパー。

recap_generation_service（振り返りの分類・本文更新）とquiz_generation_service
（復習クイズ生成）は、いずれも「資格試験・読書の目標について、週次要約用の既存アシスタントを
カテゴリ別に流用し、テーマ単位の会話でプロンプトを送信する」という同一の手順を持つため、
ここへ1箇所に集約する（CODING_RULES.md DRYの原則）。
"""

from sqlalchemy.orm import Session

from app.ai import conversation as ai_conversation
from app.ai import orchestration as ai_orchestration
from app.ai import prompt_builder
from app.constants.app_setting_keys import (
    AI_ASSISTANT_UID_WEEKLY_SUMMARY,
    AI_ASSISTANT_UID_WEEKLY_SUMMARY_READING,
)
from app.constants.enums import AiPurpose, ConversationScope, GoalCategory
from app.models.goal import Goal
from app.services import setting_reader
from app.services.exceptions import RecapPromptTooLongError

#: 目標種別ごとの既存アシスタント（新しい設定項目は増やさない。週次要約用を流用する。
#: recap・復習クイズで共有）。
ASSISTANT_KEY_BY_CATEGORY = {
    GoalCategory.EXAM: AI_ASSISTANT_UID_WEEKLY_SUMMARY,
    GoalCategory.READING: AI_ASSISTANT_UID_WEEKLY_SUMMARY_READING,
}


def send_theme_scoped_prompt(
    session: Session,
    goal: Goal,
    purpose: AiPurpose,
    scope: ConversationScope,
    variables: dict[str, str],
    *,
    scope_key: str,
    title: str,
) -> str:
    """テーマ単位の会話でプロンプトを組み立てて送信し、応答本文を返す。

    上限超過時は送信せず`RecapPromptTooLongError`を送出する（切り詰めない。recap・
    復習クイズ共通の方針）。
    """
    template_body = ai_orchestration.load_template_body(session, purpose)
    max_chars = ai_orchestration.get_max_prompt_chars(session)
    built = prompt_builder.build_simple(template_body, variables, max_chars)
    if built.was_truncated:
        raise RecapPromptTooLongError(f"prompt exceeds the limit: {purpose} ({title})")
    assistant_uid = setting_reader.get_str(session, ASSISTANT_KEY_BY_CATEGORY[goal.category])
    conversation = ai_conversation.ensure_conversation(
        session,
        goal=goal,
        scope=scope,
        scope_key=scope_key,
        assistant_uid=assistant_uid,
        title=title,
    )
    result = ai_orchestration.send_and_log(
        session,
        purpose=purpose,
        conversation=conversation,
        prompt_text=built.text,
        prompt_chars=built.prompt_chars,
        was_truncated=built.was_truncated,
    )
    return result.response_text
