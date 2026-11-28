"""閲覧API（ガント・単語帳・問題一覧）。セッションCookie必須、account_idで常にフィルタ
（開発Todo_Web公開_v1.0 単位2、D-21）。

問題一覧（`/vocab/{deck_id}/quiz`）は回答前のため正解番号・解説を含めない（D-07）。
"""

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_account, get_db
from app.models.account import PublishAccount
from app.schemas.gantt import GanttSnapshotDetail, GanttSnapshotListItem
from app.schemas.quiz import QuizQuestionPreview
from app.schemas.vocab import VocabDeckDetail, VocabDeckListItem
from app.services import view_service

router = APIRouter(prefix="/view", tags=["view"])


@router.get("/goals", response_model=list[GanttSnapshotListItem])
def list_goals(
    account: PublishAccount = Depends(get_current_account), db: Session = Depends(get_db)
) -> list:
    return view_service.list_gantt_snapshots(db, account)


@router.get("/gantt/{snapshot_id}", response_model=GanttSnapshotDetail)
def get_gantt(
    snapshot_id: int,
    account: PublishAccount = Depends(get_current_account),
    db: Session = Depends(get_db),
) -> GanttSnapshotDetail:
    snapshot = view_service.get_gantt_snapshot(db, account, snapshot_id)
    return GanttSnapshotDetail(
        id=snapshot.id,
        local_goal_id=snapshot.local_goal_id,
        goal_name=snapshot.goal_name,
        items=json.loads(snapshot.items_json),
        columns=json.loads(snapshot.columns_json),
        cells=json.loads(snapshot.cells_json),
        updated_at=snapshot.updated_at,
    )


@router.get("/vocab-decks", response_model=list[VocabDeckListItem])
def list_vocab_decks(
    account: PublishAccount = Depends(get_current_account), db: Session = Depends(get_db)
) -> list[VocabDeckListItem]:
    decks = view_service.list_vocab_decks(db, account)
    return [
        VocabDeckListItem(
            id=deck.id,
            local_deck_id=deck.local_deck_id,
            deck_name=deck.deck_name,
            card_count=len(json.loads(deck.cards_json)),
            updated_at=deck.updated_at,
        )
        for deck in decks
    ]


@router.get("/vocab/{deck_id}", response_model=VocabDeckDetail)
def get_vocab(
    deck_id: int,
    account: PublishAccount = Depends(get_current_account),
    db: Session = Depends(get_db),
) -> VocabDeckDetail:
    deck = view_service.get_vocab_deck(db, account, deck_id)
    return VocabDeckDetail(
        id=deck.id,
        local_deck_id=deck.local_deck_id,
        deck_name=deck.deck_name,
        cards=json.loads(deck.cards_json),
        updated_at=deck.updated_at,
    )


@router.get("/vocab/{deck_id}/quiz", response_model=list[QuizQuestionPreview])
def list_quiz_questions(
    deck_id: int,
    account: PublishAccount = Depends(get_current_account),
    db: Session = Depends(get_db),
) -> list[QuizQuestionPreview]:
    questions = view_service.list_quiz_questions(db, account, deck_id)
    return [
        QuizQuestionPreview(
            id=question.id,
            question_text=question.question_text,
            **view_service.decode_choices(question.choices_json),
        )
        for question in questions
    ]
