"""今日の一言の生成判定と実行（設計書 ロジック・プロンプト編17.4、
データ構造編6.2 GET /daily-message、実装フェーズ分割計画書Phase5）。

同日中に再生成しない（Phase5完了条件）。目標が複数同時にACTIVEな場合を考慮し、
今日の一言はai_conversation.goal_id=NULL・フォルダなしとする（データ構造編5.5で
今日の一言が明示的にgoal非依存とされているため、5.5の整理に従う。日次報告のフォルダ
帰属方針についてはapp/ai/conversation.pyのモジュールdocstringを参照）。
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.ai import conversation as ai_conversation
from app.ai import orchestration as ai_orchestration
from app.ai import prompt_builder
from app.constants.app_setting_keys import AI_ASSISTANT_UID_DAILY_MESSAGE
from app.constants.enums import AiPurpose, ConversationScope
from app.models.record import DailyMessage
from app.services import ai_context_service, calendar_service, goal_service, setting_reader


def get_or_generate(session: Session, today: dt.date) -> DailyMessage:
    """今日の一言を取得する。未生成なら生成する（データ構造編6.2 GET /daily-message）。"""
    existing = session.query(DailyMessage).filter_by(target_date=today).first()
    if existing is not None:
        return existing

    # 読書目標（category=READING）はexam_subjectを持たず、build_goal_summaryが「試験科目
    # 未登録」という誤った文脈を混入させるため、資格試験目標のみに限定する
    # （今日の一言に読書用の変種は設けない設計。要件定義書6.10）。
    active_goals = ai_context_service.list_active_exam_goals(session)
    active_materials = ai_context_service.list_active_materials(active_goals)
    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)
    day_type = calendar_service.resolve_day_type(session, today, treat_holiday_as_buffer)

    variables = {
        "today": today.isoformat(),
        "day_type": day_type.value,
        "goal_summary": ai_context_service.build_goal_summary(active_goals, today),
        "progress_summary": ai_context_service.build_progress_summary(
            session, active_materials
        ),
        "recent_activity": ai_context_service.build_recent_activity_text(
            session, active_goals, today
        ),
    }

    template_body = ai_orchestration.load_template_body(session, AiPurpose.DAILY_MESSAGE)
    max_chars = ai_orchestration.get_max_prompt_chars(session)
    build_result = prompt_builder.build_simple(template_body, variables, max_chars)

    assistant_uid = setting_reader.get_str(session, AI_ASSISTANT_UID_DAILY_MESSAGE)
    conversation = ai_conversation.ensure_conversation(
        session,
        goal=None,
        scope=ConversationScope.DAILY_MESSAGE,
        scope_key=today.isoformat(),
        assistant_uid=assistant_uid,
        title=f"{today.isoformat()} 今日の一言",
    )

    send_result = ai_orchestration.send_and_log(
        session,
        purpose=AiPurpose.DAILY_MESSAGE,
        conversation=conversation,
        prompt_text=build_result.text,
        prompt_chars=build_result.prompt_chars,
        was_truncated=build_result.was_truncated,
    )

    daily_message = DailyMessage(target_date=today, body=send_result.response_text.strip())
    session.add(daily_message)
    session.flush()
    return daily_message
