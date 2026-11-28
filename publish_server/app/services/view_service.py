"""閲覧API向けサービス（開発Todo_Web公開_v1.0 単位2、D-21）。

全クエリに`account_id`フィルタを必須化する（D-21、認可境界。他アカウントの公開物ID・
問題IDを指定した場合は`SnapshotNotFoundError`/`QuestionNotFoundError`になる＝IDOR対策）。
回答前は正解番号・解説を含めない（D-07。`list_quiz_questions`が返す`PublishedQuizQuestion`
から、API層が`app/schemas/quiz.py`の`QuizQuestionPreview`へ変換する際にフィールドを絞る）。

`_get_or_404`・`_list_by_account`は「id＋account_idで検索→無ければ404系例外」「account_idで
一覧→更新日時降順」という、D-21の要となる骨格を一箇所に集約する（同じ骨格を関数ごとに
コピペすると、将来モデルが増えた際にaccount_idガードを書き忘れるリスクが最も高いため、
dry-reviewerレビュー2026-11-28指摘）。
"""

import json
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.models.account import PublishAccount
from app.models.base import Base
from app.models.snapshot_gantt import PublishedGanttSnapshot
from app.models.snapshot_quiz import PublishedQuizQuestion
from app.models.snapshot_vocab import PublishedVocabDeck
from app.services.exceptions import QuestionNotFoundError, SnapshotNotFoundError


def _get_or_404[ModelT: Base](
    db: Session,
    model: type[ModelT],
    record_id: int | None,
    account: PublishAccount,
    not_found_error: Callable[[int | None], Exception],
) -> ModelT:
    record = db.query(model).filter(model.id == record_id, model.account_id == account.id).first()
    if record is None:
        raise not_found_error(record_id)
    return record


def _list_by_account[ModelT: Base](
    db: Session, model: type[ModelT], account: PublishAccount
) -> list[ModelT]:
    return (
        db.query(model)
        .filter(model.account_id == account.id)
        .order_by(model.updated_at.desc(), model.id.desc())
        .all()
    )


def list_gantt_snapshots(db: Session, account: PublishAccount) -> list[PublishedGanttSnapshot]:
    return _list_by_account(db, PublishedGanttSnapshot, account)


def get_gantt_snapshot(
    db: Session, account: PublishAccount, snapshot_id: int
) -> PublishedGanttSnapshot:
    return _get_or_404(db, PublishedGanttSnapshot, snapshot_id, account, SnapshotNotFoundError)


def list_vocab_decks(db: Session, account: PublishAccount) -> list[PublishedVocabDeck]:
    return _list_by_account(db, PublishedVocabDeck, account)


def get_vocab_deck(db: Session, account: PublishAccount, deck_id: int) -> PublishedVocabDeck:
    return _get_or_404(db, PublishedVocabDeck, deck_id, account, SnapshotNotFoundError)


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
    return _get_or_404(db, PublishedQuizQuestion, question_id, account, QuestionNotFoundError)


def decode_choices(choices_json: str) -> dict[str, str]:
    return json.loads(choices_json)
