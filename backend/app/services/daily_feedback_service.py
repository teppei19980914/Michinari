"""日次報告フィードバック（AI対話）の実行（設計書 ロジック・プロンプト編16〜17.2、
データ構造編6.2 POST /records/{date}/chat、実装フェーズ分割計画書Phase5）。

実績・日記はこの時点ではまだ確定（finalize）されていない場合があるため、DBではなく
リクエストで受け取った下書きの値をプロンプトへ注入する。AI呼び出しが失敗しても
実績入力が失われないのは、本関数がstudy_logs/diaryを一切永続化しないことによる
（16.7、Phase4完了条件）。
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai import conversation as ai_conversation
from app.ai import orchestration as ai_orchestration
from app.ai import prompt_builder
from app.constants.app_setting_keys import AI_ASSISTANT_UID_DAILY_FEEDBACK, SUMMARY_INJECT_WEEKS
from app.constants.enums import AiPurpose, ChatRole, ConversationScope
from app.models.record import ChatMessage, DailyRecord
from app.services import (
    ai_context_service,
    calendar_service,
    goal_service,
    record_service,
    setting_reader,
)
from app.services.exceptions import ValidationError
from app.services.record_service import DiaryEntryItem, StudyLogItem


@dataclass(frozen=True)
class ChatOutcome:
    daily_record: DailyRecord
    assistant_message: ChatMessage
    was_truncated: bool


def send_daily_feedback(
    session: Session,
    *,
    target_date: dt.date,
    today: dt.date,
    message: str | None,
    study_log_items: list[StudyLogItem],
    diary_entries: list[DiaryEntryItem],
) -> ChatOutcome:
    """AI対話を1往復実行する（データ構造編6.2 POST /records/{date}/chat）。"""
    if target_date > today:
        raise ValidationError("未来日のAI対話はできません")

    record = record_service.ensure_daily_record(session, target_date)
    materials_by_id = record_service.load_materials_by_id(
        session, {item.material_id for item in study_log_items}
    )

    # 読書目標（category=READING）はexam_subject/materialを持たず、この日次報告フィードバック
    # は資格試験専用のプロンプト（AiPurpose.DAILY_FEEDBACK）であるため、EXAM目標のみに限定する
    # （読書用フィードバックはAiPurpose.DAILY_FEEDBACK_READINGとしてPhase16で別途実装する）。
    active_goals = ai_context_service.list_active_exam_goals(session)
    active_materials = ai_context_service.list_active_materials(active_goals)
    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)
    day_type = calendar_service.resolve_day_type(session, target_date, treat_holiday_as_buffer)

    # 複数目標が同時にACTIVEな場合の代表選定は設計書に明記がないため、
    # 目標ごとの内訳を列挙する（goal_summaryと同様の整理、Phase5実装判断）。
    if active_goals:
        load_coefficient_text = ", ".join(
            f"{goal.name}: "
            f"{calendar_service.resolve_load_coefficient(session, goal.id, target_date):.2f}"
            for goal in active_goals
        )
    else:
        load_coefficient_text = "算出不可（進行中の目標なし）"

    # 対話履歴への注入はpurposeで絞り込む。読書のDAILY_FEEDBACK_READING（Phase16）が
    # 同一daily_recordにchat_messageを持ちうるため、他用途の対話を文脈に混入させない。
    existing_messages = (
        session.query(ChatMessage)
        .filter(
            ChatMessage.daily_record_id == record.id,
            ChatMessage.purpose == AiPurpose.DAILY_FEEDBACK,
        )
        .order_by(ChatMessage.sequence)
        .all()
    )
    history = [
        prompt_builder.ChatTurn(role=m.role, content=m.content) for m in existing_messages
    ]
    # 本日最初のAI呼び出し（自由入力メッセージがまだ無い状態）は本日の記録内容自体への
    # フィードバック依頼として扱う（17.2の変数群で状況は伝わるため、対話履歴には積まない）。
    if message:
        history.append(prompt_builder.ChatTurn(role=ChatRole.USER, content=message))

    diary_body, diary_learned = ai_context_service.build_diary_text(diary_entries, active_goals)

    context = prompt_builder.DailyFeedbackContext(
        today=target_date.isoformat(),
        day_type=day_type.value,
        load_coefficient=load_coefficient_text,
        goal_summary=ai_context_service.build_goal_summary(active_goals, target_date),
        material_entries=ai_context_service.build_material_status_entries(
            session, active_materials, target_date, treat_holiday_as_buffer
        ),
        slot_summary=ai_context_service.build_slot_summary(
            session, active_materials, target_date
        ),
        buffer_usage_rate=ai_context_service.build_buffer_usage_rate_text(
            session, active_goals, target_date, treat_holiday_as_buffer
        ),
        today_logs=ai_context_service.build_today_logs_text(study_log_items, materials_by_id),
        diary_body=diary_body,
        diary_learned=diary_learned,
        weekly_summaries=ai_context_service.build_recent_weekly_summaries(
            session, active_goals, setting_reader.get_int(session, SUMMARY_INJECT_WEEKS)
        ),
        conversation_history=history,
    )

    template_body = ai_orchestration.load_template_body(session, AiPurpose.DAILY_FEEDBACK)
    max_chars = ai_orchestration.get_max_prompt_chars(session)
    build_result = prompt_builder.build_daily_feedback(template_body, context, max_chars)

    assistant_uid = setting_reader.get_str(session, AI_ASSISTANT_UID_DAILY_FEEDBACK)
    conversation = ai_conversation.ensure_conversation(
        session,
        goal=None,
        scope=ConversationScope.DAILY_FEEDBACK,
        scope_key=target_date.isoformat(),
        assistant_uid=assistant_uid,
        title=f"{target_date.isoformat()} 日次報告",
    )

    send_result = ai_orchestration.send_and_log(
        session,
        purpose=AiPurpose.DAILY_FEEDBACK,
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
                purpose=AiPurpose.DAILY_FEEDBACK,
                role=ChatRole.USER,
                content=message,
                sequence=next_sequence,
            )
        )
        next_sequence += 1

    assistant_message = ChatMessage(
        daily_record_id=record.id,
        purpose=AiPurpose.DAILY_FEEDBACK,
        role=ChatRole.ASSISTANT,
        content=send_result.response_text,
        sequence=next_sequence,
    )
    session.add(assistant_message)
    session.flush()

    return ChatOutcome(
        daily_record=record,
        assistant_message=assistant_message,
        was_truncated=build_result.was_truncated,
    )
