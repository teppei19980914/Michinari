"""問題への回答API向けサービス（開発Todo_Web公開_v1.0 単位2、D-07・D-08・D-21）。

正誤判定はサーバ側で行う（D-07）。同一`client_answer_uuid`での再送は、新しい回答として
記録せず既存の判定結果を返す（冪等性、STRIDE分析5章「大量回答リクエストによるDB肥大化」
対策）。
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.account import PublishAccount
from app.models.base import utcnow
from app.models.quiz_answer_record import QuizAnswerRecord
from app.services import view_service
from app.services.exceptions import DuplicateClientAnswerUuidError


def answer_question(
    db: Session,
    account: PublishAccount,
    question_id: int,
    chosen_index: int,
    client_answer_uuid: str,
) -> tuple[bool, int, str]:
    """回答する。戻り値は`(is_correct, correct_choice_index, explanation)`。

    `client_answer_uuid`が既存の回答と同じ場合は、新規作成せず当時の判定結果をそのまま返す。
    その問題行が既に差し替え等で削除されている極端な場合（`question_id`が`SET NULL`済み）は
    `QuestionNotFoundError`になる（単位2では未対応のレアケースとして受容する）。

    検索は`account_id`も条件に含める（D-21）。`client_answer_uuid`はDB全体で一意だが、
    account_idを条件から外すと「他アカウントの値を知っていれば再送で判定結果を取得できる」
    というIDOR的な経路になる（直後の`get_quiz_question`のaccount_idフィルタで実害は無いが、
    auth-reviewer・injection-reviewerレビュー2026-11-28指摘により、ここ自体でも防ぐ）。
    """
    existing = (
        db.query(QuizAnswerRecord)
        .filter(
            QuizAnswerRecord.client_answer_uuid == client_answer_uuid,
            QuizAnswerRecord.account_id == account.id,
        )
        .first()
    )
    if existing is not None:
        question = view_service.get_quiz_question(db, account, existing.question_id)
        return existing.is_correct, question.correct_choice_index, question.explanation

    question = view_service.get_quiz_question(db, account, question_id)
    is_correct = chosen_index == question.correct_choice_index
    db.add(
        QuizAnswerRecord(
            account_id=account.id,
            question_id=question.id,
            local_question_id=question.local_question_id,
            chosen_index=chosen_index,
            is_correct=is_correct,
            answered_at=utcnow(),
            client_answer_uuid=client_answer_uuid,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        # `client_answer_uuid`はDB全体でUNIQUE（上記の検索はこのアカウントの行のみを見るため、
        # 他アカウントが先に同じ値を使っていた場合はここで一意制約違反になる（auth-reviewer
        # レビュー2026-11-28指摘）。
        db.rollback()
        raise DuplicateClientAnswerUuidError() from None
    return is_correct, question.correct_choice_index, question.explanation
