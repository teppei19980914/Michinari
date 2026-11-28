"""公開APIトークンで認証されたローカルアプリからのスナップショット受信・差し替え・
公開停止（開発Todo_Web公開_v1.0 単位2、D-01・D-07・D-10・D-20）。

アップロードは`(account_id, local_goal_id)`／`(account_id, local_deck_id)`単位のupsert
（同一local_goal_id／同一local_deck_idで上書き、単位2テスト観点）。問題のみ、差し替え時に
既存行を全削除してから再作成する（更新ではなく削除＋再作成）。これにより差し替え後は古い版
の問題IDが必ず無効化される（単位2テスト観点「差し替え後に古い版の問題へ回答できないこと」、
設計根拠は`app/models/snapshot_quiz.py`参照）。

公開停止（`delete_*`）は、対象が存在しない場合も冪等に成功する（`session_service.
delete_session`と同じ方針）。一方、問題のアップロードは単語帳デッキが未公開だと失敗する
（`VocabDeckNotPublishedError`、問題は単語帳デッキのスナップショットに従属するため）。
"""

import json

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.account import PublishAccount
from app.models.snapshot_gantt import PublishedGanttSnapshot
from app.models.snapshot_quiz import PublishedQuizQuestion
from app.models.snapshot_vocab import PublishedVocabDeck
from app.schemas.gantt import GanttSnapshotUploadRequest
from app.schemas.quiz import QuizQuestionIn
from app.schemas.vocab import VocabDeckUploadRequest
from app.services.exceptions import (
    QuestionNotFromVocabCardError,
    SnapshotTooLargeError,
    TooManyItemsError,
    VocabDeckNotPublishedError,
)


def _check_snapshot_size(serialized: str) -> None:
    """D-20：スナップショット1件あたりの最大サイズ（JSON化後）を検証する。"""
    settings = get_settings()
    actual_bytes = len(serialized.encode("utf-8"))
    if actual_bytes > settings.max_snapshot_bytes:
        raise SnapshotTooLargeError(actual_bytes, settings.max_snapshot_bytes)


def _check_item_count(items: list, item_name: str, max_count: int) -> None:
    """D-20：単語帳カード数・問題数の上限を検証する。"""
    if len(items) > max_count:
        raise TooManyItemsError(item_name, len(items), max_count)


def _find_gantt_snapshot(
    db: Session, account: PublishAccount, local_goal_id: int
) -> PublishedGanttSnapshot | None:
    return (
        db.query(PublishedGanttSnapshot)
        .filter(
            PublishedGanttSnapshot.account_id == account.id,
            PublishedGanttSnapshot.local_goal_id == local_goal_id,
        )
        .first()
    )


def _find_vocab_deck(
    db: Session, account: PublishAccount, local_deck_id: int
) -> PublishedVocabDeck | None:
    return (
        db.query(PublishedVocabDeck)
        .filter(
            PublishedVocabDeck.account_id == account.id,
            PublishedVocabDeck.local_deck_id == local_deck_id,
        )
        .first()
    )


def upsert_gantt_snapshot(
    db: Session,
    account: PublishAccount,
    local_goal_id: int,
    body: GanttSnapshotUploadRequest,
) -> PublishedGanttSnapshot:
    items_json = json.dumps([item.model_dump(mode="json") for item in body.items])
    columns_json = json.dumps([column.model_dump(mode="json") for column in body.columns])
    cells_json = json.dumps([cell.model_dump(mode="json") for cell in body.cells])
    holidays_json = json.dumps([holiday.isoformat() for holiday in body.holidays])
    _check_snapshot_size(items_json + columns_json + cells_json + holidays_json)

    snapshot = _find_gantt_snapshot(db, account, local_goal_id)
    if snapshot is None:
        snapshot = PublishedGanttSnapshot(account_id=account.id, local_goal_id=local_goal_id)
        db.add(snapshot)
    snapshot.goal_name = body.goal_name
    snapshot.items_json = items_json
    snapshot.columns_json = columns_json
    snapshot.cells_json = cells_json
    snapshot.holidays_json = holidays_json
    db.commit()
    db.refresh(snapshot)
    return snapshot


def delete_gantt_snapshot(db: Session, account: PublishAccount, local_goal_id: int) -> None:
    db.query(PublishedGanttSnapshot).filter(
        PublishedGanttSnapshot.account_id == account.id,
        PublishedGanttSnapshot.local_goal_id == local_goal_id,
    ).delete()
    db.commit()


def upsert_vocab_deck(
    db: Session,
    account: PublishAccount,
    local_deck_id: int,
    body: VocabDeckUploadRequest,
) -> PublishedVocabDeck:
    settings = get_settings()
    _check_item_count(body.cards, "vocab cards", settings.max_vocab_cards)
    cards_json = json.dumps([card.model_dump(mode="json") for card in body.cards])
    _check_snapshot_size(cards_json)

    deck = _find_vocab_deck(db, account, local_deck_id)
    if deck is None:
        deck = PublishedVocabDeck(account_id=account.id, local_deck_id=local_deck_id)
        db.add(deck)
    deck.deck_name = body.deck_name
    deck.cards_json = cards_json
    db.commit()
    db.refresh(deck)
    return deck


def delete_vocab_deck(db: Session, account: PublishAccount, local_deck_id: int) -> None:
    """単語帳デッキの公開停止。D-23によりORM relationshipを持たないため、紐づく問題
    （`published_quiz_question.vocab_deck_snapshot_id`）はDB側のON DELETE CASCADEで連動削除する。
    """
    db.query(PublishedVocabDeck).filter(
        PublishedVocabDeck.account_id == account.id,
        PublishedVocabDeck.local_deck_id == local_deck_id,
    ).delete()
    db.commit()


def replace_quiz_questions(
    db: Session,
    account: PublishAccount,
    local_deck_id: int,
    questions: list[QuizQuestionIn],
) -> PublishedVocabDeck:
    """単語帳デッキに紐づく問題を全置換する（`app/models/snapshot_quiz.py`参照）。

    対応する単語帳デッキが未公開の場合は`VocabDeckNotPublishedError`を送出する
    （問題は単語帳デッキのスナップショットに従属するため、先に単語帳を公開する必要がある）。

    各問題の`local_card_id`が、同じデッキのカード一覧（`cards_json`）に実在することを
    検証する（D-03・STRIDE分析5章「サーバ側でも二重検証（`vocab_card_id`必須チェック）」）。
    一致しなければ`QuestionNotFromVocabCardError`を送出する（テーマ由来等の対象外データが
    混入している可能性があるため、1件でも不一致なら全体を拒否し、一部のみの保存はしない）。
    """
    settings = get_settings()
    _check_item_count(questions, "quiz questions", settings.max_quiz_questions)
    serialized = json.dumps([question.model_dump(mode="json") for question in questions])
    _check_snapshot_size(serialized)

    deck = _find_vocab_deck(db, account, local_deck_id)
    if deck is None:
        raise VocabDeckNotPublishedError(local_deck_id)

    published_card_ids = {card["local_card_id"] for card in json.loads(deck.cards_json)}
    for question in questions:
        if question.local_card_id not in published_card_ids:
            raise QuestionNotFromVocabCardError(question.local_card_id)

    db.query(PublishedQuizQuestion).filter(
        PublishedQuizQuestion.vocab_deck_snapshot_id == deck.id
    ).delete()
    for question in questions:
        db.add(
            PublishedQuizQuestion(
                account_id=account.id,
                vocab_deck_snapshot_id=deck.id,
                local_question_id=question.local_question_id,
                question_text=question.question_text,
                choices_json=json.dumps(
                    {
                        "choice_1": question.choice_1,
                        "choice_2": question.choice_2,
                        "choice_3": question.choice_3,
                        "choice_4": question.choice_4,
                    }
                ),
                correct_choice_index=question.correct_choice_index,
                explanation=question.explanation,
            )
        )
    db.commit()
    return deck


def delete_quiz_questions(db: Session, account: PublishAccount, local_deck_id: int) -> None:
    """問題のみの公開停止（単語帳自体は残す）。単語帳デッキが未公開でも冪等に成功する。"""
    deck = _find_vocab_deck(db, account, local_deck_id)
    if deck is None:
        return
    db.query(PublishedQuizQuestion).filter(
        PublishedQuizQuestion.vocab_deck_snapshot_id == deck.id
    ).delete()
    db.commit()
