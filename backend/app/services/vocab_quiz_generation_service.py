"""単語帳由来の今日の復習の問題作り（開発Todo_単語帳_v1.0 要件B）。

単語帳のカード（用語・意味・別名）を材料にAIへ送り、復習クイズ（`quiz_question`）を
作る。単語帳の問題集（要件A、`vocab_service`）はAIを使わないが、本サービスは今日の復習
専用に「まだ問題を持たないカード」から4択クイズを生成する（B-U5）。

対象はACTIVEな資格試験の目標の、`use_in_ai=True`の単語帳のカードのみ（B-U1・B-D13）。
起動時バッチ（`run_all`、1回あたり`vocab.quiz_cards_per_startup`枚まで、対象ゴール横断の
合計件数に対する上限、B-D9）と、単語帳詳細の「今日の復習の問題を作る」ボタン
（`generate_for_deck`、そのデッキ内で同じ上限）の両方から呼ばれる。

出典は「出典: #カードID」形式（テーマ由来の日付形式とは異なる）。検証は1問ずつ行い、
不合格の問題だけを捨てる：①形式（`quiz_block_parsing`の共通解析）②出典カードIDがその回に
送った集合に含まれる③4択が正規化後にすべて異なる④出典カードの用語または別名が問題文か
正解の選択肢に含まれる（根拠検証、AIの作り話を捨てる）⑤1回の生成で1枚のカードにつき1問まで。
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import secrets
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import question_safety
from app.ai.question_safety import contains_forbidden_term
from app.constants.app_setting_keys import (
    RECAP_CLASSIFY_CHUNK_CHARS,
    VOCAB_QUIZ_CARDS_PER_STARTUP,
)
from app.constants.enums import AiPurpose, ConversationScope, GoalCategory, GoalStatus
from app.models.goal import Goal
from app.models.quiz import QuizQuestion
from app.models.vocab import VocabCard, VocabDeck
from app.services import (
    goal_service,
    quiz_block_parsing,
    recap_service,
    setting_reader,
    theme_ai_dispatch,
    vocab_service,
)
from app.services.vocab_service import normalize_for_vocab_match, vocab_match_keys

_logger = logging.getLogger(__name__)

#: 出典行（「#カードID」形式）を解釈する正規表現。
_CITATION_PATTERN = re.compile(r"^#(\d+)$")


@dataclass(frozen=True)
class _CardChunkItem:
    """`recap_service.chunk_by_chars`が要求する`.text`を持つ、カード1枚分の入力行。"""

    card_id: int
    text: str


def _format_card_line(card: VocabCard) -> str:
    """AIへ送るカード1枚分の行「#カードID 用語／意味／別名」を組み立てる。

    別名が無ければ「／別名」部分を省略する（2フィールドのみ）。複数別名は「、」で連結する
    （B-D10）。山括弧は全角化し、区切り（<<<CARDS-{{nonce}}>>>）を偽造できないようにする
    （question_safety.DELIMITER_REPLACEMENTS、プロンプト注入対策）。
    """
    term = card.term.translate(question_safety.DELIMITER_REPLACEMENTS)
    meaning = card.meaning.translate(question_safety.DELIMITER_REPLACEMENTS)
    line = f"#{card.id} {term}／{meaning}"
    aliases = [alias.strip() for alias in (card.aliases or "").splitlines() if alias.strip()]
    if aliases:
        joined = "、".join(
            alias.translate(question_safety.DELIMITER_REPLACEMENTS) for alias in aliases
        )
        line += f"／{joined}"
    return line


def _candidate_cards_query(deck_ids: list[int] | None = None):
    """まだ`quiz_question`を持たないカードを、チェック付き→新しく登録した順
    （`is_checked DESC, id DESC`、B-D8）で返すクエリ。ACTIVEな資格試験の目標・
    `use_in_ai=True`の単語帳のみを対象とする（B-U1・B-D13）。
    """
    stmt = (
        select(VocabCard)
        .join(VocabDeck, VocabDeck.id == VocabCard.deck_id)
        .join(Goal, Goal.id == VocabDeck.goal_id)
        .where(
            VocabDeck.use_in_ai.is_(True),
            Goal.status == GoalStatus.ACTIVE,
            Goal.category == GoalCategory.EXAM,
            ~VocabCard.id.in_(
                select(QuizQuestion.vocab_card_id).where(QuizQuestion.vocab_card_id.is_not(None))
            ),
        )
        .order_by(VocabCard.is_checked.desc(), VocabCard.id.desc())
    )
    if deck_ids is not None:
        stmt = stmt.where(VocabCard.deck_id.in_(deck_ids))
    return stmt


def _validate_block(
    block: quiz_block_parsing.ParsedQuestionBlock,
    valid_card_ids: frozenset[int],
    cards_by_id: dict[int, VocabCard],
    seen_card_ids: set[int],
) -> tuple[int, quiz_block_parsing.ParsedQuestionBlock] | None:
    """1ブロックを検証する。不合格なら`None`（呼び出し側は個別に破棄する）。"""
    match = _CITATION_PATTERN.match(block.citation_raw)
    if match is None:
        return None
    card_id = int(match.group(1))
    if card_id not in valid_card_ids or card_id in seen_card_ids:
        return None
    if len({normalize_for_vocab_match(choice) for choice in block.choices}) != 4:
        return None
    card = cards_by_id[card_id]
    evidence_text = normalize_for_vocab_match(
        f"{block.question_text} {block.choices[block.correct_choice_index]}"
    )
    if not any(key in evidence_text for key in vocab_match_keys(card)):
        return None
    return card_id, block


def _send(session: Session, goal: Goal, deck: VocabDeck, variables: dict[str, str]) -> str:
    return theme_ai_dispatch.send_theme_scoped_prompt(
        session,
        goal,
        AiPurpose.VOCAB_QUIZ_GENERATE,
        ConversationScope.VOCAB_QUIZ_GENERATE,
        variables,
        scope_key=f"deck-{deck.id}",
        title=f"単語帳クイズ生成 deck-{deck.id}",
    )


def _generate_for_cards(
    session: Session, goal: Goal, deck: VocabDeck, cards: list[VocabCard]
) -> int:
    """渡されたカード群（既に対象・上限の絞り込み済み）から問題を作る。戻り値は採用数。"""
    eligible = [
        card
        for card in cards
        if not contains_forbidden_term(session, f"{card.term} {card.meaning} {card.aliases or ''}")
    ]
    if not eligible:
        return 0
    cards_by_id = {card.id: card for card in eligible}
    items = [_CardChunkItem(card_id=card.id, text=_format_card_line(card)) for card in eligible]
    chunk_budget = setting_reader.get_int(session, RECAP_CLASSIFY_CHUNK_CHARS)
    created = 0
    for chunk in recap_service.chunk_by_chars(items, chunk_budget):
        valid_card_ids = frozenset(item.card_id for item in chunk)
        nonce = secrets.token_hex(question_safety.NONCE_BYTES)
        response = _send(
            session,
            goal,
            deck,
            {
                "card_count": str(len(chunk)),
                "cards": "\n".join(item.text for item in chunk),
                "nonce": nonce,
            },
        )
        seen_card_ids: set[int] = set()
        for block in quiz_block_parsing.parse_question_blocks(response):
            validated = _validate_block(block, valid_card_ids, cards_by_id, seen_card_ids)
            if validated is None:
                continue
            card_id, parsed = validated
            seen_card_ids.add(card_id)
            session.add(
                QuizQuestion(
                    vocab_card_id=card_id,
                    question_text=parsed.question_text,
                    choice_1=parsed.choices[0],
                    choice_2=parsed.choices[1],
                    choice_3=parsed.choices[2],
                    choice_4=parsed.choices[3],
                    correct_choice_index=parsed.correct_choice_index,
                    explanation=parsed.explanation,
                    citation_date=None,
                    interval_index=0,
                    next_due_date=dt.date.today(),
                )
            )
            created += 1
        session.flush()
    return created


def generate_for_deck(session: Session, goal: Goal, deck: VocabDeck) -> int:
    """単語帳詳細の「今日の復習の問題を作る」ボタン（B-U5）。`use_in_ai=False`のデッキは
    何もしない（対象はuse_in_ai=Trueのみ、B-U1）。上限は起動時バッチと同じ
    `vocab.quiz_cards_per_startup`をそのデッキ単独に適用する（B-D9）。
    """
    if not deck.use_in_ai:
        return 0
    limit = setting_reader.get_int(session, VOCAB_QUIZ_CARDS_PER_STARTUP)
    cards = list(session.scalars(_candidate_cards_query([deck.id]).limit(limit)).all())
    if not cards:
        return 0
    return _generate_for_cards(session, goal, deck, cards)


def run_all(session: Session) -> int:
    """起動時バッチ（B-U5。`main.run_ai_startup_tasks`、既存のテーマ由来クイズ生成
    `quiz_generation_service.run_all`の直後に呼ぶ）。

    対象ゴール横断で合計`vocab.quiz_cards_per_startup`枚まで（B-D9）。デッキ単位で
    AI送信・保存し、1デッキの失敗が他デッキを止めないようデッキごとに取り消して続行する
    （`quiz_generation_service.run_all`と同方式）。戻り値は生成した問題の総件数。
    """
    limit = setting_reader.get_int(session, VOCAB_QUIZ_CARDS_PER_STARTUP)
    cards = list(session.scalars(_candidate_cards_query().limit(limit)).all())
    if not cards:
        return 0
    cards_by_deck: dict[int, list[VocabCard]] = defaultdict(list)
    for card in cards:
        cards_by_deck[card.deck_id].append(card)

    total = 0
    for deck_id, deck_cards in cards_by_deck.items():
        deck = vocab_service.get_deck(session, deck_id)
        goal = goal_service.get_goal(session, deck.goal_id)
        try:
            total += _generate_for_cards(session, goal, deck, deck_cards)
            session.commit()
        except Exception:  # noqa: BLE001 - 1デッキの失敗で起動時処理全体を止めないため意図的に握りつぶす
            _logger.exception("単語帳由来の復習クイズの生成に失敗しました: deck_id=%s", deck_id)
            session.rollback()
    return total
