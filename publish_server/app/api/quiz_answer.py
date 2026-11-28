"""問題への回答API（開発Todo_Web公開_v1.0 単位2、D-07・D-08・D-18）。

状態変更リクエストのためCSRFトークン必須（D-18、`require_csrf`）。応答に初めて
`correct_choice_index`・`explanation`を含める（D-07）。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_account, get_db, require_csrf
from app.models.account import PublishAccount
from app.schemas.quiz import QuizAnswerRequest, QuizAnswerResult
from app.services import answer_service

router = APIRouter(prefix="/view", tags=["quiz-answer"])


@router.post("/quiz/{question_id}/answer", response_model=QuizAnswerResult)
def answer(
    question_id: int,
    body: QuizAnswerRequest,
    account: PublishAccount = Depends(get_current_account),
    _csrf: None = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> QuizAnswerResult:
    is_correct, correct_choice_index, explanation = answer_service.answer_question(
        db, account, question_id, body.chosen_index, body.client_answer_uuid
    )
    return QuizAnswerResult(
        is_correct=is_correct,
        correct_choice_index=correct_choice_index,
        explanation=explanation,
    )
