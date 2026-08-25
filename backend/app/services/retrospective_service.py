"""総括レポート（GOAL_RETROSPECTIVE）の生成（設計書 ロジック・プロンプト編17.5、
データ構造編5.4、実装フェーズ分割計画書Phase10）。

goal_service.close_goalのdocstring通り、総括レポートの生成はクローズ処理の成否に
影響させない別責務とする（クローズはgoal_service、生成は本サービスがAPI層から別々に
呼ばれる。仕様書6.9「クローズ実行後、総括レポートの生成を開始し」）。
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.ai import conversation as ai_conversation
from app.ai import orchestration as ai_orchestration
from app.ai import prompt_builder
from app.constants.app_setting_keys import AI_ASSISTANT_UID_GOAL_RETROSPECTIVE
from app.constants.enums import AiPurpose, ConversationScope
from app.models.goal import Goal
from app.models.retrospective import GoalRetrospective
from app.services import ai_context_service, goal_service, setting_reader

#: ai_conversation.scope_key はGOAL_RETROSPECTIVEでは固定値"main"とする
#: （データ構造編5.5「scope_keyの値」表）。匿名化版・通常版は同一会話内の別送信として扱う
#: （goal_retrospectiveはgoal_id単位、chat自体はconversation_uid一つで足りるため）。
_SCOPE_KEY = "main"


def get_latest_retrospective(
    session: Session, goal: Goal, *, anonymized: bool = False
) -> GoalRetrospective | None:
    """最新の総括レポートを取得する（5.4「最新のものを既定で表示する」）。"""
    return (
        session.query(GoalRetrospective)
        .filter(GoalRetrospective.goal_id == goal.id, GoalRetrospective.is_anonymized == anonymized)
        .order_by(GoalRetrospective.generated_at.desc())
        .first()
    )


def generate_retrospective(
    session: Session, goal: Goal, *, today: dt.date, anonymize: bool = False
) -> GoalRetrospective:
    """総括レポートを生成する（17.5、仕様書6.9〜6.10。再生成は新規レコードとして追加し、
    旧レコードは削除しない＝5.4「再生成を許容するため複数レコードを持てる」）。
    """
    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)
    materials = [material for material in goal.materials if material.is_active]

    variables = {
        "goal_summary": ai_context_service.build_goal_summary([goal], today),
        "material_summary": ai_context_service.build_material_summary_text(session, materials),
        "overall_metrics": ai_context_service.build_overall_metrics_text(
            session, goal, today, treat_holiday_as_buffer
        ),
        "quality_trend": ai_context_service.build_quality_trend_text(session, materials),
        "replan_history": ai_context_service.build_replan_history_text(session, goal),
        "weekly_summaries": ai_context_service.build_all_weekly_summaries_text(session, goal),
        "exam_results": ai_context_service.build_exam_results_text(goal),
        "anonymize": ai_context_service.build_anonymize_instruction(anonymize),
    }

    template_body = ai_orchestration.load_template_body(session, AiPurpose.GOAL_RETROSPECTIVE)
    max_chars = ai_orchestration.get_max_prompt_chars(session)
    build_result = prompt_builder.build_simple(template_body, variables, max_chars)

    assistant_uid = setting_reader.get_str(session, AI_ASSISTANT_UID_GOAL_RETROSPECTIVE)
    conversation = ai_conversation.ensure_conversation(
        session,
        goal=goal,
        scope=ConversationScope.GOAL_RETROSPECTIVE,
        scope_key=_SCOPE_KEY,
        assistant_uid=assistant_uid,
        title=f"{goal.name} 総括レポート",
    )

    send_result = ai_orchestration.send_and_log(
        session,
        purpose=AiPurpose.GOAL_RETROSPECTIVE,
        conversation=conversation,
        prompt_text=build_result.text,
        prompt_chars=build_result.prompt_chars,
        was_truncated=build_result.was_truncated,
    )

    retrospective = GoalRetrospective(
        goal_id=goal.id,
        body=send_result.response_text.strip(),
        is_anonymized=anonymize,
    )
    session.add(retrospective)
    session.flush()
    return retrospective
