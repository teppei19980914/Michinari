"""閲覧API向けサービス（開発Todo_Web公開_v1.0 単位2、D-21）。

全クエリに`account_id`フィルタを必須化する（D-21、認可境界。他アカウントの公開物ID・
問題IDを指定した場合は`SnapshotNotFoundError`/`QuestionNotFoundError`になる＝IDOR対策）。
回答前は正解番号・解説を含めない（D-07。`list_quiz_questions`が返す`PublishedQuizQuestion`
から、API層が`app/schemas/quiz.py`の`QuizQuestionPreview`へ変換する際にフィールドを絞る）。
"""

import json

from sqlalchemy.orm import Session

from app.models.account import PublishAccount
from app.models.snapshot_gantt import PublishedGanttSnapshot
from app.models.snapshot_quiz import PublishedQuizQuestion
from app.models.snapshot_vocab import PublishedVocabDeck
from app.services.exceptions import QuestionNotFoundError, SnapshotNotFoundError


def list_gantt_snapshots(db: Session, account: PublishAccount) -> list[PublishedGanttSnapshot]:
    return (
        db.query(PublishedGanttSnapshot)
        .filter(PublishedGanttSnapshot.account_id == account.id)
        .order_by(PublishedGanttSnapshot.updated_at.desc(), PublishedGanttSnapshot.id.desc())
        .all()
    )


def get_gantt_snapshot(
    db: Session, account: PublishAccount, snapshot_id: int
) -> PublishedGanttSnapshot:
    snapshot = (
        db.query(PublishedGanttSnapshot)
        .filter(
            PublishedGanttSnapshot.id == snapshot_id,
            PublishedGanttSnapshot.account_id == account.id,
        )
        .first()
    )
    if snapshot is None:
        raise SnapshotNotFoundError(snapshot_id)
    return snapshot


def list_vocab_decks(db: Session, account: PublishAccount) -> list[PublishedVocabDeck]:
    return (
        db.query(PublishedVocabDeck)
        .filter(PublishedVocabDeck.account_id == account.id)
        .order_by(PublishedVocabDeck.updated_at.desc(), PublishedVocabDeck.id.desc())
        .all()
    )


def get_vocab_deck(db: Session, account: PublishAccount, deck_id: int) -> PublishedVocabDeck:
    deck = (
        db.query(PublishedVocabDeck)
        .filter(PublishedVocabDeck.id == deck_id, PublishedVocabDeck.account_id == account.id)
        .first()
    )
    if deck is None:
        raise SnapshotNotFoundError(deck_id)
    return deck


def list_quiz_questions(
    db: Session, account: PublishAccount, deck_id: int
) -> list[PublishedQuizQuestion]:
    """D-07：正解番号・解説を含まない一覧（API層のスキーマ変換でフィールドを絞る）。"""
    get_vocab_deck(db, account, deck_id)  # 存在・所有確認（IDOR対策）
    return (
        db.query(PublishedQuizQuestion)
        .filter(
            PublishedQuizQuestion.vocab_deck_snapshot_id == deck_id,
            PublishedQuizQuestion.account_id == account.id,
        )
        .order_by(PublishedQuizQuestion.id.asc())
        .all()
    )


def get_quiz_question(
    db: Session, account: PublishAccount, question_id: int | None
) -> PublishedQuizQuestion:
    question = (
        db.query(PublishedQuizQuestion)
        .filter(
            PublishedQuizQuestion.id == question_id,
            PublishedQuizQuestion.account_id == account.id,
        )
        .first()
    )
    if question is None:
        raise QuestionNotFoundError(question_id)
    return question


def decode_choices(choices_json: str) -> dict[str, str]:
    return json.loads(choices_json)
