"""今日の一言の生成判定と実行（設計書 ロジック・プロンプト編17.4、
データ構造編5.5・6.2 GET /daily-message、実装フェーズ分割計画書Phase5）。

同日中に再生成しない（Phase5完了条件、目標ごとに判定する）。目標ごとに完全に独立した
プロンプト呼び出しで生成する（他目標の情報を一切渡さない）。複数目標が同時進行して
いる場合に、順調な目標の情報に引っ張られて停滞している目標の実態と乖離した一言が
生成されることを構造的に防ぐため（未決事項L-04関連）。ACTIVEな目標が1件も無い日は
goal_id=NULLの1件のみ生成する。
"""

import datetime as dt

from sqlalchemy.orm import Session, joinedload

from app.ai import conversation as ai_conversation
from app.ai import orchestration as ai_orchestration
from app.ai import prompt_builder
from app.constants.app_setting_keys import AI_ASSISTANT_UID_DAILY_MESSAGE
from app.constants.enums import AiPurpose, ConversationScope
from app.models.goal import Goal
from app.models.record import DailyMessage
from app.services import ai_context_service, calendar_service, goal_service, setting_reader


def _generate_for_goal(
    session: Session, today: dt.date, day_type_value: str, goal: Goal | None
) -> DailyMessage:
    """1件分（1目標、またはgoal=Noneで目標非依存）の今日の一言を生成する。

    goalsをこの呼び出し内で[goal]（またはgoalがNoneなら[]）に限定して各builderへ渡す
    ことで、他目標の情報を一切含まないプロンプトを組み立てる。呼び出し元のget_or_generateが
    list_active_exam_goalsで資格試験目標のみに絞り込み済みのため、ここに渡るgoalは常に
    category=EXAM（今日の一言に読書用の変種は設けない設計。要件定義書6.10）。
    """
    goals = [goal] if goal is not None else []
    materials = ai_context_service.list_active_materials(goals)

    variables = {
        "today": today.isoformat(),
        "day_type": day_type_value,
        "goal_summary": ai_context_service.build_goal_summary(goals, today),
        "progress_summary": ai_context_service.build_progress_summary(
            session, materials, today
        ),
        "recent_activity": ai_context_service.build_recent_activity_text(session, goals, today),
    }

    template_body = ai_orchestration.load_template_body(session, AiPurpose.DAILY_MESSAGE)
    max_chars = ai_orchestration.get_max_prompt_chars(session)
    build_result = prompt_builder.build_simple(template_body, variables, max_chars)

    assistant_uid = setting_reader.get_str(session, AI_ASSISTANT_UID_DAILY_MESSAGE)
    title_suffix = f" {goal.name}" if goal is not None else ""
    conversation = ai_conversation.ensure_conversation(
        session,
        goal=goal,
        scope=ConversationScope.DAILY_MESSAGE,
        scope_key=today.isoformat(),
        assistant_uid=assistant_uid,
        title=f"{today.isoformat()} 今日の一言{title_suffix}",
    )

    send_result = ai_orchestration.send_and_log(
        session,
        purpose=AiPurpose.DAILY_MESSAGE,
        conversation=conversation,
        prompt_text=build_result.text,
        prompt_chars=build_result.prompt_chars,
        was_truncated=build_result.was_truncated,
    )

    daily_message = DailyMessage(
        target_date=today, goal=goal, body=send_result.response_text.strip()
    )
    session.add(daily_message)
    session.flush()
    return daily_message


def get_or_generate(session: Session, today: dt.date) -> list[DailyMessage]:
    """今日の一言を目標ごとに取得する。未生成の目標があれば生成する
    （データ構造編6.2 GET /daily-message）。日中に新たにACTIVEになった目標があれば、
    既存の目標のメッセージは再生成せずその目標の分だけ追加生成する。
    """
    # 読書目標（category=READING）はexam_subjectを持たず、build_goal_summaryが「試験科目
    # 未登録」という誤った文脈を混入させるため、資格試験目標のみに限定する
    # （今日の一言に読書用の変種は設けない設計。要件定義書6.10）。
    active_goals = ai_context_service.list_active_exam_goals(session)
    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)
    day_type = calendar_service.resolve_day_type(session, today, treat_holiday_as_buffer)

    if not active_goals:
        existing = (
            session.query(DailyMessage)
            .filter_by(target_date=today, goal_id=None)
            .first()
        )
        if existing is not None:
            return [existing]
        return [_generate_for_goal(session, today, day_type.value, None)]

    existing_by_goal = {
        message.goal_id: message
        for message in session.query(DailyMessage)
        .options(joinedload(DailyMessage.goal))
        .filter(DailyMessage.target_date == today, DailyMessage.goal_id.isnot(None))
        .all()
    }
    messages = []
    for goal in active_goals:
        existing = existing_by_goal.get(goal.id)
        if existing is None:
            existing = _generate_for_goal(session, today, day_type.value, goal)
        messages.append(existing)
    return messages
