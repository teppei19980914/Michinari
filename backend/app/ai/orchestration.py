"""AI呼び出しの共通オーケストレーション（送信→通信ログ記録、テンプレート読み出し）。

daily_feedback_service・daily_message_service・weekly_summary_serviceの3系統は、
「プロンプトテンプレートを読む→送信する→ai_logへ記録する」という手順が共通している
（差異は注入する変数の組み立て＝業務判断のみ）。この手順自体は技術的な通信処理であり
業務判断を含まないため、ai/パッケージに置く（データ構造編8.1）。
"""

from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.ai import logger as ai_logger
from app.ai import rate_limiter
from app.constants.app_setting_keys import AI_MAX_PROMPT_CHARS, AI_MIN_INTERVAL_SECONDS
from app.constants.enums import AiPurpose
from app.models.ai import AiConversation
from app.models.setting import PromptTemplate
from app.services import setting_reader
from app.services.exceptions import DomainError, ValidationError


def load_template_body(session: Session, purpose: AiPurpose) -> str:
    """prompt_templateからテンプレート本文を読む（CLAUDE.md「プロンプトはデータベースから読む」）。"""
    template = session.query(PromptTemplate).filter_by(purpose=purpose.value).first()
    if template is None:
        raise ValidationError(f"プロンプトテンプレート({purpose.value})が未初期化です")
    return template.body


def get_max_prompt_chars(session: Session) -> int:
    return setting_reader.get_int(session, AI_MAX_PROMPT_CHARS)


def send_and_log(
    session: Session,
    *,
    purpose: AiPurpose,
    conversation: AiConversation,
    prompt_text: str,
    prompt_chars: int,
    was_truncated: bool,
) -> ai_client.SendResult:
    """呼び出し間隔を守って送信し、成否によらずai_logへ記録する（16.4・16.8）。

    失敗時はここでcommitする。呼び出し元（API層）は正常時のみcommitするため、
    commitしない限りこのエラー記録自体がロールバックで失われる（16.8「全ての呼び出しに
    ついてai_logにレコードを追加する」）。成功時はlast_parent_orderを更新する
    （v0.10.5では文脈維持に使用できないが、将来の開発キット改修に備えた記録として、
    16.3.1）。
    """
    rate_limiter.wait_for_interval(setting_reader.get_int(session, AI_MIN_INTERVAL_SECONDS))

    try:
        send_result = ai_client.send_message(
            session, chat_uid=conversation.conversation_uid, message=prompt_text
        )
    except DomainError as exc:
        ai_logger.record_call(
            session,
            purpose=purpose,
            conversation_uid=conversation.conversation_uid,
            request_body=prompt_text,
            response_body=None,
            prompt_chars=prompt_chars,
            was_truncated=was_truncated,
            latency_ms=None,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        session.commit()
        raise

    conversation.last_parent_order += 1
    session.flush()

    ai_logger.record_call(
        session,
        purpose=purpose,
        conversation_uid=conversation.conversation_uid,
        request_body=prompt_text,
        response_body=send_result.response_text,
        prompt_chars=prompt_chars,
        was_truncated=was_truncated,
        latency_ms=send_result.latency_ms,
        error_type=None,
        error_message=None,
    )
    return send_result
