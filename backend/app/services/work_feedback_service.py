"""仕事日次報告フィードバック（AI対話）の実行（設計書 ロジック・プロンプト編16〜17.8、
データ構造編6.2 POST /records/{date}/work-chat、実装フェーズ分割計画書Phase22）。

daily_feedback_service.py（資格試験用）・reading_feedback_service.py（読書用）と対になる
仕事版。用途と日付ごとに会話を分離する既存方針（16.3）に従い、AiPurpose.DAILY_FEEDBACK_WORK
／ConversationScope.DAILY_FEEDBACK_WORKという別の用途として扱うため、同日に資格試験・読書の
日次報告フィードバックが行われていても文脈が混入しない。

実績はこの時点ではまだ確定（finalize）されていない場合があるため、DBではなくリクエストで
受け取った下書きの値をプロンプトへ注入する（daily_feedback_service・reading_feedback_service
と同じ設計。AI呼び出しが失敗しても入力が失われない、16.7）。
"""

import datetime as dt
import secrets
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai import conversation as ai_conversation
from app.ai import orchestration as ai_orchestration
from app.ai import prompt_builder, question_safety
from app.constants.app_setting_keys import (
    AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK,
    AI_PERSPECTIVE_SUGGESTION_MIN_RECORDS,
)
from app.constants.enums import AiPurpose, ChatRole, ConversationScope, GoalCategory
from app.models.attachment import ChatMessageAttachment
from app.models.goal import Goal
from app.models.record import ChatMessage, DailyRecord
from app.services import (
    ai_context_common,
    ai_context_work,
    attachment_service,
    goal_service,
    record_service_common,
    record_service_work,
    setting_reader,
)
from app.services.exceptions import DailyFeedbackPromptTooLongError, ValidationError
from app.services.record_service_work import WorkLogItem

_ACTION_LABEL = "daily report feedback"
#: {{recent_work_logs}}が空（対象案件なし、または対象期間に業務記録なし）の場合の
#: 表示（17.8）。ai_context_work.build_recent_work_logs_entriesは整形前のlist[DatedLogEntry]
#: を返すため、空の場合の文言は呼び出し側（prompt_builder.build_with_degradable_entries）が持つ
#: この定数を使う（CLAUDE.md DRYの原則。reading_feedback_serviceの_NO_RECENT_RECALLS_TEXTと
#: 同じ形）。
_NO_RECENT_WORK_LOGS_TEXT = "（直近の業務記録はありません）"
#: {{weekly_summaries}}が空（週次要約が1件も無い）場合の表示（17.8、L-11）。
_NO_OLDER_WEEKLY_SUMMARIES_TEXT = "（まだ週次要約はありません）"


def _ensure_active_work_goal(goal: Goal) -> None:
    if goal.category != GoalCategory.WORK:
        raise ValidationError(f"{_ACTION_LABEL} can only be run for WORK goals")
    goal_service.ensure_goal_active(goal, action_label=_ACTION_LABEL)


@dataclass(frozen=True)
class WorkChatOutcome:
    daily_record: DailyRecord
    assistant_message: ChatMessage
    was_truncated: bool


def send_work_feedback(
    session: Session,
    *,
    goal_id: int,
    target_date: dt.date,
    today: dt.date,
    message: str | None,
    work_log_items: list[WorkLogItem],
    attachment_ids: list[int] | None = None,
) -> WorkChatOutcome:
    """AI対話を1往復実行する（データ構造編6.2 POST /records/{date}/work-chat）。

    Phase26で日次フィードバックを目標単位の会話へ分離した。goal_idで指定された1目標
    （＝1案件）のみを対象とする（未決事項L-07の解消方針転換）。

    `attachment_ids`は利用者が選択した添付ファイル（開発Todo_添付ファイル機能_v1.0 A1・A8）。
    """
    if target_date > today:
        raise ValidationError("Cannot start an AI conversation for a future date")

    goal = goal_service.get_goal(session, goal_id)
    _ensure_active_work_goal(goal)
    attachments = attachment_service.get_many_or_raise(session, attachment_ids or [])

    record = record_service_common.ensure_daily_record(session, target_date)
    work_assignments_by_id = record_service_work.load_work_assignments_by_id(
        session, {item.work_assignment_id for item in work_log_items}
    )
    # 選択中の目標（案件）宛ての業務記録のみを対象とする（他の仕事目標の下書きが
    # プロンプトへ混入しないようにする、Phase26）。
    work_log_items = [
        item
        for item in work_log_items
        if work_assignments_by_id[item.work_assignment_id].goal_id == goal.id
    ]

    active_work_assignments = ai_context_work.list_active_work_assignments([goal])
    # S04 G1：目標開始日〜対象日の前日の全期間を対象とし、件数・週数の上限を設けない
    # （2026-09-16のL-11是正から、reading_feedback_serviceと同じ考え方でさらに踏み込む）。
    period_end = target_date - dt.timedelta(days=1)
    past_records = ai_context_common.build_past_record_entries(
        session,
        goal,
        period_start=goal.start_date,
        period_end=period_end,
        raw_entries=ai_context_work.build_recent_work_logs_entries(
            session, active_work_assignments, period_start=goal.start_date, period_end=period_end
        ),
    )

    # 対話履歴への注入はpurpose・goal_idで絞り込む（daily_feedback_service・reading_feedback_service
    # と同じ理由。ChatMessageモデルのdocstring参照）。goal_id=NULLの行は移行前のレガシー
    # メッセージのため対話履歴には含めない（Phase26）。
    existing_messages = (
        session.query(ChatMessage)
        .filter(
            ChatMessage.daily_record_id == record.id,
            ChatMessage.purpose == AiPurpose.DAILY_FEEDBACK_WORK,
            ChatMessage.goal_id == goal.id,
        )
        .order_by(ChatMessage.sequence)
        .all()
    )
    history = [prompt_builder.ChatTurn(role=m.role, content=m.content) for m in existing_messages]
    if message:
        history.append(prompt_builder.ChatTurn(role=ChatRole.USER, content=message))

    reported_count = record_service_common.count_reported_records_before(
        session, GoalCategory.WORK, target_date
    )
    min_records = setting_reader.get_int(session, AI_PERSPECTIVE_SUGGESTION_MIN_RECORDS)
    perspective_suggestion = ai_context_common.build_perspective_suggestion_instruction(
        GoalCategory.WORK, reported_count < min_records
    )

    # 添付ファイルの文字数は段階的縮退の対象外（当日入力と同等、開発Todo_添付ファイル機能_v1.0
    # A6）。禁止語は保存後に追加される可能性があるため送信直前に再照合する（P12②）。
    attachment_block = attachment_service.build_attachment_block(session, attachments)
    nonce = secrets.token_hex(question_safety.NONCE_BYTES)

    context = prompt_builder.DegradableFeedbackContext(
        fixed_variables={
            "today": target_date.isoformat(),
            "work_summary": ai_context_work.build_daily_work_summary_text(
                active_work_assignments, today
            ),
            "today_work": ai_context_work.build_today_work_text(
                work_log_items, work_assignments_by_id
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
                key="recent_work_logs",
                entries=past_records.raw_entries,
                empty_text=_NO_RECENT_WORK_LOGS_TEXT,
            ),
        ],
        conversation_history=history,
    )

    template_body = ai_orchestration.load_template_body(session, AiPurpose.DAILY_FEEDBACK_WORK)
    max_chars = ai_orchestration.get_max_prompt_chars(session)
    # S04決定事項D1・D9：当日の入力（業務記録・対話）は縮退しない。過去の記録を全て削っても
    # 上限を超える場合は、切り詰めずに送信を中止する（NewtonX利用ナレッジ「切り詰めない」）。
    if prompt_builder.exceeds_with_entries_emptied(template_body, context, max_chars):
        raise DailyFeedbackPromptTooLongError(f"prompt exceeds the limit: goal_id={goal.id}")
    build_result = prompt_builder.build_with_degradable_entries(template_body, context, max_chars)

    assistant_uid = setting_reader.get_str(session, AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK)
    conversation = ai_conversation.ensure_conversation(
        session,
        goal=goal,
        scope=ConversationScope.DAILY_FEEDBACK_WORK,
        scope_key=target_date.isoformat(),
        assistant_uid=assistant_uid,
        title=f"{target_date.isoformat()} 仕事日次報告（{goal.name}）",
    )

    send_result = ai_orchestration.send_and_log(
        session,
        purpose=AiPurpose.DAILY_FEEDBACK_WORK,
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
            purpose=AiPurpose.DAILY_FEEDBACK_WORK,
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
        purpose=AiPurpose.DAILY_FEEDBACK_WORK,
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

    return WorkChatOutcome(
        daily_record=record,
        assistant_message=assistant_message,
        was_truncated=build_result.was_truncated,
    )
