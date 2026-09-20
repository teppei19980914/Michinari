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
    AI_PERSPECTIVE_SUGGESTION_MIN_RECORDS,
    AI_READING_RECALL_RECENT_DAYS,
    SUMMARY_INJECT_WEEKS,
)
from app.constants.enums import AiPurpose, ChatRole, ConversationScope, GoalCategory
from app.models.goal import Goal
from app.models.record import ChatMessage, DailyRecord
from app.services import ai_context_service, goal_service, record_service, setting_reader
from app.services.exceptions import ValidationError
from app.services.record_service import ReadingLogItem

_ACTION_LABEL = "日次報告フィードバック"
#: {{recent_recalls}}が空（対象書籍なし、または直近recent_days日分に想起記録なし）の場合の表示
#: （17.6）。ai_context_service.build_recent_recalls_entriesは整形前のlist[DatedLogEntry]を
#: 返すため、空の場合の文言は呼び出し側（prompt_builder.build_with_degradable_entries）が持つ
#: この定数を使う（CLAUDE.md DRYの原則）。
_NO_RECENT_RECALLS_TEXT = "（直近の想起記録はありません）"
#: {{weekly_summaries}}が空（週次要約が1件も無い）場合の表示（17.6、L-11）。
_NO_OLDER_WEEKLY_SUMMARIES_TEXT = "（まだ週次要約はありません）"


def _ensure_active_reading_goal(goal: Goal) -> None:
    if goal.category != GoalCategory.READING:
        raise ValidationError(f"読書目標（category=READING）にのみ{_ACTION_LABEL}を実行できます")
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
) -> ReadingChatOutcome:
    """AI対話を1往復実行する（データ構造編6.2 POST /records/{date}/reading-chat）。

    Phase26で日次フィードバックを目標単位の会話へ分離した。goal_idで指定された1目標
    （＝1冊）のみを対象とする（未決事項L-07の解消方針転換）。
    """
    if target_date > today:
        raise ValidationError("未来日のAI対話はできません")

    goal = goal_service.get_goal(session, goal_id)
    _ensure_active_reading_goal(goal)

    record = record_service.ensure_daily_record(session, target_date)
    books_by_id = record_service.load_books_by_id(
        session, {item.book_id for item in reading_log_items}
    )
    # 選択中の目標（書籍）宛ての想起記録のみを対象とする（他の読書目標の下書きが
    # プロンプトへ混入しないようにする、Phase26）。
    reading_log_items = [
        item for item in reading_log_items if books_by_id[item.book_id].goal_id == goal.id
    ]

    active_books = ai_context_service.list_active_books([goal])
    recent_days = setting_reader.get_int(session, AI_READING_RECALL_RECENT_DAYS)
    inject_weeks = setting_reader.get_int(session, SUMMARY_INJECT_WEEKS)
    # L-11: period_startは直近の窓に絞らず目標開始日まで広げ、窓の外側（より過去）に
    # ある週次要約もlimit=inject_weeks件まで遡って見せる（要約による過去の経緯の反映）。
    # 同時に、直近の窓のうち既に週次要約が生成済みの週は圧縮表現へ、それ以外は生ログの
    # まま注入することで、要約による文字数削減の効果が生ログ側にも及ぶ（2026-09-16是正。
    # 従来はrecent_recallsが常に窓いっぱいの生ログを返し、weekly_summariesは窓より前の
    # 分を追加するだけだったため、週次要約が増えてもプロンプト全体は縮まらなかった。
    # またperiod_startを窓の開始日に限定すると、窓より過去の週次要約が一切見えなくなり
    # 従来あった「直近の窓を越えた過去の経緯の反映」機能が失われるため、limitで歯止め
    # をかけつつperiod_startは目標開始日まで広げる）。
    compressed = ai_context_service.resolve_weekly_compressed_period(
        session,
        goal,
        period_start=goal.start_date,
        period_end=target_date - dt.timedelta(days=1),
        limit=inject_weeks,
    )
    recent_recalls_entries = ai_context_service.exclude_covered_dates(
        ai_context_service.build_recent_recalls_entries(
            session, active_books, target_date, recent_days
        ),
        compressed.covered_ranges,
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

    reported_count = record_service.count_reported_records_before(
        session, GoalCategory.READING, target_date
    )
    min_records = setting_reader.get_int(session, AI_PERSPECTIVE_SUGGESTION_MIN_RECORDS)
    perspective_suggestion = ai_context_service.build_perspective_suggestion_instruction(
        GoalCategory.READING, reported_count < min_records
    )

    context = prompt_builder.DegradableFeedbackContext(
        fixed_variables={
            "today": target_date.isoformat(),
            "book_summary": ai_context_service.build_daily_book_summary_text(active_books, today),
            "today_recall": ai_context_service.build_today_recall_text(
                reading_log_items, books_by_id
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
                key="recent_recalls",
                entries=recent_recalls_entries,
                empty_text=_NO_RECENT_RECALLS_TEXT,
            ),
        ],
        conversation_history=history,
    )

    template_body = ai_orchestration.load_template_body(session, AiPurpose.DAILY_FEEDBACK_READING)
    max_chars = ai_orchestration.get_max_prompt_chars(session)
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

    next_sequence = record_service.next_chat_sequence(session, record.id)
    if message:
        session.add(
            ChatMessage(
                daily_record_id=record.id,
                goal_id=goal.id,
                purpose=AiPurpose.DAILY_FEEDBACK_READING,
                role=ChatRole.USER,
                content=message,
                sequence=next_sequence,
            )
        )
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
    session.flush()

    return ReadingChatOutcome(
        daily_record=record,
        assistant_message=assistant_message,
        was_truncated=build_result.was_truncated,
    )
