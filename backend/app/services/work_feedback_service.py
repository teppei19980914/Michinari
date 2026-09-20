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
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai import conversation as ai_conversation
from app.ai import orchestration as ai_orchestration
from app.ai import prompt_builder
from app.constants.app_setting_keys import (
    AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK,
    AI_PERSPECTIVE_SUGGESTION_MIN_RECORDS,
    AI_WORK_RECENT_LOG_DAYS,
    SUMMARY_INJECT_WEEKS,
)
from app.constants.enums import AiPurpose, ChatRole, ConversationScope, GoalCategory
from app.models.goal import Goal
from app.models.record import ChatMessage, DailyRecord
from app.services import ai_context_service, goal_service, record_service, setting_reader
from app.services.exceptions import ValidationError
from app.services.record_service import WorkLogItem

_ACTION_LABEL = "日次報告フィードバック"
#: {{recent_work_logs}}が空（対象案件なし、または直近recent_days日分に業務記録なし）の場合の
#: 表示（17.8）。ai_context_service.build_recent_work_logs_entriesは整形前のlist[DatedLogEntry]
#: を返すため、空の場合の文言は呼び出し側（prompt_builder.build_with_degradable_entries）が持つ
#: この定数を使う（CLAUDE.md DRYの原則。reading_feedback_serviceの_NO_RECENT_RECALLS_TEXTと
#: 同じ形）。
_NO_RECENT_WORK_LOGS_TEXT = "（直近の業務記録はありません）"
#: {{weekly_summaries}}が空（週次要約が1件も無い）場合の表示（17.8、L-11）。
_NO_OLDER_WEEKLY_SUMMARIES_TEXT = "（まだ週次要約はありません）"


def _ensure_active_work_goal(goal: Goal) -> None:
    if goal.category != GoalCategory.WORK:
        raise ValidationError(f"仕事目標（category=WORK）にのみ{_ACTION_LABEL}を実行できます")
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
) -> WorkChatOutcome:
    """AI対話を1往復実行する（データ構造編6.2 POST /records/{date}/work-chat）。

    Phase26で日次フィードバックを目標単位の会話へ分離した。goal_idで指定された1目標
    （＝1案件）のみを対象とする（未決事項L-07の解消方針転換）。
    """
    if target_date > today:
        raise ValidationError("未来日のAI対話はできません")

    goal = goal_service.get_goal(session, goal_id)
    _ensure_active_work_goal(goal)

    record = record_service.ensure_daily_record(session, target_date)
    work_assignments_by_id = record_service.load_work_assignments_by_id(
        session, {item.work_assignment_id for item in work_log_items}
    )
    # 選択中の目標（案件）宛ての業務記録のみを対象とする（他の仕事目標の下書きが
    # プロンプトへ混入しないようにする、Phase26）。
    work_log_items = [
        item
        for item in work_log_items
        if work_assignments_by_id[item.work_assignment_id].goal_id == goal.id
    ]

    active_work_assignments = ai_context_service.list_active_work_assignments([goal])
    recent_days = setting_reader.get_int(session, AI_WORK_RECENT_LOG_DAYS)
    inject_weeks = setting_reader.get_int(session, SUMMARY_INJECT_WEEKS)
    # L-11: period_startは直近の窓に絞らず目標開始日まで広げ、窓の外側（より過去）に
    # ある週次要約もlimit=inject_weeks件まで遡って見せつつ、直近の窓のうち既に週次要約が
    # 生成済みの週は圧縮表現へ、それ以外は生ログのまま注入する
    # （2026-09-16、reading_feedback_serviceと同じ是正。理由もそちらのコメント参照）。
    compressed = ai_context_service.resolve_weekly_compressed_period(
        session,
        goal,
        period_start=goal.start_date,
        period_end=target_date - dt.timedelta(days=1),
        limit=inject_weeks,
    )
    recent_work_logs_entries = ai_context_service.exclude_covered_dates(
        ai_context_service.build_recent_work_logs_entries(
            session, active_work_assignments, target_date, recent_days
        ),
        compressed.covered_ranges,
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

    reported_count = record_service.count_reported_records_before(
        session, GoalCategory.WORK, target_date
    )
    min_records = setting_reader.get_int(session, AI_PERSPECTIVE_SUGGESTION_MIN_RECORDS)
    perspective_suggestion = ai_context_service.build_perspective_suggestion_instruction(
        GoalCategory.WORK, reported_count < min_records
    )

    context = prompt_builder.DegradableFeedbackContext(
        fixed_variables={
            "today": target_date.isoformat(),
            "work_summary": ai_context_service.build_daily_work_summary_text(
                active_work_assignments, today
            ),
            "today_work": ai_context_service.build_today_work_text(
                work_log_items, work_assignments_by_id
            ),
            "perspective_suggestion": perspective_suggestion,
        },
        stages=[
            prompt_builder.DegradableEntryStage(
                key="weekly_summaries",
                entries=compressed.weekly_summary_entries,
                empty_text=_NO_OLDER_WEEKLY_SUMMARIES_TEXT,
            ),
            prompt_builder.DegradableEntryStage(
                key="recent_work_logs",
                entries=recent_work_logs_entries,
                empty_text=_NO_RECENT_WORK_LOGS_TEXT,
            ),
        ],
        conversation_history=history,
    )

    template_body = ai_orchestration.load_template_body(session, AiPurpose.DAILY_FEEDBACK_WORK)
    max_chars = ai_orchestration.get_max_prompt_chars(session)
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

    next_sequence = record_service.next_chat_sequence(session, record.id)
    if message:
        session.add(
            ChatMessage(
                daily_record_id=record.id,
                goal_id=goal.id,
                purpose=AiPurpose.DAILY_FEEDBACK_WORK,
                role=ChatRole.USER,
                content=message,
                sequence=next_sequence,
            )
        )
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
    session.flush()

    return WorkChatOutcome(
        daily_record=record,
        assistant_message=assistant_message,
        was_truncated=build_result.was_truncated,
    )
