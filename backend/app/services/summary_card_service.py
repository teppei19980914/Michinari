"""ふりかえりまとめ・共有カードの集計・AI一文生成（開発Todo「まとめと共有カード」v1.0、
ロジック・プロンプト編28章）。

集計（get_summary）はAI呼び出しを含まず都度算出する。AI一文（generate_sentence）は
利用者が明示的に操作したときのみ呼び、応答は永続化しない（§0 U4）。
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.ai import conversation as ai_conversation
from app.ai import orchestration as ai_orchestration
from app.ai import prompt_builder
from app.ai.exceptions import AiAuthRequiredError
from app.constants.app_setting_keys import (
    AI_ASSISTANT_UID_SUMMARY_CARD,
    AI_SUMMARY_CARD_FOLDER_NAME,
)
from app.constants.enums import AiPurpose, ConversationScope, GoalCategory, RecordState
from app.models.goal import Goal
from app.models.recap import RecapEntry, RecapTheme, RecapThemeLink
from app.models.record import DailyRecord
from app.services import (
    ai_context_common,
    ai_context_exam,
    ai_context_reading,
    ai_context_work,
    goal_service,
    metrics_service,
    milestone_service_common,
    record_service_common,
    roadmap_service,
    setting_reader,
)
from app.services.exceptions import ValidationError

#: AI一文が期間内に記録を1件も参照できない場合に埋め込む文面（build_with_degradable_entries
#: のempty_text。他の用途のempty_text（例: retrospective_service）と同じ扱い）。
_NO_RECORDS_TEXT = "（対象期間に記録はありません）"


class SummaryCardAggregate:
    """集計結果（AI呼び出しなし）。schemas.summary_card.SummaryCardReadへそのまま渡す。"""

    def __init__(
        self,
        *,
        record_days: int,
        longest_consecutive_days: int,
        top_theme_name: str | None,
        milestones: list,
        roadmap,
    ) -> None:
        self.record_days = record_days
        self.longest_consecutive_days = longest_consecutive_days
        self.top_theme_name = top_theme_name
        self.milestones = milestones
        self.roadmap = roadmap


def _validate_period(date_from: dt.date, date_to: dt.date) -> None:
    if date_from > date_to:
        raise ValidationError("date_from must not be after date_to")


def _top_theme_name(
    session: Session, goal: Goal, date_from: dt.date, date_to: dt.date
) -> str | None:
    """いちばん多く書いたテーマ（EXAM/READINGのみ、§0 U7）。期間内の件数が最大のテーマ名を返す。

    件数が同じテーマが複数ある場合は`recap_service.list_themes`と同じ順序（本文の更新日時の
    新しい順）で最初に見つかったものを採用する（決定的な順序、CLAUDE.mdの都度算出方針）。
    テーマ件数分のクエリ（N+1、`recap_service.get_theme`/`theme_entry_rows`を毎テーマ呼ぶ）を
    避け、1クエリの集計で求める（パフォーマンスレビュー指摘、2026-11-13。本関数が目標詳細
    画面の既定タブ表示時に毎回呼ばれるようになったため修正）。
    """
    if goal.category == GoalCategory.WORK:
        return None
    row = session.execute(
        select(RecapTheme.name)
        .join(RecapThemeLink, RecapThemeLink.theme_id == RecapTheme.id)
        .join(RecapEntry, RecapEntry.id == RecapThemeLink.entry_id)
        .where(
            RecapTheme.goal_id == goal.id,
            RecapEntry.record_date >= date_from,
            RecapEntry.record_date <= date_to,
        )
        .group_by(RecapTheme.id, RecapTheme.name, RecapTheme.updated_at)
        .order_by(
            func.count(RecapEntry.id).desc(),
            RecapTheme.updated_at.desc(),
            RecapTheme.id.desc(),
        )
        .limit(1)
    ).first()
    return row[0] if row is not None else None


def get_summary(
    session: Session, goal: Goal, *, date_from: dt.date, date_to: dt.date
) -> SummaryCardAggregate:
    """期間内の集計を算出する（AI呼び出しなし、28.2手順1）。"""
    _validate_period(date_from, date_to)
    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)

    record_days = (
        session.query(DailyRecord.record_date)
        .filter(
            DailyRecord.record_date >= date_from,
            DailyRecord.record_date <= date_to,
            record_service_common.category_state_column(goal.category) == RecordState.REPORTED,
        )
        .distinct()
        .count()
    )
    longest_consecutive_days = metrics_service.compute_longest_consecutive_report_days(
        session, goal, date_from, date_to, treat_holiday_as_buffer
    )
    milestones = [
        achievement
        for achievement in milestone_service_common.list_achievements(session, goal.id)
        if date_from <= achievement.achieved_at.date() <= date_to
    ]
    roadmap = roadmap_service.get_roadmap(session, goal, date_to, treat_holiday_as_buffer)

    return SummaryCardAggregate(
        record_days=record_days,
        longest_consecutive_days=longest_consecutive_days,
        top_theme_name=_top_theme_name(session, goal, date_from, date_to),
        milestones=milestones,
        roadmap=roadmap,
    )


def _resolve_category_context(
    session: Session, goal: Goal, date_from: dt.date, date_to: dt.date
) -> tuple[AiPurpose, ConversationScope, list[prompt_builder.DatedLogEntry]]:
    if goal.category == GoalCategory.READING:
        purpose = AiPurpose.SUMMARY_CARD_SENTENCE_READING
        scope = ConversationScope.SUMMARY_CARD_SENTENCE_READING
        books = [goal.book] if goal.book is not None else []
        entries = ai_context_reading.build_recent_recalls_entries(
            session, books, date_from, date_to
        )
    elif goal.category == GoalCategory.WORK:
        purpose = AiPurpose.SUMMARY_CARD_SENTENCE_WORK
        scope = ConversationScope.SUMMARY_CARD_SENTENCE_WORK
        assignments = [goal.work_assignment] if goal.work_assignment is not None else []
        entries = ai_context_work.build_recent_work_logs_entries(
            session, assignments, date_from, date_to
        )
    else:
        purpose = AiPurpose.SUMMARY_CARD_SENTENCE
        scope = ConversationScope.SUMMARY_CARD_SENTENCE
        entries = ai_context_exam.build_recent_study_entries(session, goal, date_from, date_to)
    return purpose, scope, entries


def generate_sentence(session: Session, goal: Goal, *, date_from: dt.date, date_to: dt.date) -> str:
    """AIが選んだ印象的な一文を生成する（利用者の明示操作時のみ呼ぶ、28.2手順3）。

    記録を要約・一般化した新しい一文のみを返す（逐語引用はしない、要件定義書R-157）。
    生成結果は永続化しない（§0 U4）。使い捨てチャットは応答取得後に必ず削除する（28.5）。
    """
    _validate_period(date_from, date_to)
    if not ai_client.is_authenticated(session):
        raise AiAuthRequiredError("AI connection is required")

    purpose, scope, entries = _resolve_category_context(session, goal, date_from, date_to)
    template_body = ai_orchestration.load_template_body(session, purpose)
    max_chars = ai_orchestration.get_max_prompt_chars(session)
    context = prompt_builder.DegradableFeedbackContext(
        fixed_variables={"anonymize": ai_context_common.build_anonymize_instruction(True)},
        stages=[
            prompt_builder.DegradableEntryStage(
                key="period_records", entries=entries, empty_text=_NO_RECORDS_TEXT
            )
        ],
    )
    build_result = prompt_builder.build_with_degradable_entries(template_body, context, max_chars)

    folder_name = setting_reader.get_str(session, AI_SUMMARY_CARD_FOLDER_NAME)
    conversation = ai_conversation.ensure_conversation(
        session,
        goal=goal,
        scope=scope,
        scope_key=uuid.uuid4().hex,
        assistant_uid=setting_reader.get_str(session, AI_ASSISTANT_UID_SUMMARY_CARD),
        title=f"{goal.name} ふりかえりまとめ",
        folder_name=folder_name,
    )
    try:
        result = ai_orchestration.send_and_log(
            session,
            purpose=purpose,
            conversation=conversation,
            prompt_text=build_result.text,
            prompt_chars=build_result.prompt_chars,
            was_truncated=build_result.was_truncated,
        )
    finally:
        ai_conversation.discard_conversation(session, conversation, folder_name=folder_name)
    return result.response_text.strip()
