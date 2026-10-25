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
import secrets
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai import conversation as ai_conversation
from app.ai import orchestration as ai_orchestration
from app.ai import prompt_builder, question_safety
from app.constants.app_setting_keys import (
    AI_ASSISTANT_UID_DAILY_FEEDBACK_READING,
    AI_PERSPECTIVE_SUGGESTION_MIN_RECORDS,
)
from app.constants.enums import AiPurpose, ChatRole, ConversationScope, GoalCategory
from app.models.attachment import ChatMessageAttachment
from app.models.goal import Goal
from app.models.record import ChatMessage, DailyRecord
from app.services import (
    ai_context_common,
    ai_context_reading,
    attachment_service,
    goal_service,
    record_service_common,
    record_service_reading,
    setting_reader,
)
from app.services.exceptions import DailyFeedbackPromptTooLongError, ValidationError
from app.services.record_service_reading import ReadingLogItem

_ACTION_LABEL = "daily report feedback"
#: {{recent_recalls}}が空（対象書籍なし、または対象期間に想起記録なし）の場合の表示
#: （17.6）。ai_context_reading.build_recent_recalls_entriesは整形前のlist[DatedLogEntry]を
#: 返すため、空の場合の文言は呼び出し側（prompt_builder.build_with_degradable_entries）が持つ
#: この定数を使う（CLAUDE.md DRYの原則）。
_NO_RECENT_RECALLS_TEXT = "（直近の想起記録はありません）"
#: {{weekly_summaries}}が空（週次要約が1件も無い）場合の表示（17.6、L-11）。
_NO_OLDER_WEEKLY_SUMMARIES_TEXT = "（まだ週次要約はありません）"


def _ensure_active_reading_goal(goal: Goal) -> None:
    if goal.category != GoalCategory.READING:
        raise ValidationError(f"{_ACTION_LABEL} can only be run for READING goals")
    goal_service.ensure_goal_active(goal, action_label=_ACTION_LABEL)


@dataclass(frozen=True)
class ReadingChatOutcome:
    daily_record: DailyRecord
    assistant_message: ChatMessage
    was_truncated: bool


def send_reading_feedback(
    session: Session,
    *,
    goal_id: int,
    target_date: dt.date,
    today: dt.date,
    message: str | None,
    reading_log_items: list[ReadingLogItem],
    attachment_ids: list[int] | None = None,
) -> ReadingChatOutcome:
    """AI対話を1往復実行する（データ構造編6.2 POST /records/{date}/reading-chat）。

    Phase26で日次フィードバックを目標単位の会話へ分離した。goal_idで指定された1目標
    （＝1冊）のみを対象とする（未決事項L-07の解消方針転換）。

    `attachment_ids`は利用者が選択した添付ファイル（開発Todo_添付ファイル機能_v1.0 A1・A8）。
    """
    if target_date > today:
        raise ValidationError("Cannot start an AI conversation for a future date")

    goal = goal_service.get_goal(session, goal_id)
    _ensure_active_reading_goal(goal)
    attachments = attachment_service.get_many_or_raise(session, attachment_ids or [])

    record = record_service_common.ensure_daily_record(session, target_date)
    books_by_id = record_service_reading.load_books_by_id(
        session, {item.book_id for item in reading_log_items}
    )
    # 選択中の目標（書籍）宛ての想起記録のみを対象とする（他の読書目標の下書きが
    # プロンプトへ混入しないようにする、Phase26）。
    reading_log_items = [
        item for item in reading_log_items if books_by_id[item.book_id].goal_id == goal.id
    ]

    active_books = ai_context_reading.list_active_books([goal])
    book = goal.book
    # S04 G1：目標開始日（読書はbook.start_date。goal.start_dateとは独立に変更できるため
    # 区別する、決定事項D6）〜対象日の前日の全期間を対象とし、件数・週数の上限を設けない。
    period_end = target_date - dt.timedelta(days=1)
    past_records = ai_context_common.build_past_record_entries(
        session,
        goal,
        period_start=book.start_date,
        period_end=period_end,
        raw_entries=ai_context_reading.build_recent_recalls_entries(
            session, active_books, period_start=book.start_date, period_end=period_end
        ),
    )

    # 対話履歴への注入はpurpose・goal_idで絞り込む（daily_feedback_serviceと同じ理由。
    # ChatMessageモデルのdocstring参照）。goal_id=NULLの行は移行前のレガシーメッセージ
    # のため対話履歴には含めない（Phase26）。
    existing_messages = (
        session.query(ChatMessage)
        .filter(
            ChatMessage.daily_record_id == record.id,
            ChatMessage.purpose == AiPurpose.DAILY_FEEDBACK_READING,
            ChatMessage.goal_id == goal.id,
        )
        .order_by(ChatMessage.sequence)
        .all()
    )
    history = [prompt_builder.ChatTurn(role=m.role, content=m.content) for m in existing_messages]
    if message:
        history.append(prompt_builder.ChatTurn(role=ChatRole.USER, content=message))

    reported_count = record_service_common.count_reported_records_before(
        session, GoalCategory.READING, target_date
    )
    min_records = setting_reader.get_int(session, AI_PERSPECTIVE_SUGGESTION_MIN_RECORDS)
    perspective_suggestion = ai_context_common.build_perspective_suggestion_instruction(
        GoalCategory.READING, reported_count < min_records
    )

    # 添付ファイルの文字数は段階的縮退の対象外（当日入力と同等、開発Todo_添付ファイル機能_v1.0
    # A6）。禁止語は保存後に追加される可能性があるため送信直前に再照合する（P12②）。
    attachment_block = attachment_service.build_attachment_block(session, attachments)
    nonce = secrets.token_hex(question_safety.NONCE_BYTES)

    context = prompt_builder.DegradableFeedbackContext(
        fixed_variables={
            "today": target_date.isoformat(),
            "book_summary": ai_context_reading.build_daily_book_summary_text(active_books, today),
            "today_recall": ai_context_reading.build_today_recall_text(
                reading_log_items, books_by_id
            ),
            "perspective_suggestion": perspective_suggestion,
            "attachments": attachment_block or prompt_builder.NO_ATTACHMENTS_TEXT,
            "nonce": nonce,
        },
        stages=[
            prompt_builder.DegradableEntryStage(
                key="weekly_summaries",
                entries=past_records.weekly_summary_entries,
                empty_text=_NO_OLDER_WEEKLY_SUMMARIES_TEXT,
            ),
            prompt_builder.DegradableEntryStage(
                key="recent_recalls",
                entries=past_records.raw_entries,
                empty_text=_NO_RECENT_RECALLS_TEXT,
            ),
        ],
        conversation_history=history,
    )

    template_body = ai_orchestration.load_template_body(session, AiPurpose.DAILY_FEEDBACK_READING)
    max_chars = ai_orchestration.get_max_prompt_chars(session)
    # S04決定事項D1・D9：当日の入力（想起・対話）は縮退しない。過去の記録を全て削っても
    # 上限を超える場合は、切り詰めずに送信を中止する（NewtonX利用ナレッジ「切り詰めない」）。
    if prompt_builder.exceeds_with_entries_emptied(template_body, context, max_chars):
        raise DailyFeedbackPromptTooLongError(f"prompt exceeds the limit: goal_id={goal.id}")
    build_result = prompt_builder.build_with_degradable_entries(template_body, context, max_chars)

    assistant_uid = setting_reader.get_str(session, AI_ASSISTANT_UID_DAILY_FEEDBACK_READING)
    conversation = ai_conversation.ensure_conversation(
        session,
        goal=goal,
        scope=ConversationScope.DAILY_FEEDBACK_READING,
        scope_key=target_date.isoformat(),
        assistant_uid=assistant_uid,
        title=f"{target_date.isoformat()} 読書日次報告（{goal.name}）",
    )

    send_result = ai_orchestration.send_and_log(
        session,
        purpose=AiPurpose.DAILY_FEEDBACK_READING,
        conversation=conversation,
        prompt_text=build_result.text,
        prompt_chars=build_result.prompt_chars,
        was_truncated=build_result.was_truncated,
    )

    next_sequence = record_service_common.next_chat_sequence(session, record.id)
    attachment_target_message: ChatMessage | None = None
    if message:
        user_message = ChatMessage(
            daily_record_id=record.id,
            goal_id=goal.id,
            purpose=AiPurpose.DAILY_FEEDBACK_READING,
            role=ChatRole.USER,
            content=message,
            sequence=next_sequence,
        )
        session.add(user_message)
        attachment_target_message = user_message
        next_sequence += 1

    assistant_message = ChatMessage(
        daily_record_id=record.id,
        goal_id=goal.id,
        purpose=AiPurpose.DAILY_FEEDBACK_READING,
        role=ChatRole.ASSISTANT,
        content=send_result.response_text,
        sequence=next_sequence,
    )
    session.add(assistant_message)
    if attachment_target_message is None:
        attachment_target_message = assistant_message
    session.flush()
    for attachment_id in attachment_ids or []:
        session.add(
            ChatMessageAttachment(
                chat_message_id=attachment_target_message.id, attachment_id=attachment_id
            )
        )
    session.flush()

    return ReadingChatOutcome(
        daily_record=record,
        assistant_message=assistant_message,
        was_truncated=build_result.was_truncated,
    )
