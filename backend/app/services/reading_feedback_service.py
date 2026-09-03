"""読書日次報告フィードバック（AI対話）の実行（設計書 ロジック・プロンプト編16〜17.6、
データ構造編6.2 POST /records/{date}/reading-chat、実装フェーズ分割計画書Phase16）。

daily_feedback_service.py（資格試験用）と対になる読書版。用途と日付ごとに会話を分離する
既存方針（16.3）に従い、AiPurpose.DAILY_FEEDBACK_READING／ConversationScope.
DAILY_FEEDBACK_READINGという別の用途として扱うため、同日に資格試験の日次報告フィード
バックが行われていても文脈が混入しない（conversation_history・chat_message.purposeの
両方でDAILY_FEEDBACKとは分離される）。

実績・想起はこの時点ではまだ確定（finalize）されていない場合があるため、DBではなく
リクエストで受け取った下書きの値をプロンプトへ注入する（daily_feedback_serviceと同じ設計。
AI呼び出しが失敗しても入力が失われない、16.7）。
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai import conversation as ai_conversation
from app.ai import orchestration as ai_orchestration
from app.ai import prompt_builder
from app.constants.app_setting_keys import (
    AI_ASSISTANT_UID_DAILY_FEEDBACK_READING,
    AI_READING_RECALL_RECENT_DAYS,
)
from app.constants.enums import AiPurpose, ChatRole, ConversationScope
from app.models.record import ChatMessage, DailyRecord
from app.services import ai_context_service, record_service, setting_reader
from app.services.exceptions import ValidationError
from app.services.record_service import ReadingLogItem


@dataclass(frozen=True)
class ReadingChatOutcome:
    daily_record: DailyRecord
    assistant_message: ChatMessage
    was_truncated: bool


def send_reading_feedback(
    session: Session,
    *,
    target_date: dt.date,
    today: dt.date,
    message: str | None,
    reading_log_items: list[ReadingLogItem],
) -> ReadingChatOutcome:
    """AI対話を1往復実行する（データ構造編6.2 POST /records/{date}/reading-chat）。"""
    if target_date > today:
        raise ValidationError("未来日のAI対話はできません")

    record = record_service.ensure_daily_record(session, target_date)
    books_by_id = record_service.load_books_by_id(
        session, {item.book_id for item in reading_log_items}
    )

    active_reading_goals = ai_context_service.list_active_reading_goals(session)
    active_books = ai_context_service.list_active_books(active_reading_goals)
    recent_days = setting_reader.get_int(session, AI_READING_RECALL_RECENT_DAYS)

    # 対話履歴への注入はpurposeで絞り込む（daily_feedback_serviceと同じ理由。ChatMessage
    # モデルのdocstring参照）。
    existing_messages = (
        session.query(ChatMessage)
        .filter(
            ChatMessage.daily_record_id == record.id,
            ChatMessage.purpose == AiPurpose.DAILY_FEEDBACK_READING,
        )
        .order_by(ChatMessage.sequence)
        .all()
    )
    history = [
        prompt_builder.ChatTurn(role=m.role, content=m.content) for m in existing_messages
    ]
    if message:
        history.append(prompt_builder.ChatTurn(role=ChatRole.USER, content=message))

    variables = {
        "today": target_date.isoformat(),
        "book_summary": ai_context_service.build_daily_book_summary_text(active_books, today),
        "today_recall": ai_context_service.build_today_recall_text(
            reading_log_items, books_by_id
        ),
        "recent_recalls": ai_context_service.build_recent_recalls_text(
            session, active_books, target_date, recent_days
        ),
        "conversation_history": prompt_builder.format_conversation_history(history),
    }

    template_body = ai_orchestration.load_template_body(
        session, AiPurpose.DAILY_FEEDBACK_READING
    )
    max_chars = ai_orchestration.get_max_prompt_chars(session)
    build_result = prompt_builder.build_simple(template_body, variables, max_chars)

    assistant_uid = setting_reader.get_str(session, AI_ASSISTANT_UID_DAILY_FEEDBACK_READING)
    conversation = ai_conversation.ensure_conversation(
        session,
        goal=None,
        scope=ConversationScope.DAILY_FEEDBACK_READING,
        scope_key=target_date.isoformat(),
        assistant_uid=assistant_uid,
        title=f"{target_date.isoformat()} 読書日次報告",
    )

    send_result = ai_orchestration.send_and_log(
        session,
        purpose=AiPurpose.DAILY_FEEDBACK_READING,
        conversation=conversation,
        prompt_text=build_result.text,
        prompt_chars=build_result.prompt_chars,
        was_truncated=build_result.was_truncated,
    )

    next_sequence = record_service.next_chat_sequence(session, record.id)
    if message:
        session.add(
            ChatMessage(
                daily_record_id=record.id,
                purpose=AiPurpose.DAILY_FEEDBACK_READING,
                role=ChatRole.USER,
                content=message,
                sequence=next_sequence,
            )
        )
        next_sequence += 1

    assistant_message = ChatMessage(
        daily_record_id=record.id,
        purpose=AiPurpose.DAILY_FEEDBACK_READING,
        role=ChatRole.ASSISTANT,
        content=send_result.response_text,
        sequence=next_sequence,
    )
    session.add(assistant_message)
    session.flush()

    return ReadingChatOutcome(
        daily_record=record,
        assistant_message=assistant_message,
        was_truncated=build_result.was_truncated,
    )
