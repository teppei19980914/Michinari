"""AI呼び出しの共通オーケストレーション（送信→通信ログ記録、テンプレート読み出し）。

daily_feedback_service・daily_message_service・weekly_summary_serviceの3系統は、
「プロンプトテンプレートを読む→送信する→ai_logへ記録する」という手順が共通している
（差異は注入する変数の組み立て＝業務判断のみ）。この手順自体は技術的な通信処理であり
業務判断を含まないため、ai/パッケージに置く（データ構造編8.1）。
"""

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.ai import logger as ai_logger
from app.ai import rate_limiter
from app.constants.app_setting_keys import (
    AI_LANGUAGE_DIRECTIVE_EN,
    AI_LANGUAGE_DIRECTIVE_JA,
    AI_MAX_PROMPT_CHARS,
    AI_MIN_INTERVAL_SECONDS,
)
from app.constants.enums import AiPurpose
from app.database import serialize_writes
from app.models.ai import AiConversation
from app.models.setting import PromptTemplate
from app.services import setting_reader
from app.services.exceptions import DomainError, ValidationError


def load_template_body(session: Session, purpose: AiPurpose) -> str:
    """prompt_templateからテンプレート本文を読む（CLAUDE.md「プロンプトはデータベースから読む」）。"""
    template = session.query(PromptTemplate).filter_by(purpose=purpose.value).first()
    if template is None:
        raise ValidationError(f"Prompt template not initialized: purpose={purpose.value}")
    return template.body


def get_max_prompt_chars(session: Session) -> int:
    return setting_reader.get_int(session, AI_MAX_PROMPT_CHARS)


def _append_language_directive(session: Session, prompt_text: str) -> str:
    """表示言語に応じた応答言語の指示をプロンプト末尾へ追記する（日英i18n対応、2026-10）。

    `prompt_template`の本文自体は言語別に複製せず1つのまま、末尾にこの指示を追記する方式
    とした（`DAILY_FEEDBACK`等のテンプレートは出力を厳密に構造化させる指示を持たないため、
    自然文の指示追記で足りると判断。2026-10-09の設計検討）。指示文自体は`prompt_template`
    ではなく`app_setting`に置く（`PromptTemplateSection`の設定画面が`prompt_template`の
    全行を無条件に編集可能なテンプレート一覧として表示するため、そちらに置くと意図せず
    露出してしまう）。切り詰め後の`prompt_text`（`AI_MAX_PROMPT_CHARS`適用後）に追記する
    ため、追記分が上限から溢れることはない。
    """
    directive_key = (
        AI_LANGUAGE_DIRECTIVE_EN
        if setting_reader.is_english_locale(session)
        else AI_LANGUAGE_DIRECTIVE_JA
    )
    directive = setting_reader.get_str(session, directive_key)
    return f"{prompt_text}\n\n{directive}"


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

    成否によらずここでcommitする。AI応答の待機中に書き込みトランザクションを保持しない
    ため（CODING_RULES.md「AI通信とトランザクション」）、呼び出し元の後続処理が失敗しても
    通信記録は失われない（16.8「全ての呼び出しについてai_logにレコードを追加する」）。
    成功時はlast_parent_orderを更新する
    （v0.10.5では文脈維持に使用できないが、将来の開発キット改修に備えた記録として、
    16.3.1）。この更新とログ記録は付随的な記帳であり、SQLiteの書き込みロック競合
    （他のAI生成処理と重なった場合の「database is locked」、2026-10-09の不具合）で
    失敗しても、既に得られたAI応答を失わないよう、個別にロールバックして続行する。
    `database.serialize_writes()`で先に直列化することで、この競合自体が起きる頻度を
    減らす（SQLite自身のbusy_timeoutに委ねるより先に、アプリ内で待たせる）。
    """
    rate_limiter.wait_for_interval(setting_reader.get_int(session, AI_MIN_INTERVAL_SECONDS))

    final_prompt_text = _append_language_directive(session, prompt_text)
    conversation_uid = conversation.conversation_uid
    try:
        send_result = ai_client.send_message(
            session, chat_uid=conversation_uid, message=final_prompt_text
        )
    except DomainError as exc:
        try:
            with serialize_writes():
                ai_logger.record_call(
                    session,
                    purpose=purpose,
                    conversation_uid=conversation_uid,
                    request_body=final_prompt_text,
                    response_body=None,
                    prompt_chars=prompt_chars,
                    was_truncated=was_truncated,
                    latency_ms=None,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                session.commit()
        except OperationalError:
            session.rollback()
        raise

    try:
        conversation.last_parent_order += 1
        with serialize_writes():
            session.flush()
    except OperationalError:
        session.rollback()

    try:
        with serialize_writes():
            ai_logger.record_call(
                session,
                purpose=purpose,
                conversation_uid=conversation_uid,
                request_body=final_prompt_text,
                response_body=send_result.response_text,
                prompt_chars=prompt_chars,
                was_truncated=was_truncated,
                latency_ms=send_result.latency_ms,
                error_type=None,
                error_message=None,
            )
            session.commit()
    except OperationalError:
        session.rollback()
    return send_result
