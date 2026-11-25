"""日次報告の日記（学んだこと）から、単語帳へ追加する用語の候補を抜き出す
（開発Todo_単語帳_v1.0 要件D）。

AIの役割は「日記の文章から、資格の用語らしい語句を抜き出す」ことだけであり、抜き出した
語句は日記の本文に文字どおり含まれるもの（`question_safety.normalize_for_match`で正規化
した後の部分一致）だけを採用する（開発Todo §0.8 D-U3）。意味はAIに書かせず、意味の下書き
には用語を含む日記の一文（`source_sentence`）をそのまま使う（D-U2）。

提案は日次報告の確定（`finalize_record`）の中では作らない。確定処理自体はこのモジュールを
一切呼ばない（D-U4、確定のレスポンスを遅くしないため確定成功後に画面から別APIを呼ぶ）。
"""

from __future__ import annotations

import re
import secrets
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import question_safety
from app.ai.question_safety import normalize_for_match
from app.constants.app_setting_keys import VOCAB_SUGGEST_MAX_PER_RECORD, VOCAB_TERM_MAX_CHARS
from app.constants.enums import (
    AiPurpose,
    ConversationScope,
    GoalCategory,
    VocabTermSuggestionStatus,
)
from app.models.goal import Goal
from app.models.record import DailyGoalDiary, DailyRecord
from app.models.vocab import VocabCard, VocabDeck, VocabTermSuggestion
from app.services import setting_reader, theme_ai_dispatch, vocab_service
from app.services.exceptions import NotFoundError

#: 日記の文の区切り（。！？・改行）。単純な文字クラスのみで正規表現の連鎖は行わない
#: （ReDoS対策、開発Todo §0.9 D-D7と同じ考え方）。
_SENTENCE_SPLIT_PATTERN = re.compile(r"[。！？\n]")


def _split_sentences(text: str) -> list[str]:
    """日記本文を文単位に分ける（空行は除く、前後の空白は除去済み）。"""
    return [s.strip() for s in _SENTENCE_SPLIT_PATTERN.split(text) if s.strip()]


def _get_diary_learned(session: Session, goal_id: int, record_date: date) -> str | None:
    """指定日・指定目標の日記（学んだこと）を取得する（無ければNone）。"""
    row = (
        session.query(DailyGoalDiary.diary_learned)
        .join(DailyRecord, DailyRecord.id == DailyGoalDiary.daily_record_id)
        .filter(DailyRecord.record_date == record_date, DailyGoalDiary.goal_id == goal_id)
        .first()
    )
    return row[0] if row else None


def _excluded_vocab_match_keys(session: Session, goal_id: int) -> set[str]:
    """同じ目標で既に提案済み（status不問）・既に単語帳にある用語・別名の照合キー一覧
    （開発Todo §0.8 D-U5）。

    `vocab_service.normalize_for_vocab_match`（カタカナ→ひらがな統一込み）基準で揃える。
    単語帳内の既存の重複判定（`judge_typed_answer`・一括登録・`build_glossary_reference`等）
    と同じ基準にしないと、カタカナ/ひらがな表記違いの重複を検知できない
    （dry-reviewerレビューで検出、2026-11-21。`term_key`列自体は`normalize_for_match`で
    保存するが、それは重複防止の照合基準としては不十分だったため、除外判定はこの基準に
    独立させる）。
    """
    keys: set[str] = {
        vocab_service.normalize_for_vocab_match(term)
        for (term,) in session.query(VocabTermSuggestion.term).filter(
            VocabTermSuggestion.goal_id == goal_id
        )
    }
    deck_ids = [deck.id for deck in vocab_service.list_decks_for_goal(session, goal_id)]
    if deck_ids:
        cards = session.scalars(select(VocabCard).where(VocabCard.deck_id.in_(deck_ids))).all()
        for card in cards:
            keys.update(vocab_service.build_vocab_match_keys(card))
    return {key for key in keys if key}


def _extract_candidates(
    *,
    response: str,
    sentences: list[str],
    term_max_chars: int,
    max_terms: int,
    excluded_vocab_keys: set[str],
) -> list[tuple[str, str, str]]:
    """AI応答（1行1語句）を解析し、日記に文字どおり含まれる語句だけを採用する。

    戻り値は`(term, term_key, source_sentence)`のリスト（採用順）。長すぎる行は正規化・
    一致判定より先に捨てる（D-D7）。`max_terms`に達したら残りの行は読まない（D-D8）。

    日記本文への部分一致判定（`term_key`、D-U3の明示指示どおり`normalize_for_match`）と、
    重複除外の判定（`vocab_key`、`normalize_for_vocab_match`）は別の正規化基準を使う。前者は
    「日記に文字どおり含まれるか」、後者は「単語帳の既存の重複判定と同じ基準で既に提案・
    登録済みか」であり、意味が異なるため（dry-reviewerレビューで検出、2026-11-21）。
    """
    normalized_sentences = [(sentence, normalize_for_match(sentence)) for sentence in sentences]
    seen_vocab_keys = set(excluded_vocab_keys)
    candidates: list[tuple[str, str, str]] = []
    for raw_line in response.splitlines():
        if len(candidates) >= max_terms:
            break
        line = raw_line.strip()
        if not line or len(line) > term_max_chars:
            continue
        term_key = normalize_for_match(line)
        vocab_key = vocab_service.normalize_for_vocab_match(line)
        # term_keyが空になる行は実質的に構築できない（normalize_for_matchは空白除去のみで
        # 文字の削除は行わないため）が、空文字列は「どの文にも部分一致してしまう」ため
        # 安全側のガードとして残す（not line の時点で弾けないケースへの保険）。
        if not term_key or vocab_key in seen_vocab_keys:
            continue
        source_sentence = next(
            (original for original, normalized in normalized_sentences if term_key in normalized),
            None,
        )
        if source_sentence is None:
            continue
        seen_vocab_keys.add(vocab_key)
        candidates.append((line, term_key, source_sentence))
    return candidates


def generate_suggestions(
    session: Session, goal: Goal, record_date: date
) -> list[VocabTermSuggestion]:
    """その日の日記からAIが用語候補を抜き出し、PENDINGの提案として保存する。

    資格試験（EXAM）以外の目標はサイレントに空を返す（開発Todo §0.9 D-D1）。既に同じ
    (goal_id, record_date)に提案行があれば、AI呼び出しを行わずその日のPENDING一覧を返す
    （D-D3、AI利用枠の浪費を防ぐ）。日記が無い・禁止語を含む場合もAI呼び出しを行わない。
    """
    if goal.category != GoalCategory.EXAM:
        return []

    existing = list(
        session.scalars(
            select(VocabTermSuggestion).where(
                VocabTermSuggestion.goal_id == goal.id,
                VocabTermSuggestion.record_date == record_date,
            )
        ).all()
    )
    if existing:
        return [s for s in existing if s.status == VocabTermSuggestionStatus.PENDING]

    diary_text = _get_diary_learned(session, goal.id, record_date)
    if not diary_text or not diary_text.strip():
        return []
    if question_safety.contains_forbidden_term(session, diary_text):
        return []

    max_terms = setting_reader.get_int(session, VOCAB_SUGGEST_MAX_PER_RECORD)
    term_max_chars = setting_reader.get_int(session, VOCAB_TERM_MAX_CHARS)
    nonce = secrets.token_hex(question_safety.NONCE_BYTES)
    response = theme_ai_dispatch.send_theme_scoped_prompt(
        session,
        goal,
        AiPurpose.VOCAB_TERM_EXTRACT,
        ConversationScope.VOCAB_TERM_EXTRACT,
        {
            "diary_text": diary_text.translate(question_safety.DELIMITER_REPLACEMENTS),
            "max_terms": str(max_terms),
            "nonce": nonce,
        },
        scope_key=f"record-{record_date.isoformat()}",
        title=f"単語帳の用語提案 record-{record_date.isoformat()}",
    )

    excluded_vocab_keys = _excluded_vocab_match_keys(session, goal.id)
    candidates = _extract_candidates(
        response=response,
        sentences=_split_sentences(diary_text),
        term_max_chars=term_max_chars,
        max_terms=max_terms,
        excluded_vocab_keys=excluded_vocab_keys,
    )

    created = [
        VocabTermSuggestion(
            goal_id=goal.id,
            record_date=record_date,
            term=term,
            term_key=term_key,
            source_sentence=source_sentence,
            status=VocabTermSuggestionStatus.PENDING,
        )
        for term, term_key, source_sentence in candidates
    ]
    session.add_all(created)
    session.flush()
    return created


def list_pending(session: Session, goal_id: int, record_date: date) -> list[VocabTermSuggestion]:
    """指定日のPENDINGの提案一覧を返す（開発Todo §0.9 D-D15、record_dateは必須）。"""
    return list(
        session.scalars(
            select(VocabTermSuggestion)
            .where(
                VocabTermSuggestion.goal_id == goal_id,
                VocabTermSuggestion.record_date == record_date,
                VocabTermSuggestion.status == VocabTermSuggestionStatus.PENDING,
            )
            .order_by(VocabTermSuggestion.id)
        ).all()
    )


def get_suggestion(session: Session, goal_id: int, suggestion_id: int) -> VocabTermSuggestion:
    """他の目標の提案IDを指定された場合も404と同様に扱う（`milestone_service_common.
    mark_celebrated`と同じ方式、開発Todo §0.9 D-D10）。
    """
    row = session.get(VocabTermSuggestion, suggestion_id)
    if row is None or row.goal_id != goal_id:
        raise NotFoundError("VocabTermSuggestion", suggestion_id)
    return row


def _get_deck_for_goal(session: Session, goal_id: int, deck_id: int) -> VocabDeck:
    """他の目標の単語帳IDを指定された場合も404と同様に扱う（D-D10の横展開）。"""
    deck = session.get(VocabDeck, deck_id)
    if deck is None or deck.goal_id != goal_id:
        raise NotFoundError("VocabDeck", deck_id)
    return deck


def accept_suggestion(
    session: Session,
    goal_id: int,
    suggestion_id: int,
    *,
    deck_id: int,
    term: str,
    meaning: str,
    aliases: str | None,
) -> VocabCard:
    """提案を採用し、単語帳へカードを追加する（既存の`vocab_service.create_card`を
    そのまま呼ぶ。文字数検証・容量上限は既存のまま、D-D9）。
    """
    suggestion = get_suggestion(session, goal_id, suggestion_id)
    deck = _get_deck_for_goal(session, goal_id, deck_id)
    card = vocab_service.create_card(session, deck, term=term, meaning=meaning, aliases=aliases)
    suggestion.status = VocabTermSuggestionStatus.ADDED
    session.flush()
    return card


def dismiss_suggestion(session: Session, goal_id: int, suggestion_id: int) -> VocabTermSuggestion:
    """提案を見送る。見送った用語も、同じ目標では二度と提案しない（D-U5、term_keyが
    残るため再提案されない）。
    """
    suggestion = get_suggestion(session, goal_id, suggestion_id)
    suggestion.status = VocabTermSuggestionStatus.DISMISSED
    session.flush()
    return suggestion
