"""単語帳のAPI（開発Todo_単語帳_v1.0 要件A）。AI呼び出しは一切含まない。

API層はドメイン例外をHTTPへ変換するのみ（CODING_RULES.md「サービス層でのHTTP例外の
送出禁止」）。出題・判定・集計の実体は`vocab_service`（AI非依存）が担う。
"""

import datetime as dt
import random

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.constants.app_setting_keys import (
    VOCAB_MASTERY_STREAK,
    VOCAB_SESSION_MAX_QUESTIONS,
    VOCAB_WEAK_ACCURACY_PERCENT,
)
from app.constants.enums import VocabQuizMode
from app.database import get_db
from app.models.vocab import VocabCard, VocabDeck
from app.schemas.quiz import QuizGenerateResultRead
from app.schemas.vocab import (
    VocabAnswerRequest,
    VocabAnswerResultRead,
    VocabCardCheckRequest,
    VocabCardCreateRequest,
    VocabCardRead,
    VocabCardUpdateRequest,
    VocabDeckCreateRequest,
    VocabDeckRead,
    VocabDeckReorderRequest,
    VocabDeckUpdateRequest,
    VocabExportRead,
    VocabImportConfirmRead,
    VocabImportConfirmRequest,
    VocabImportErrorRead,
    VocabImportPreviewRead,
    VocabImportPreviewRequest,
    VocabImportRowRead,
    VocabQuizOptionRead,
    VocabQuizQuestionRead,
    VocabQuizSessionRead,
    VocabQuizSessionRequest,
    VocabTermSuggestionAcceptRequest,
    VocabTermSuggestionGenerateRequest,
    VocabTermSuggestionListRead,
    VocabTermSuggestionRead,
)
from app.services import (
    goal_service,
    milestone_service_common,
    quiz_service,
    setting_reader,
    vocab_quiz_generation_service,
    vocab_service,
    vocab_term_suggestion_service,
)
from app.services.exceptions import ValidationError

router = APIRouter(tags=["vocab"])

_CHOICE_MODES = (VocabQuizMode.CHOICE_TERM_TO_MEANING, VocabQuizMode.CHOICE_MEANING_TO_TERM)
#: 4択に最低限必要なカード数（対象カード本体＋誤答3件）。
_MIN_CARDS_FOR_CHOICE = 4


def _deck_read(deck: VocabDeck, card_count: int, mastered_card_count: int) -> VocabDeckRead:
    return VocabDeckRead(
        id=deck.id,
        goal_id=deck.goal_id,
        name=deck.name,
        description=deck.description,
        use_in_ai=deck.use_in_ai,
        display_order=deck.display_order,
        card_count=card_count,
        mastered_card_count=mastered_card_count,
    )


def _card_read(
    card: VocabCard, stats: vocab_service.VocabCardStats, is_mastered: bool
) -> VocabCardRead:
    return VocabCardRead(
        id=card.id,
        deck_id=card.deck_id,
        term=card.term,
        meaning=card.meaning,
        aliases=card.aliases,
        note=card.note,
        is_checked=card.is_checked,
        display_order=card.display_order,
        correct_count=stats.correct_count,
        incorrect_count=stats.incorrect_count,
        accuracy_percent=stats.accuracy_percent,
        consecutive_incorrect=stats.consecutive_incorrect,
        last_answered_at=stats.last_answered_at,
        is_mastered=is_mastered,
    )


def _mastery_streak(session: Session) -> int:
    return setting_reader.get_int(session, VOCAB_MASTERY_STREAK)


def _card_read_single(session: Session, card: VocabCard) -> VocabCardRead:
    """既存カード1件分の応答を組み立てる（成績・習得状態を再計算、N+1にはならない
    単発エンドポイント用）。"""
    stats = vocab_service.compute_card_stats(session, [card.id])[card.id]
    is_mastered = card.id in vocab_service.compute_mastered_card_ids(
        session, [card.id], _mastery_streak(session)
    )
    return _card_read(card, stats, is_mastered)


@router.get("/goals/{goal_id}/vocab-decks", response_model=list[VocabDeckRead])
def list_vocab_decks(goal_id: int, session: Session = Depends(get_db)) -> list[VocabDeckRead]:
    goal_service.get_goal(session, goal_id)
    decks = vocab_service.list_decks_for_goal(session, goal_id)
    deck_ids = [deck.id for deck in decks]
    card_counts = vocab_service.count_cards_by_deck(session, deck_ids)
    mastered_counts = vocab_service.compute_mastered_card_counts_by_deck(
        session, deck_ids, _mastery_streak(session)
    )
    return [
        _deck_read(deck, card_counts.get(deck.id, 0), mastered_counts.get(deck.id, 0))
        for deck in decks
    ]


@router.post("/goals/{goal_id}/vocab-decks", response_model=VocabDeckRead)
def create_vocab_deck(
    goal_id: int, payload: VocabDeckCreateRequest, session: Session = Depends(get_db)
) -> VocabDeckRead:
    goal = goal_service.get_goal(session, goal_id)
    deck = vocab_service.create_deck(
        session, goal, name=payload.name, description=payload.description
    )
    session.commit()
    return _deck_read(deck, card_count=0, mastered_card_count=0)


@router.put("/goals/{goal_id}/vocab-decks/order")
def reorder_vocab_decks(
    goal_id: int, payload: VocabDeckReorderRequest, session: Session = Depends(get_db)
) -> dict[str, bool]:
    goal = goal_service.get_goal(session, goal_id)
    vocab_service.reorder_decks(session, goal, payload.ordered_deck_ids)
    session.commit()
    return {"success": True}


def _single_deck_read(session: Session, deck: VocabDeck) -> VocabDeckRead:
    card_count = vocab_service.count_cards_by_deck(session, [deck.id]).get(deck.id, 0)
    mastered_count = vocab_service.compute_mastered_card_counts_by_deck(
        session, [deck.id], _mastery_streak(session)
    ).get(deck.id, 0)
    return _deck_read(deck, card_count, mastered_count)


@router.get("/vocab-decks/{deck_id}", response_model=VocabDeckRead)
def get_vocab_deck(deck_id: int, session: Session = Depends(get_db)) -> VocabDeckRead:
    deck = vocab_service.get_deck(session, deck_id)
    return _single_deck_read(session, deck)


@router.patch("/vocab-decks/{deck_id}", response_model=VocabDeckRead)
def update_vocab_deck(
    deck_id: int, payload: VocabDeckUpdateRequest, session: Session = Depends(get_db)
) -> VocabDeckRead:
    deck = vocab_service.get_deck(session, deck_id)
    vocab_service.update_deck(
        session,
        deck,
        name=payload.name,
        description=payload.description,
        use_in_ai=payload.use_in_ai,
    )
    session.commit()
    return _single_deck_read(session, deck)


@router.delete("/vocab-decks/{deck_id}")
def delete_vocab_deck(deck_id: int, session: Session = Depends(get_db)) -> dict[str, bool]:
    deck = vocab_service.get_deck(session, deck_id)
    vocab_service.delete_deck(session, deck)
    session.commit()
    return {"success": True}


@router.get("/vocab-decks/{deck_id}/cards", response_model=list[VocabCardRead])
def list_vocab_cards(
    deck_id: int,
    filter: str = "ALL",
    sort: str = "REGISTERED",
    session: Session = Depends(get_db),
) -> list[VocabCardRead]:
    vocab_service.get_deck(session, deck_id)
    cards = vocab_service.list_cards_for_deck(session, deck_id)
    card_ids = [card.id for card in cards]
    stats_by_card = vocab_service.compute_card_stats(session, card_ids)
    mastered_card_ids = frozenset(
        vocab_service.compute_mastered_card_ids(session, card_ids, _mastery_streak(session))
    )
    weak_accuracy_percent = setting_reader.get_int(session, VOCAB_WEAK_ACCURACY_PERCENT)
    filtered = vocab_service.filter_cards(
        cards,
        stats_by_card,
        filter_key=filter,
        weak_accuracy_percent=weak_accuracy_percent,
        mastered_card_ids=mastered_card_ids,
    )
    sorted_cards = vocab_service.sort_cards(filtered, stats_by_card, sort_key=sort)
    return [
        _card_read(card, stats_by_card[card.id], card.id in mastered_card_ids)
        for card in sorted_cards
    ]


@router.post("/vocab-decks/{deck_id}/cards", response_model=VocabCardRead)
def create_vocab_card(
    deck_id: int, payload: VocabCardCreateRequest, session: Session = Depends(get_db)
) -> VocabCardRead:
    deck = vocab_service.get_deck(session, deck_id)
    card = vocab_service.create_card(
        session,
        deck,
        term=payload.term,
        meaning=payload.meaning,
        aliases=payload.aliases,
        note=payload.note,
    )
    session.commit()
    stats = vocab_service.compute_card_stats(session, [card.id])[card.id]
    return _card_read(card, stats, is_mastered=False)


@router.patch("/vocab-cards/{card_id}", response_model=VocabCardRead)
def update_vocab_card(
    card_id: int, payload: VocabCardUpdateRequest, session: Session = Depends(get_db)
) -> VocabCardRead:
    card = vocab_service.get_card(session, card_id)
    vocab_service.update_card(
        session,
        card,
        term=payload.term,
        meaning=payload.meaning,
        aliases=payload.aliases,
        note=payload.note,
    )
    quiz_service.delete_questions_for_vocab_card(session, card.id)
    session.commit()
    return _card_read_single(session, card)


@router.patch("/vocab-cards/{card_id}/check", response_model=VocabCardRead)
def check_vocab_card(
    card_id: int, payload: VocabCardCheckRequest, session: Session = Depends(get_db)
) -> VocabCardRead:
    card = vocab_service.get_card(session, card_id)
    vocab_service.set_card_checked(session, card, payload.is_checked)
    session.commit()
    return _card_read_single(session, card)


@router.delete("/vocab-cards/{card_id}")
def delete_vocab_card(card_id: int, session: Session = Depends(get_db)) -> dict[str, bool]:
    card = vocab_service.get_card(session, card_id)
    vocab_service.delete_card(session, card)
    session.commit()
    return {"success": True}


@router.post("/vocab-decks/{deck_id}/cards/import-preview", response_model=VocabImportPreviewRead)
def preview_vocab_import(
    deck_id: int, payload: VocabImportPreviewRequest, session: Session = Depends(get_db)
) -> VocabImportPreviewRead:
    deck = vocab_service.get_deck(session, deck_id)
    preview = vocab_service.parse_bulk_import(session, deck, payload.text)
    return VocabImportPreviewRead(
        rows=[
            VocabImportRowRead(
                line_number=row.line_number,
                term=row.term,
                meaning=row.meaning,
                aliases=row.aliases,
                note=row.note,
            )
            for row in preview.rows
        ],
        errors=[
            VocabImportErrorRead(line_number=error.line_number, reason=error.reason)
            for error in preview.errors
        ],
        duplicate_count=len(preview.duplicate_line_numbers),
    )


@router.post("/vocab-decks/{deck_id}/cards/import", response_model=VocabImportConfirmRead)
def confirm_vocab_import(
    deck_id: int, payload: VocabImportConfirmRequest, session: Session = Depends(get_db)
) -> VocabImportConfirmRead:
    deck = vocab_service.get_deck(session, deck_id)
    rows = [
        vocab_service.VocabImportRow(
            line_number=index,
            term=row.term,
            meaning=row.meaning,
            aliases=row.aliases,
            note=row.note,
        )
        for index, row in enumerate(payload.rows, start=1)
    ]
    created_count = vocab_service.confirm_bulk_import(session, deck, rows)
    session.commit()
    return VocabImportConfirmRead(created_count=created_count)


@router.get("/vocab-decks/{deck_id}/export", response_model=VocabExportRead)
def export_vocab_deck(deck_id: int, session: Session = Depends(get_db)) -> VocabExportRead:
    deck = vocab_service.get_deck(session, deck_id)
    return VocabExportRead(text=vocab_service.export_deck(session, deck))


def _prompt_and_reveal(mode: VocabQuizMode, card: VocabCard) -> tuple[str, str | None]:
    if mode == VocabQuizMode.FLASH_TERM_TO_MEANING:
        return card.term, card.meaning
    if mode == VocabQuizMode.FLASH_MEANING_TO_TERM:
        return card.meaning, card.term
    if mode == VocabQuizMode.TYPED_MEANING_TO_TERM:
        return card.meaning, None
    if mode == VocabQuizMode.CHOICE_TERM_TO_MEANING:
        return card.term, None
    return card.meaning, None  # CHOICE_MEANING_TO_TERM


def _choice_field(mode: VocabQuizMode) -> str:
    #: 選択肢に表示する欄（出題の欄と逆）。
    return "meaning" if mode == VocabQuizMode.CHOICE_TERM_TO_MEANING else "term"


@router.post("/vocab-decks/{deck_id}/quiz-sessions", response_model=VocabQuizSessionRead)
def start_vocab_quiz_session(
    deck_id: int, payload: VocabQuizSessionRequest, session: Session = Depends(get_db)
) -> VocabQuizSessionRead:
    """問題集の出題セッションを開始する。サーバーにセッション自体は保存しない。"""
    deck_cards = vocab_service.list_cards_for_deck(session, deck_id)
    if payload.mode in _CHOICE_MODES and len(deck_cards) < _MIN_CARDS_FOR_CHOICE:
        raise ValidationError(
            f"CHOICE modes require at least {_MIN_CARDS_FOR_CHOICE} cards in the deck"
        )
    max_questions = setting_reader.get_int(session, VOCAB_SESSION_MAX_QUESTIONS)
    if payload.question_count < 1 or payload.question_count > max_questions:
        raise ValidationError(f"question_count must be between 1 and {max_questions}")

    stats_by_card = vocab_service.compute_card_stats(session, [c.id for c in deck_cards])
    weak_accuracy_percent = setting_reader.get_int(session, VOCAB_WEAK_ACCURACY_PERCENT)
    filtered = vocab_service.filter_cards(
        deck_cards,
        stats_by_card,
        filter_key=payload.filter,
        weak_accuracy_percent=weak_accuracy_percent,
    )
    rng = random.Random()
    candidates = vocab_service.select_session_cards(
        filtered,
        stats_by_card,
        order_key=payload.order,
        question_count=len(filtered),
        rng=rng,
    )

    questions: list[VocabQuizQuestionRead] = []
    excluded_count = 0
    for card in candidates:
        if len(questions) >= payload.question_count:
            break
        prompt, reveal = _prompt_and_reveal(payload.mode, card)
        if payload.mode in _CHOICE_MODES:
            option_ids = vocab_service.build_choice_option_ids(
                deck_cards, card, field=_choice_field(payload.mode), rng=rng
            )
            if option_ids is None:
                excluded_count += 1
                continue
            field = _choice_field(payload.mode)
            cards_by_id = {c.id: c for c in deck_cards}
            options = [
                VocabQuizOptionRead(card_id=option_id, text=getattr(cards_by_id[option_id], field))
                for option_id in option_ids
            ]
            questions.append(
                VocabQuizQuestionRead(card_id=card.id, prompt=prompt, reveal=None, options=options)
            )
        else:
            questions.append(
                VocabQuizQuestionRead(card_id=card.id, prompt=prompt, reveal=reveal, options=None)
            )
    return VocabQuizSessionRead(questions=questions, excluded_count=excluded_count)


@router.post("/vocab-cards/{card_id}/answer", response_model=VocabAnswerResultRead)
def answer_vocab_card(
    card_id: int, payload: VocabAnswerRequest, session: Session = Depends(get_db)
) -> VocabAnswerResultRead:
    card = vocab_service.get_card(session, card_id)
    if payload.mode in (VocabQuizMode.FLASH_TERM_TO_MEANING, VocabQuizMode.FLASH_MEANING_TO_TERM):
        if payload.self_judged_correct is None:
            raise ValidationError("self_judged_correct is required for FLASH modes")
        is_correct = payload.self_judged_correct
    elif payload.mode == VocabQuizMode.TYPED_MEANING_TO_TERM:
        if payload.answer_text is None:
            raise ValidationError("answer_text is required for TYPED_MEANING_TO_TERM")
        is_correct = vocab_service.judge_typed_answer(card, payload.answer_text)
    else:
        if payload.selected_card_id is None:
            raise ValidationError("selected_card_id is required for CHOICE modes")
        is_correct = payload.selected_card_id == card.id
    vocab_service.record_answer(session, card, payload.mode, is_correct)
    session.commit()
    return VocabAnswerResultRead(is_correct=is_correct)


@router.post("/vocab-decks/{deck_id}/quiz-sessions/complete")
def complete_vocab_quiz_session(
    deck_id: int, session: Session = Depends(get_db)
) -> dict[str, bool]:
    """出題セッションを終えた直後に呼ぶ（開発Todo_単語帳_v1.0 要件E E-U3）。既存の記録確定時
    （`milestone_service_common.detect_and_record_for_category`）と同じ判定関数
    （`detect_and_record_new_achievements`、単一目標版）をこの1デッキの目標に対して呼ぶ。
    未お祝いの節目は既存の`GET /goals/{goal_id}/milestones/pending-celebrations`から別途取得する
    （GETに副作用を持たせない方針のため、本APIはレスポンスに節目を含めない）。
    """
    deck = vocab_service.get_deck(session, deck_id)
    goal = goal_service.get_goal(session, deck.goal_id)
    today = goal_service.resolve_today(session)
    milestone_service_common.detect_and_record_new_achievements(session, goal, today)
    session.commit()
    return {"success": True}


@router.post("/vocab-decks/{deck_id}/quiz/generate", response_model=QuizGenerateResultRead)
def generate_vocab_deck_quiz(
    deck_id: int, session: Session = Depends(get_db)
) -> QuizGenerateResultRead:
    """単語帳詳細の「今日の復習の問題を作る」ボタン（開発Todo_単語帳_v1.0 要件B B-U5）。

    `use_in_ai=False`のデッキは何も作らない（`vocab_quiz_generation_service.generate_for_deck`
    側の判定）。`quiz.questions_per_theme`等と同じく、作り直し（既存の未出題分の削除）は
    行わない点がテーマ由来と異なる（カードごとに1問までのため、まだ問題を持たないカードの
    分だけを追加で作る設計、B-U5）。
    """
    deck = vocab_service.get_deck(session, deck_id)
    goal = goal_service.get_goal(session, deck.goal_id)
    created = vocab_quiz_generation_service.generate_for_deck(session, goal, deck)
    session.commit()
    return QuizGenerateResultRead(created=created)


def _suggestion_list_read(
    session: Session, goal_id: int, suggestions: list
) -> VocabTermSuggestionListRead:
    return VocabTermSuggestionListRead(
        suggestions=[
            VocabTermSuggestionRead(
                id=s.id,
                goal_id=s.goal_id,
                record_date=s.record_date,
                term=s.term,
                source_sentence=s.source_sentence,
            )
            for s in suggestions
        ],
        default_deck_id=vocab_service.last_used_deck_id(session, goal_id),
    )


@router.post("/goals/{goal_id}/vocab-suggestions", response_model=VocabTermSuggestionListRead)
def generate_vocab_term_suggestions(
    goal_id: int, payload: VocabTermSuggestionGenerateRequest, session: Session = Depends(get_db)
) -> VocabTermSuggestionListRead:
    """日次報告の確定成功後に画面から呼ぶ（開発Todo_単語帳_v1.0 要件D D-U4）。確定処理
    自体（`finalize_record`）からは呼ばない。
    """
    goal = goal_service.get_goal(session, goal_id)
    suggestions = vocab_term_suggestion_service.generate_suggestions(
        session, goal, payload.record_date
    )
    session.commit()
    return _suggestion_list_read(session, goal_id, suggestions)


@router.get("/goals/{goal_id}/vocab-suggestions", response_model=VocabTermSuggestionListRead)
def list_vocab_term_suggestions(
    goal_id: int, record_date: dt.date, session: Session = Depends(get_db)
) -> VocabTermSuggestionListRead:
    goal_service.get_goal(session, goal_id)
    suggestions = vocab_term_suggestion_service.list_pending(session, goal_id, record_date)
    return _suggestion_list_read(session, goal_id, suggestions)


@router.post(
    "/goals/{goal_id}/vocab-suggestions/{suggestion_id}/accept", response_model=VocabCardRead
)
def accept_vocab_term_suggestion(
    goal_id: int,
    suggestion_id: int,
    payload: VocabTermSuggestionAcceptRequest,
    session: Session = Depends(get_db),
) -> VocabCardRead:
    card = vocab_term_suggestion_service.accept_suggestion(
        session,
        goal_id,
        suggestion_id,
        deck_id=payload.deck_id,
        term=payload.term,
        meaning=payload.meaning,
        aliases=payload.aliases,
    )
    session.commit()
    stats = vocab_service.compute_card_stats(session, [card.id])[card.id]
    return _card_read(card, stats, is_mastered=False)


@router.post("/goals/{goal_id}/vocab-suggestions/{suggestion_id}/dismiss")
def dismiss_vocab_term_suggestion(
    goal_id: int, suggestion_id: int, session: Session = Depends(get_db)
) -> dict[str, bool]:
    vocab_term_suggestion_service.dismiss_suggestion(session, goal_id, suggestion_id)
    session.commit()
    return {"success": True}
