"""復習クイズのAPI（開発Todo_復習クイズ_v1.0、仕様書6.1.6）。

出題・解答の記録は`quiz_service`（AI非依存）、テーマからの生成は
`quiz_generation_service`（AI呼び出し）が担う。API層はドメイン例外をHTTPへ変換するのみ
（CODING_RULES.md「サービス層でのHTTP例外の送出禁止」）。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.recap import RecapTheme
from app.schemas.quiz import (
    QuizAnswerRequest,
    QuizAnswerResultRead,
    QuizGenerateResultRead,
    QuizQuestionRead,
)
from app.services import goal_service, quiz_generation_service, quiz_service, recap_service

router = APIRouter(tags=["quiz"])


def _question_read(question, theme_name: str) -> QuizQuestionRead:
    return QuizQuestionRead(
        id=question.id,
        theme_id=question.theme_id,
        theme_name=theme_name,
        question_text=question.question_text,
        choices=[question.choice_1, question.choice_2, question.choice_3, question.choice_4],
    )


@router.get("/quiz/today", response_model=list[QuizQuestionRead])
def get_today_quiz(session: Session = Depends(get_db)) -> list[QuizQuestionRead]:
    """今日出題すべきクイズ（間隔が来たもの、1日の上限まで）を返す。"""
    today = goal_service.resolve_today(session)
    questions = quiz_service.get_due_questions(session, today)
    theme_names = {
        theme.id: theme.name
        for theme in session.query(RecapTheme)
        .filter(RecapTheme.id.in_({q.theme_id for q in questions}))
        .all()
    }
    return [_question_read(q, theme_names[q.theme_id]) for q in questions]


@router.post("/quiz/{question_id}/answer", response_model=QuizAnswerResultRead)
def answer_quiz(
    question_id: int, payload: QuizAnswerRequest, session: Session = Depends(get_db)
) -> QuizAnswerResultRead:
    """解答を記録し、正誤・解説・出典・次回出題予定日を返す。"""
    question = quiz_service.get_question(session, question_id)
    is_correct = payload.choice_index == question.correct_choice_index
    quiz_service.record_answer(session, question, is_correct)
    session.commit()
    return QuizAnswerResultRead(
        is_correct=is_correct,
        correct_choice_index=question.correct_choice_index,
        explanation=question.explanation,
        citation_date=question.citation_date,
        next_due_date=question.next_due_date,
    )


@router.post("/themes/{theme_id}/quiz/generate", response_model=QuizGenerateResultRead)
def generate_theme_quiz(
    theme_id: int, session: Session = Depends(get_db)
) -> QuizGenerateResultRead:
    """テーマのクイズを作る・作り直す（利用者操作）。未出題分のみ削除してから生成する。"""
    theme = recap_service.get_theme(session, theme_id)
    goal = goal_service.get_goal(session, theme.goal_id)
    created = quiz_generation_service.regenerate_for_theme(session, goal, theme)
    session.commit()
    return QuizGenerateResultRead(created=created)
