"""目標相談チャットのAPI（S09、要件定義書R-104）。

質問の受付と、画面が使う上限の取得だけを担う。質疑の処理そのものは
`services/goal_consultation_service.py`に置く（API層はドメイン例外をHTTPへ変換するのみ、
CODING_RULES.md、`help_assistant.py`と同じ方針）。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.constants.app_setting_keys import AI_GOAL_CONSULTATION_QUESTION_MAX_CHARS
from app.database import get_db
from app.schemas.goal_consultation import (
    GoalConsultationAnswerRead,
    GoalConsultationCitedWeek,
    GoalConsultationLimitsRead,
    GoalConsultationQuestionRequest,
)
from app.services import goal_consultation_service, goal_service, setting_reader

router = APIRouter(tags=["goal-consultation"])


@router.post("/goals/{goal_id}/consultation/questions", response_model=GoalConsultationAnswerRead)
def ask_question(
    goal_id: int, payload: GoalConsultationQuestionRequest, session: Session = Depends(get_db)
) -> GoalConsultationAnswerRead:
    """質問に、目標の記録に基づいて答える（質問ごとのチャットで送信し、回答後に削除する）。"""
    goal = goal_service.get_goal(session, goal_id)
    today = goal_service.resolve_today(session)
    answer = goal_consultation_service.ask(
        session, goal=goal, today=today, raw_question=payload.question
    )
    return GoalConsultationAnswerRead(
        status=answer.status,
        answer=answer.text or None,
        cited_dates=list(answer.cited_dates),
        cited_weeks=[
            GoalConsultationCitedWeek(start=start, end=end) for start, end in answer.cited_weeks
        ],
    )


@router.get("/goals/{goal_id}/consultation/limits", response_model=GoalConsultationLimitsRead)
def get_limits(goal_id: int, session: Session = Depends(get_db)) -> GoalConsultationLimitsRead:
    """質問の上限文字数を返す（入力欄の文字数表示と事前チェックに使う）。

    上限値自体は目標に依存しない設定だが、画面（目標詳細の相談タブ）側の呼び出しを
    他の目標相談APIと同じ`/goals/{goal_id}/...`の形に揃える（goal_idの妥当性検証も兼ねる）。
    """
    goal_service.get_goal(session, goal_id)
    return GoalConsultationLimitsRead(
        max_question_chars=setting_reader.get_int(session, AI_GOAL_CONSULTATION_QUESTION_MAX_CHARS)
    )
