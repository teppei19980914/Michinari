"""復習クイズのAPI（開発Todo_復習クイズ_v1.0、仕様書6.1.6。開発Todo_単語帳_v1.0 要件Bで
単語帳由来の出所を追加）。

出題・解答の記録は`quiz_service`（AI非依存）、テーマからの生成は
`quiz_generation_service`（AI呼び出し）が担う。API層はドメイン例外をHTTPへ変換するのみ
（CODING_RULES.md「サービス層でのHTTP例外の送出禁止」）。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.quiz import QuizQuestion
from app.models.recap import RecapTheme
from app.schemas.quiz import (
    QuizAnswerRequest,
    QuizAnswerResultRead,
    QuizGenerateResultRead,
    QuizQuestionRead,
)
from app.services import (
    goal_service,
    quiz_generation_service,
    quiz_service,
    recap_service,
    vocab_service,
)

router = APIRouter(tags=["quiz"])


def _question_read(
    question: QuizQuestion,
    *,
    theme_names: dict[int, str],
    deck_info: dict[int, tuple[int, str]],
) -> QuizQuestionRead:
    if question.vocab_card_id is not None:
        deck_id, deck_name = deck_info[question.vocab_card_id]
        return QuizQuestionRead(
            id=question.id,
            source="vocab",
            vocab_deck_id=deck_id,
            vocab_deck_name=deck_name,
            question_text=question.question_text,
            choices=[question.choice_1, question.choice_2, question.choice_3, question.choice_4],
        )
    return QuizQuestionRead(
        id=question.id,
        source="theme",
        theme_id=question.theme_id,
        theme_name=theme_names[question.theme_id],
        question_text=question.question_text,
        choices=[question.choice_1, question.choice_2, question.choice_3, question.choice_4],
    )


@router.get("/quiz/today", response_model=list[QuizQuestionRead])
def get_today_quiz(session: Session = Depends(get_db)) -> list[QuizQuestionRead]:
    """今日出題すべきクイズ（間隔が来たもの、1日の上限まで）を返す。"""
    today = goal_service.resolve_today(session)
    questions = quiz_service.get_due_questions(session, today)
    theme_ids = {q.theme_id for q in questions if q.theme_id is not None}
    theme_names = {
        theme.id: theme.name
        for theme in session.query(RecapTheme).filter(RecapTheme.id.in_(theme_ids)).all()
    }
    vocab_card_ids = [q.vocab_card_id for q in questions if q.vocab_card_id is not None]
    deck_info = vocab_service.get_deck_info_for_cards(session, vocab_card_ids)
    return [_question_read(q, theme_names=theme_names, deck_info=deck_info) for q in questions]


@router.post("/quiz/{question_id}/answer", response_model=QuizAnswerResultRead)
def answer_quiz(
    question_id: int, payload: QuizAnswerRequest, session: Session = Depends(get_db)
) -> QuizAnswerResultRead:
    """解答を記録し、正誤・解説・出典・次回出題予定日を返す。"""
    question = quiz_service.get_question(session, question_id)
    is_correct = payload.choice_index == question.correct_choice_index
    quiz_service.record_answer(session, question, is_correct)
    if question.vocab_card_id is not None:
        deck_id, deck_name = vocab_service.get_deck_info_for_cards(
            session, [question.vocab_card_id]
        )[question.vocab_card_id]
        result = QuizAnswerResultRead(
            is_correct=is_correct,
            correct_choice_index=question.correct_choice_index,
            explanation=question.explanation,
            source="vocab",
            vocab_deck_id=deck_id,
            vocab_deck_name=deck_name,
            next_due_date=question.next_due_date,
        )
    else:
        result = QuizAnswerResultRead(
            is_correct=is_correct,
            correct_choice_index=question.correct_choice_index,
            explanation=question.explanation,
            source="theme",
            citation_date=question.citation_date,
            next_due_date=question.next_due_date,
        )
    session.commit()
    return result


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
