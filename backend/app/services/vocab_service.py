"""単語帳（開発Todo_単語帳_v1.0 要件A）のデッキ/カードCRUD・一括登録・成績集計・
出題選択・判定。AI呼び出しは一切含まない（要件A §0 U2）。

成績（正答数・誤答数・正答率・連続誤答数・最終解答日）は保存せず、`vocab_answer_log`
から都度算出する（開発Todo §0 U6）。複数カード分はまとめて1回のクエリで取得し、
Python側で集計することでN+1を回避する（`compute_card_stats`）。
"""

from __future__ import annotations

import csv
import io
import random
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import question_safety
from app.ai.question_safety import normalize_for_match
from app.constants.app_setting_keys import (
    VOCAB_DECK_MAX_CARDS,
    VOCAB_IMPORT_MAX_ROWS,
    VOCAB_MEANING_MAX_CHARS,
    VOCAB_TERM_MAX_CHARS,
    VOCAB_WEAK_ACCURACY_PERCENT,
)
from app.constants.enums import GoalCategory, GoalStatus, VocabQuizMode
from app.models.base import utcnow
from app.models.goal import Goal
from app.models.vocab import VocabAnswerLog, VocabCard, VocabDeck
from app.services import setting_reader
from app.services.exceptions import (
    NotFoundError,
    ValidationError,
    VocabDeckCardLimitExceededError,
    VocabDeckGoalCategoryError,
    VocabImportTooManyRowsError,
)

#: カタカナ→ひらがな変換表（Unicode符号点のオフセット、「ァ」(U+30A1)〜「ヶ」(U+30F6)が
#: 対応するひらがなへ60移動した位置にある範囲のみ変換する）。
_KATAKANA_START = ord("ァ")
_KATAKANA_END = ord("ヶ")
_KATAKANA_TO_HIRAGANA_OFFSET = ord("ぁ") - ord("ァ")


def normalize_for_vocab_match(text: str) -> str:
    """単語帳の用語照合用に正規化する（`normalize_for_match`に加えてカタカナをひらがなへ
    統一する）。既存の禁止語判定（`question_safety.normalize_for_match`）の挙動は変えず、
    別関数として追加する（利用者プロンプトの明示指示）。
    """
    normalized = normalize_for_match(text)
    return "".join(
        chr(ord(ch) + _KATAKANA_TO_HIRAGANA_OFFSET)
        if _KATAKANA_START <= ord(ch) <= _KATAKANA_END
        else ch
        for ch in normalized
    )


# ---------------------------------------------------------------------------
# デッキCRUD
# ---------------------------------------------------------------------------


def get_deck(session: Session, deck_id: int) -> VocabDeck:
    deck = session.get(VocabDeck, deck_id)
    if deck is None:
        raise NotFoundError("VocabDeck", deck_id)
    return deck


def list_decks_for_goal(session: Session, goal_id: int) -> list[VocabDeck]:
    return list(
        session.scalars(
            select(VocabDeck)
            .where(VocabDeck.goal_id == goal_id)
            .order_by(VocabDeck.display_order, VocabDeck.id)
        ).all()
    )


def last_used_deck_id(session: Session, goal_id: int) -> int | None:
    """その目標で「最後に使った単語帳」（直近にカードを追加したデッキ）のIDを返す
    （開発Todo_単語帳_v1.0 要件D、提案の追加先デッキの初期値、D-D5）。

    「使った」をカード追加のタイミングで解釈し、その目標の全デッキを通じて直近に作成された
    `VocabCard`が属するデッキ（`VocabCard.id`降順で1件）を返す。1件もカードが無い目標は
    `display_order`最小のデッキ（`list_decks_for_goal`の並び順の先頭）を返す。デッキが
    1つも無い場合は`None`を返す。
    """
    deck_ids = [deck.id for deck in list_decks_for_goal(session, goal_id)]
    if not deck_ids:
        return None
    latest_deck_id = session.scalars(
        select(VocabCard.deck_id)
        .where(VocabCard.deck_id.in_(deck_ids))
        .order_by(VocabCard.id.desc())
        .limit(1)
    ).first()
    return latest_deck_id if latest_deck_id is not None else deck_ids[0]


def _next_display_order(session: Session, column, condition) -> int:
    """`column`の最大値+1を返す（0件なら0）。`len(既存件数)`による採番は、中間の行が
    削除された後に既存のdisplay_orderと衝突しうるため使わない（dry-reviewerレビューで
    検出、2026-11-15。`material_service.create_material`と同じ`max+1`方式）。
    """
    current_max = session.query(func.max(column)).filter(condition).scalar()
    return 0 if current_max is None else current_max + 1


def create_deck(session: Session, goal: Goal, *, name: str, description: str | None) -> VocabDeck:
    """単語帳を作成する。対象goalが資格試験（EXAM）以外なら拒否する（開発Todo §0 U1）。"""
    if goal.category != GoalCategory.EXAM:
        raise VocabDeckGoalCategoryError(goal.id)
    next_order = _next_display_order(session, VocabDeck.display_order, VocabDeck.goal_id == goal.id)
    deck = VocabDeck(
        goal_id=goal.id,
        name=name,
        description=description,
        use_in_ai=True,
        display_order=next_order,
    )
    session.add(deck)
    session.flush()
    return deck


def update_deck(
    session: Session,
    deck: VocabDeck,
    *,
    name: str | None = None,
    description: str | None = None,
    use_in_ai: bool | None = None,
) -> VocabDeck:
    if name is not None:
        deck.name = name
    if description is not None:
        deck.description = description
    if use_in_ai is not None:
        deck.use_in_ai = use_in_ai
    session.flush()
    return deck


def delete_deck(session: Session, deck: VocabDeck) -> None:
    session.delete(deck)
    session.flush()


def reorder_decks(session: Session, goal: Goal, ordered_deck_ids: list[int]) -> None:
    """渡された順序でデッキの`display_order`を振り直す。対象の目標に属さないデッキが
    含まれる場合は拒否する（`material_service`のsubject所有関係検証と同じ考え方）。
    """
    decks = list_decks_for_goal(session, goal.id)
    decks_by_id = {deck.id: deck for deck in decks}
    if set(ordered_deck_ids) != set(decks_by_id):
        raise ValidationError("ordered_deck_ids must contain exactly this goal's deck ids")
    for index, deck_id in enumerate(ordered_deck_ids):
        decks_by_id[deck_id].display_order = index
    session.flush()


# ---------------------------------------------------------------------------
# カードCRUD
# ---------------------------------------------------------------------------


def get_card(session: Session, card_id: int) -> VocabCard:
    card = session.get(VocabCard, card_id)
    if card is None:
        raise NotFoundError("VocabCard", card_id)
    return card


def list_cards_for_deck(session: Session, deck_id: int) -> list[VocabCard]:
    return list(
        session.scalars(
            select(VocabCard)
            .where(VocabCard.deck_id == deck_id)
            .order_by(VocabCard.display_order, VocabCard.id)
        ).all()
    )


def count_cards_by_deck(session: Session, deck_ids: list[int]) -> dict[int, int]:
    """複数デッキのカード件数を1回の問い合わせで返す（デッキ一覧表示用、N+1禁止。
    `quiz_service.count_questions_by_theme`と同じ方針、performance-reviewerレビューで
    検出、2026-11-15）。
    """
    if not deck_ids:
        return {}
    rows = session.execute(
        select(VocabCard.deck_id, func.count(VocabCard.id))
        .where(VocabCard.deck_id.in_(deck_ids))
        .group_by(VocabCard.deck_id)
    ).all()
    return dict(rows)


def get_deck_info_for_cards(session: Session, card_ids: list[int]) -> dict[int, tuple[int, str]]:
    """複数カードの単語帳ID・名前を1回の問い合わせで返す（`card_id → (deck_id, deck_name)`）。

    今日の復習（開発Todo_単語帳_v1.0 要件B）が単語帳由来の問題の出所表示・「単語帳で
    確認する」リンクに使う（N+1禁止、`count_cards_by_deck`と同じ方針）。
    """
    if not card_ids:
        return {}
    rows = session.execute(
        select(VocabCard.id, VocabDeck.id, VocabDeck.name)
        .join(VocabDeck, VocabDeck.id == VocabCard.deck_id)
        .where(VocabCard.id.in_(card_ids))
    ).all()
    return {card_id: (deck_id, deck_name) for card_id, deck_id, deck_name in rows}


def _validate_card_fields(session: Session, term: str, meaning: str) -> None:
    term_max = setting_reader.get_int(session, VOCAB_TERM_MAX_CHARS)
    meaning_max = setting_reader.get_int(session, VOCAB_MEANING_MAX_CHARS)
    if not term.strip():
        raise ValidationError("term must not be empty")
    if len(term) > term_max:
        raise ValidationError(f"term must be {term_max} characters or fewer")
    if not meaning.strip():
        raise ValidationError("meaning must not be empty")
    if len(meaning) > meaning_max:
        raise ValidationError(f"meaning must be {meaning_max} characters or fewer")


def _ensure_deck_card_capacity(
    session: Session, deck_id: int, *, current_count: int, adding: int
) -> None:
    max_cards = setting_reader.get_int(session, VOCAB_DECK_MAX_CARDS)
    if current_count + adding > max_cards:
        raise VocabDeckCardLimitExceededError(deck_id, max_cards)


def create_card(
    session: Session,
    deck: VocabDeck,
    *,
    term: str,
    meaning: str,
    aliases: str | None = None,
    note: str | None = None,
) -> VocabCard:
    _validate_card_fields(session, term, meaning)
    existing_cards = list_cards_for_deck(session, deck.id)
    _ensure_deck_card_capacity(session, deck.id, current_count=len(existing_cards), adding=1)
    next_order = max((c.display_order for c in existing_cards), default=-1) + 1
    card = VocabCard(
        deck_id=deck.id,
        term=term,
        meaning=meaning,
        aliases=aliases,
        note=note,
        is_checked=False,
        display_order=next_order,
    )
    session.add(card)
    session.flush()
    return card


def update_card(
    session: Session,
    card: VocabCard,
    *,
    term: str | None = None,
    meaning: str | None = None,
    aliases: str | None = None,
    note: str | None = None,
) -> VocabCard:
    _validate_card_fields(
        session,
        term if term is not None else card.term,
        meaning if meaning is not None else card.meaning,
    )
    if term is not None:
        card.term = term
    if meaning is not None:
        card.meaning = meaning
    if aliases is not None:
        card.aliases = aliases
    if note is not None:
        card.note = note
    session.flush()
    return card


def set_card_checked(session: Session, card: VocabCard, is_checked: bool) -> VocabCard:
    card.is_checked = is_checked
    session.flush()
    return card


def delete_card(session: Session, card: VocabCard) -> None:
    session.delete(card)
    session.flush()


# ---------------------------------------------------------------------------
# 成績集計（都度算出、N+1禁止）
# ---------------------------------------------------------------------------


@dataclass
class VocabCardStats:
    correct_count: int
    incorrect_count: int
    accuracy_percent: float | None
    consecutive_incorrect: int
    last_answered_at: datetime | None


_EMPTY_STATS = VocabCardStats(
    correct_count=0,
    incorrect_count=0,
    accuracy_percent=None,
    consecutive_incorrect=0,
    last_answered_at=None,
)


def compute_card_stats(session: Session, card_ids: list[int]) -> dict[int, VocabCardStats]:
    """複数カードの成績を1回のクエリでまとめて算出する（N+1禁止）。

    SQLiteのウィンドウ関数に依存せず、1回のSELECTで取得した全解答行をPython側で
    カードごとに走査して集計する（移植性・可読性を優先、本コードベースにウィンドウ関数の
    前例が無いため）。並び順は`answered_at`に`id`を第2キーとして付与する（CODING_RULES.md
    「タイムスタンプでの並び替え」）。
    """
    if not card_ids:
        return {}
    rows = session.execute(
        select(VocabAnswerLog.card_id, VocabAnswerLog.is_correct, VocabAnswerLog.answered_at)
        .where(VocabAnswerLog.card_id.in_(card_ids))
        .order_by(VocabAnswerLog.card_id, VocabAnswerLog.answered_at, VocabAnswerLog.id)
    ).all()
    grouped: dict[int, list[tuple[bool, datetime]]] = defaultdict(list)
    for card_id, is_correct, answered_at in rows:
        grouped[card_id].append((is_correct, answered_at))

    stats: dict[int, VocabCardStats] = {}
    for card_id in card_ids:
        logs = grouped.get(card_id)
        if not logs:
            stats[card_id] = _EMPTY_STATS
            continue
        correct = sum(1 for is_correct, _ in logs if is_correct)
        incorrect = len(logs) - correct
        streak = 0
        for is_correct, _ in reversed(logs):
            if is_correct:
                break
            streak += 1
        stats[card_id] = VocabCardStats(
            correct_count=correct,
            incorrect_count=incorrect,
            accuracy_percent=correct / len(logs) * 100,
            consecutive_incorrect=streak,
            last_answered_at=logs[-1][1],
        )
    return stats


def record_answer(session: Session, card: VocabCard, mode: VocabQuizMode, is_correct: bool) -> None:
    """単語帳の問題集での解答を記録する（今日の復習〈要件B〉の解答はここに記録しない）。"""
    session.add(
        VocabAnswerLog(card_id=card.id, mode=mode, is_correct=is_correct, answered_at=utcnow())
    )
    session.flush()


# ---------------------------------------------------------------------------
# 習得の判定（開発Todo_単語帳_v1.0 要件E、都度算出・N+1禁止）
# ---------------------------------------------------------------------------


@dataclass
class VocabMasteryTotals:
    """目標配下の単語帳全体の習得集計（開発Todo_単語帳_v1.0 要件E E-U1・E-U2）。
    節目判定・道のりマップで共通に使う（DRYの原則）。
    """

    total_cards: int
    mastered_cards: int


def compute_mastered_card_ids(
    session: Session, card_ids: list[int], mastery_streak: int
) -> set[int]:
    """直近`mastery_streak`回の解答がすべて正解のカードIDを返す（開発Todo_単語帳_v1.0
    要件E E-U1）。解答回数が`mastery_streak`未満のカードは含めない。節目判定・道のりマップ・
    単語帳画面（一覧・詳細の表示、絞り込み）で「習得」を判定する唯一の定義（DRYの原則）。

    `compute_card_stats`と同じ1回のクエリ・同じ並び順（`answered_at`→`id`、CODING_RULES.md
    「タイムスタンプでの並び替え」）で算出するが、集計の形（正答率等ではなく「直近N件が
    すべて正解か」）が異なるため別関数とする（N+1禁止：card_idsの件数に関わらずクエリ1回）。
    """
    if not card_ids or mastery_streak <= 0:
        return set()
    rows = session.execute(
        select(VocabAnswerLog.card_id, VocabAnswerLog.is_correct)
        .where(VocabAnswerLog.card_id.in_(card_ids))
        .order_by(VocabAnswerLog.card_id, VocabAnswerLog.answered_at, VocabAnswerLog.id)
    ).all()
    grouped: dict[int, list[bool]] = defaultdict(list)
    for card_id, is_correct in rows:
        grouped[card_id].append(is_correct)
    return {
        card_id
        for card_id, answers in grouped.items()
        if len(answers) >= mastery_streak and all(answers[-mastery_streak:])
    }


def compute_goal_vocab_mastery(
    session: Session, goal_id: int, mastery_streak: int
) -> VocabMasteryTotals:
    """その目標のすべての単語帳を通じた習得用語数の合計（節目判定・道のりマップ用、
    開発Todo_単語帳_v1.0 要件E E-U1・E-U2）。単語帳が1つも無い目標は`total_cards=0`で返す。
    """
    deck_ids = [deck.id for deck in list_decks_for_goal(session, goal_id)]
    if not deck_ids:
        return VocabMasteryTotals(total_cards=0, mastered_cards=0)
    card_ids = list(
        session.scalars(select(VocabCard.id).where(VocabCard.deck_id.in_(deck_ids))).all()
    )
    mastered = compute_mastered_card_ids(session, card_ids, mastery_streak)
    return VocabMasteryTotals(total_cards=len(card_ids), mastered_cards=len(mastered))


def compute_mastered_card_counts_by_deck(
    session: Session, deck_ids: list[int], mastery_streak: int
) -> dict[int, int]:
    """複数デッキの習得済みカード数を1回の問い合わせでまとめて返す（デッキ一覧・詳細の
    表示用、N+1禁止。開発Todo_単語帳_v1.0 要件E E-U6。`compute_mastered_card_ids`〈唯一の
    習得判定〉を共有するだけで、判定ロジック自体は再実装しない）。
    """
    if not deck_ids:
        return {}
    rows = session.execute(
        select(VocabCard.id, VocabCard.deck_id).where(VocabCard.deck_id.in_(deck_ids))
    ).all()
    deck_id_by_card_id = dict(rows)
    mastered_card_ids = compute_mastered_card_ids(
        session, list(deck_id_by_card_id), mastery_streak
    )
    counts: dict[int, int] = defaultdict(int)
    for card_id in mastered_card_ids:
        counts[deck_id_by_card_id[card_id]] += 1
    return dict(counts)


# ---------------------------------------------------------------------------
# 一括登録（貼り付け）・エクスポート
# ---------------------------------------------------------------------------


@dataclass
class VocabImportRow:
    line_number: int
    term: str
    meaning: str
    aliases: str | None
    note: str | None


@dataclass
class VocabImportError:
    line_number: int
    reason: str


@dataclass
class VocabImportPreview:
    rows: list[VocabImportRow]
    errors: list[VocabImportError]
    duplicate_line_numbers: list[int]


def _split_import_line(line: str) -> list[str]:
    delimiter = "\t" if "\t" in line else ","
    return next(csv.reader([line], delimiter=delimiter))


def _parse_import_aliases(raw: str) -> str | None:
    """一括登録の別名欄（`|`区切り、利用者プロンプトの明示指示）を、保存形式（改行区切り、
    `judge_typed_answer`が`splitlines()`で読む形式）へ変換する。変換を忘れると、一括登録した
    別名が入力式の判定で1本の文字列としてしか一致しなくなる（横展開チェックで検出）。
    """
    aliases = [part.strip() for part in raw.split("|") if part.strip()]
    return "\n".join(aliases) if aliases else None


def parse_bulk_import(session: Session, deck: VocabDeck, text: str) -> VocabImportPreview:
    """貼り付けテキストを解析し、取り込み前のプレビューを返す。

    列は「用語・意味・別名（任意、`|`区切り）・補足（任意）」。タブ区切り、タブが無い行は
    カンマ区切りとして扱う（利用者プロンプトの明示指示）。`csv`モジュールのみを使い、
    正規表現の連鎖は行わない（ReDoS対策）。別名は入力時の`|`区切りから保存形式（改行区切り）
    へ`_parse_import_aliases`で変換する（横展開チェックで検出：変換を忘れると入力式判定の
    別名一致が機能しなくなる）。
    """
    term_max = setting_reader.get_int(session, VOCAB_TERM_MAX_CHARS)
    meaning_max = setting_reader.get_int(session, VOCAB_MEANING_MAX_CHARS)
    import_max_rows = setting_reader.get_int(session, VOCAB_IMPORT_MAX_ROWS)

    raw_lines = [line for line in text.splitlines() if line.strip()]
    if len(raw_lines) > import_max_rows:
        raise VocabImportTooManyRowsError(len(raw_lines), import_max_rows)

    rows: list[VocabImportRow] = []
    errors: list[VocabImportError] = []
    for line_number, raw_line in enumerate(raw_lines, start=1):
        fields = _split_import_line(raw_line)
        term = fields[0].strip() if len(fields) > 0 else ""
        meaning = fields[1].strip() if len(fields) > 1 else ""
        aliases = _parse_import_aliases(fields[2]) if len(fields) > 2 else None
        note = fields[3].strip() if len(fields) > 3 and fields[3].strip() else None
        if not term:
            errors.append(VocabImportError(line_number, "term is empty"))
            continue
        if not meaning:
            errors.append(VocabImportError(line_number, "meaning is empty"))
            continue
        if len(term) > term_max:
            errors.append(VocabImportError(line_number, f"term exceeds {term_max} characters"))
            continue
        if len(meaning) > meaning_max:
            errors.append(
                VocabImportError(line_number, f"meaning exceeds {meaning_max} characters")
            )
            continue
        rows.append(VocabImportRow(line_number, term, meaning, aliases, note))

    existing_keys = {
        normalize_for_vocab_match(card.term) for card in list_cards_for_deck(session, deck.id)
    }
    seen_keys: set[str] = set()
    duplicate_line_numbers: list[int] = []
    deduped_rows: list[VocabImportRow] = []
    for row in rows:
        key = normalize_for_vocab_match(row.term)
        if key in existing_keys or key in seen_keys:
            duplicate_line_numbers.append(row.line_number)
            continue
        seen_keys.add(key)
        deduped_rows.append(row)

    return VocabImportPreview(deduped_rows, errors, duplicate_line_numbers)


def confirm_bulk_import(session: Session, deck: VocabDeck, rows: list[VocabImportRow]) -> int:
    """プレビューで確定した行をカードとして登録する。重複・エラー行は呼び出し側
    （`parse_bulk_import`の結果）で既に除かれている前提だが、`parse_bulk_import`を経由せず
    このAPIへ直接送られた行も想定し、行数・文字数はここでも再検証する（信頼境界を
    クライアントで止めない。injection-reviewerレビューで検出、2026-11-15）。
    """
    import_max_rows = setting_reader.get_int(session, VOCAB_IMPORT_MAX_ROWS)
    if len(rows) > import_max_rows:
        raise VocabImportTooManyRowsError(len(rows), import_max_rows)
    for row in rows:
        _validate_card_fields(session, row.term, row.meaning)
    existing_cards = list_cards_for_deck(session, deck.id)
    _ensure_deck_card_capacity(
        session, deck.id, current_count=len(existing_cards), adding=len(rows)
    )
    next_order = max((c.display_order for c in existing_cards), default=-1) + 1
    for offset, row in enumerate(rows):
        session.add(
            VocabCard(
                deck_id=deck.id,
                term=row.term,
                meaning=row.meaning,
                aliases=row.aliases,
                note=row.note,
                is_checked=False,
                display_order=next_order + offset,
            )
        )
    session.flush()
    return len(rows)


def export_deck(session: Session, deck: VocabDeck) -> str:
    """単語帳をタブ区切りテキストへ書き出す（用語・意味・別名・補足の4列）。"""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\n")
    for card in list_cards_for_deck(session, deck.id):
        writer.writerow([card.term, card.meaning, card.aliases or "", card.note or ""])
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# 出題選択・判定
# ---------------------------------------------------------------------------


def is_weak_card(stats: VocabCardStats, weak_accuracy_percent: float) -> bool:
    return stats.accuracy_percent is not None and stats.accuracy_percent < weak_accuracy_percent


def filter_cards(
    cards: list[VocabCard],
    stats_by_card: dict[int, VocabCardStats],
    *,
    filter_key: str,
    weak_accuracy_percent: float,
    mastered_card_ids: frozenset[int] = frozenset(),
) -> list[VocabCard]:
    """絞り込み（全件／チェック付きのみ／一度でも間違えた／連続して間違えている／苦手／
    未解答／未習得）を適用する。`mastered_card_ids`は`UNMASTERED`（開発Todo_単語帳_v1.0
    要件E E-U6）のときのみ使う（`vocab_service.compute_mastered_card_ids`の結果）。"""
    if filter_key == "ALL":
        return cards
    if filter_key == "CHECKED":
        return [card for card in cards if card.is_checked]
    if filter_key == "EVER_WRONG":
        return [card for card in cards if stats_by_card[card.id].incorrect_count > 0]
    if filter_key == "CONSECUTIVE_WRONG":
        return [card for card in cards if stats_by_card[card.id].consecutive_incorrect >= 1]
    if filter_key == "WEAK":
        return [
            card for card in cards if is_weak_card(stats_by_card[card.id], weak_accuracy_percent)
        ]
    if filter_key == "UNMASTERED":
        return [card for card in cards if card.id not in mastered_card_ids]
    if filter_key == "UNANSWERED":
        return [
            card
            for card in cards
            if stats_by_card[card.id].correct_count + stats_by_card[card.id].incorrect_count == 0
        ]
    raise ValidationError(f"Unknown filter: {filter_key}")


def sort_cards(
    cards: list[VocabCard], stats_by_card: dict[int, VocabCardStats], *, sort_key: str
) -> list[VocabCard]:
    """並び順（登録順／正答率の低い順／誤答数の多い順／連続誤答数の多い順）を適用する。"""
    if sort_key == "REGISTERED":
        return sorted(cards, key=lambda card: (card.display_order, card.id))
    if sort_key == "ACCURACY_ASC":
        # 未解答（正答率なし）は末尾へ（苦手かどうか判定できないため、低い順の先頭には置かない）。
        return sorted(
            cards,
            key=lambda card: (
                stats_by_card[card.id].accuracy_percent is None,
                stats_by_card[card.id].accuracy_percent or 0,
            ),
        )
    if sort_key == "INCORRECT_COUNT_DESC":
        return sorted(cards, key=lambda card: -stats_by_card[card.id].incorrect_count)
    if sort_key == "CONSECUTIVE_WRONG_DESC":
        return sorted(cards, key=lambda card: -stats_by_card[card.id].consecutive_incorrect)
    raise ValidationError(f"Unknown sort: {sort_key}")


def select_session_cards(
    cards: list[VocabCard],
    stats_by_card: dict[int, VocabCardStats],
    *,
    order_key: str,
    question_count: int,
    rng: random.Random | None = None,
) -> list[VocabCard]:
    """出題セッション用の並び順（ランダム／苦手順／登録順）を適用し、問題数で切り詰める。"""
    rng = rng or random.Random()
    if order_key == "RANDOM":
        shuffled = list(cards)
        rng.shuffle(shuffled)
        ordered = shuffled
    elif order_key == "WEAK_ORDER":
        ordered = sorted(
            cards,
            key=lambda card: (
                -stats_by_card[card.id].consecutive_incorrect,
                stats_by_card[card.id].accuracy_percent
                if stats_by_card[card.id].accuracy_percent is not None
                else 100.0,
            ),
        )
    elif order_key == "REGISTERED":
        ordered = sorted(cards, key=lambda card: (card.display_order, card.id))
    else:
        raise ValidationError(f"Unknown order: {order_key}")
    return ordered[:question_count]


def judge_typed_answer(card: VocabCard, answer: str) -> bool:
    """入力式（意味→用語）の解答を判定する。用語か別名のいずれかと一致したら正解。"""
    normalized_answer = normalize_for_vocab_match(answer)
    if normalized_answer == normalize_for_vocab_match(card.term):
        return True
    for alias in (card.aliases or "").splitlines():
        if alias.strip() and normalized_answer == normalize_for_vocab_match(alias):
            return True
    return False


def build_choice_option_ids(
    deck_cards: list[VocabCard],
    target_card: VocabCard,
    *,
    field: str,
    rng: random.Random | None = None,
) -> list[int] | None:
    """4択の選択肢カードID（出題カード自身を含む、シャッフル済み）を組み立てる。
    `field`は"term"または"meaning"（表示する欄）。

    同じ単語帳の他カードから、正規化後に出題カードと重複しない3件を選ぶ。足りない場合は
    Noneを返す（呼び出し側はこのカードを出題から外し、除外件数を数える）。
    """
    rng = rng or random.Random()
    target_key = normalize_for_vocab_match(getattr(target_card, field))
    candidates = [
        card
        for card in deck_cards
        if card.id != target_card.id
        and normalize_for_vocab_match(getattr(card, field)) != target_key
    ]
    # 候補内で正規化後に重複する値は1件に絞る（同じ選択肢が2回出るのを防ぐ）。
    unique_candidates: dict[str, VocabCard] = {}
    for card in candidates:
        key = normalize_for_vocab_match(getattr(card, field))
        unique_candidates.setdefault(key, card)
    if len(unique_candidates) < 3:
        return None
    distractors = rng.sample(list(unique_candidates.values()), 3)
    option_cards = [*distractors, target_card]
    rng.shuffle(option_cards)
    return [card.id for card in option_cards]


# ---------------------------------------------------------------------------
# AI連携: 参考用語の組み立て（開発Todo_単語帳_v1.0 要件B B-U6）
# ---------------------------------------------------------------------------

#: 参考用語が無い場合の表示（資格試験以外の目標、対象カードが無い場合）。
NO_GLOSSARY_REFERENCE_TEXT = "（なし）"


def ai_eligible_deck_conditions() -> tuple:
    """AI用途（今日の復習の生成・出題、参考用語の注入）の対象となる単語帳の絞り込み条件
    （`use_in_ai=True`・目標ACTIVE・EXAM限定、B-U1・B-D13）。`VocabDeck`・`Goal`への
    JOINを前提にした`.where(*ai_eligible_deck_conditions())`として使う。

    `quiz_service._due_vocab_questions`（出題クエリ）と
    `vocab_quiz_generation_service._candidate_cards_query`（生成対象クエリ）の両方が
    同一の業務ルールを別々に実装して重複していたため共通化した（dry-reviewerレビューで
    検出、2026-11-17）。
    """
    return (
        VocabDeck.use_in_ai.is_(True),
        Goal.status == GoalStatus.ACTIVE,
        Goal.category == GoalCategory.EXAM,
    )


def split_aliases(card: VocabCard) -> list[str]:
    """別名欄（改行区切り）を、空行を除いたリストで返す（前後の空白を除去済み）。

    カードの表示・AI送信用フォーマット（`build_vocab_match_keys`・`_format_glossary_label`・
    `vocab_quiz_generation_service._format_card_line`）で共通して使う別名の分解処理
    （dry-reviewerレビューで3箇所の重複を検出、2026-11-17）。
    """
    return [alias.strip() for alias in (card.aliases or "").splitlines() if alias.strip()]


def build_vocab_match_keys(card: VocabCard) -> list[str]:
    """カードの用語・別名を正規化したキー一覧（`normalize_for_vocab_match`適用後）。

    参考用語の組み立て（`build_glossary_reference`）・単語帳由来クイズの根拠検証
    （`vocab_quiz_generation_service`、出典カードの用語または別名が問題文・正解の
    選択肢に含まれるかの判定）の両方で使う共通処理（CLAUDE.md DRYの原則）。
    """
    keys = [normalize_for_vocab_match(card.term)]
    keys.extend(normalize_for_vocab_match(alias) for alias in split_aliases(card))
    return [key for key in keys if key]


def flatten_for_single_line(text: str) -> str:
    """AIへ渡す1行形式へ組み込む前に、改行等の行区切り文字を半角空白へ置換する。

    用語・意味に改行が含まれていると、「#カードID 用語／意味」のような1行形式の
    プロンプト構造を崩し、存在しないカードの行を偽装できてしまう（injection-reviewer
    レビューで検出、2026-11-17）。データとしての改行の保存自体は妨げない（表示・入力検証
    では拒否しない）。Unicode制御文字（Cc）・行区切り（Zl）・段落区切り（Zp）が対象。
    """
    return "".join(" " if unicodedata.category(ch) in ("Cc", "Zl", "Zp") else ch for ch in text)


def forbidden_term_search_text(card: VocabCard) -> str:
    """禁止語照合の対象文字列（用語・意味・別名を連結、要件B・Cで共有）。

    `build_glossary_reference`・`build_glossary_overview`（本モジュール）・
    `vocab_quiz_generation_service._generate_for_cards`の3箇所が同じ組み立てを
    必要とするため、ここへ共通化する（自己レビューで検出した重複、§5.3 #1と同種。
    モジュール外から呼ぶため公開関数とする、`flatten_for_single_line`等と同じ扱い）。
    """
    return f"{card.term} {card.meaning} {card.aliases or ''}"


def _format_glossary_label(card: VocabCard) -> str:
    """「・用語（別名1、別名2）: 意味」の形式（別名が無ければ括弧を省略、B-D11）。

    埋め込み先の区切り（`<<<GLOSSARY-{{nonce}}>>>`）を利用者入力から偽造できないよう、
    山括弧を全角化する（`DELIMITER_REPLACEMENTS`、呼び出し元に依存しないデフォルトで
    安全な実装にする。injection-reviewerレビューで検出、2026-11-17）。改行等は1行形式を
    崩すため空白へ変換する（`flatten_for_single_line`）。`build_glossary_reference`
    （要件B）・`build_glossary_overview`（要件C）の両方が同じ書式を使うため共有する
    （自己レビューで検出した重複）。
    """
    term = flatten_for_single_line(card.term).translate(question_safety.DELIMITER_REPLACEMENTS)
    meaning = flatten_for_single_line(card.meaning).translate(
        question_safety.DELIMITER_REPLACEMENTS
    )
    aliases = [
        flatten_for_single_line(alias).translate(question_safety.DELIMITER_REPLACEMENTS)
        for alias in split_aliases(card)
    ]
    if aliases:
        return f"・{term}（{'、'.join(aliases)}）: {meaning}"
    return f"・{term}: {meaning}"


def eligible_glossary_cards(session: Session, goal: Goal) -> list[VocabCard]:
    """参考用語（`build_glossary_reference`）の対象カード一覧を1回のクエリで取得する。

    テーマ由来クイズ生成（`quiz_generation_service.generate_for_theme`）はチャンクごとに
    `build_glossary_reference`を呼ぶため、呼び出し元がこの関数をループの外で1回だけ呼び、
    結果を`build_glossary_reference`の`cards`引数へ渡すことで、チャンク数だけデッキ・
    カード一覧を再取得する重複クエリを避けられる（performance-reviewerレビューで検出、
    2026-11-17）。
    """
    if goal.category != GoalCategory.EXAM:
        return []
    deck_ids = [deck.id for deck in list_decks_for_goal(session, goal.id) if deck.use_in_ai]
    if not deck_ids:
        return []
    return list(
        session.scalars(
            select(VocabCard)
            .where(VocabCard.deck_id.in_(deck_ids))
            .order_by(VocabCard.deck_id, VocabCard.display_order, VocabCard.id)
        ).all()
    )


def build_glossary_reference(
    session: Session,
    goal: Goal,
    texts: list[str],
    *,
    max_chars: int,
    cards: list[VocabCard] | None = None,
    forbidden_keys: list[str] | None = None,
) -> str:
    """参考用語（学習者が単語帳に登録した意味）を、与えられた文章群に用語または別名が
    含まれるカードから組み立てる（B-U6、テーマ由来クイズ生成の{{glossary_reference}}）。

    資格試験以外の目標・対象カードが無い場合は`NO_GLOSSARY_REFERENCE_TEXT`（「（なし）」）
    を返す。禁止語を含むカードは除外する（vocab_quiz_generation_serviceと共通の方針）。
    マッチ対象の文章群（`texts`）・文字数予算（`max_chars`）を引数化し、要件C（日次
    フィードバック・目標相談への注入）でも再利用できる共通関数とする（利用者プロンプトの
    明示指示）。カードの並び順（デッキ表示順→カード表示順）は固定とし、要件Cで異なる
    並び順が必要になった場合はそのとき拡張する（B-D14、スコープの最小化）。

    `cards`・`forbidden_keys`は、呼び出し元がチャンクごとに繰り返し呼ぶ場合に、
    `eligible_glossary_cards`・`question_safety.list_enabled_forbidden_term_keys`の結果を
    ループの外で1回だけ取得して渡すための引数（省略時はこの呼び出しの中で取得する、
    performance-reviewerレビューで検出、2026-11-17）。
    """
    if cards is None:
        cards = eligible_glossary_cards(session, goal)
    if not cards:
        return NO_GLOSSARY_REFERENCE_TEXT
    if forbidden_keys is None:
        forbidden_keys = question_safety.list_enabled_forbidden_term_keys(session)
    normalized_texts = [normalize_for_vocab_match(text) for text in texts]
    lines: list[str] = []
    total_chars = 0
    for card in cards:
        if question_safety.contains_any_forbidden_term(
            forbidden_term_search_text(card), forbidden_keys
        ):
            continue
        if not any(
            key in text for key in build_vocab_match_keys(card) for text in normalized_texts
        ):
            continue
        line = _format_glossary_label(card)
        if lines and total_chars + len(line) > max_chars:
            break
        lines.append(line)
        total_chars += len(line)
    return "\n".join(lines) if lines else NO_GLOSSARY_REFERENCE_TEXT


# ---------------------------------------------------------------------------
# AI連携: 日次フィードバック・目標相談への参考用語の組み立て（開発Todo_単語帳_v1.0 要件C）
# ---------------------------------------------------------------------------

#: 参考用語（build_glossary_overview）が無い場合の表示。build_glossary_reference（要件B）の
#: NO_GLOSSARY_REFERENCE_TEXT（「（なし）」）とは文言・用途が異なるため別の定数とする
#: （利用者が直接読む文章のため分かりやすい文言を使う、C-D9）。
NO_GLOSSARY_OVERVIEW_TEXT = "（登録された用語はありません）"


def _glossary_overview_tier(
    card: VocabCard, stats: VocabCardStats, weak_accuracy_percent: float
) -> int:
    """優先順（チェック付き→連続誤答数の多い順→正答率の低い順→未解答→その他）の
    5段のどこに属するかを返す（0が最優先、C-D2）。

    各段は排他的なバケットとする（1つの単純な数値キーで「正答率の低い順」と「その他」を
    同時に表現しようとすると、正答率の高い「その他」が常に未解答より先に来てしまい
    `未解答→その他`の順序を表現できないため、段ごとに分けるのが最も素直な実装）。
    「正答率の低い順」は既存の「苦手」判定（`is_weak_card`・`vocab.weak_accuracy_percent`、
    単語帳一覧の絞り込みと同じ基準）に合わせ、連続誤答が無い解答済みカードのうち
    苦手なものに限定する（CLAUDE.md DRYの原則）。
    """
    if card.is_checked:
        return 0
    if stats.consecutive_incorrect >= 1:
        return 1
    if is_weak_card(stats, weak_accuracy_percent):
        return 2
    if stats.correct_count + stats.incorrect_count == 0:
        return 3
    return 4  # その他（解答済みで苦手でも連続誤答もない）


def _glossary_overview_sort_key(
    card: VocabCard, stats_by_card: dict[int, VocabCardStats], weak_accuracy_percent: float
) -> tuple[int, float, int, int]:
    """段の中の順序：段1（連続誤答）は多い順、段2（苦手）は正答率の低い順。
    他の段は登録順（`display_order`→`id`）で安定させる（過剰な一般化を避ける、C-D2）。
    """
    stats = stats_by_card[card.id]
    tier = _glossary_overview_tier(card, stats, weak_accuracy_percent)
    secondary = 0.0
    if tier == 1:
        secondary = -stats.consecutive_incorrect
    elif tier == 2:
        secondary = stats.accuracy_percent or 0.0
    return (tier, secondary, card.display_order, card.id)


def _format_overview_line(
    card: VocabCard, stats: VocabCardStats, weak_accuracy_percent: float
) -> str:
    """「・用語（別名1、別名2）: 意味［正答率 60%（3/5）・連続誤答 2回・要復習］」の形式
    （未解答のカードは成績注記自体を省略する）。「・用語（別名）: 意味」部分は
    `_format_glossary_label`（区切りの全角化・改行潰しを含む、B-D11・C-D5）を共有し、
    成績注記のみを追加する。
    """
    label = _format_glossary_label(card)

    total_answers = stats.correct_count + stats.incorrect_count
    if total_answers == 0:
        return label

    notes = [f"正答率 {stats.accuracy_percent:.0f}%（{stats.correct_count}/{total_answers}）"]
    if stats.consecutive_incorrect >= 1:
        notes.append(f"連続誤答 {stats.consecutive_incorrect}回")
    if is_weak_card(stats, weak_accuracy_percent):
        notes.append("要復習")
    return f"{label}［{'・'.join(notes)}］"


def build_glossary_overview(session: Session, goal: Goal, *, max_chars: int) -> str:
    """日次フィードバック・目標相談への参考用語（`{{glossary}}`）を組み立てる
    （開発Todo_単語帳_v1.0 要件C）。

    `build_glossary_reference`（要件B、報告・テーマ本文に実際に用語が出てくるカードだけに
    絞る「マッチ型」）とは選定方法が異なり、その目標の`use_in_ai=True`の単語帳のカードを
    全て対象に、成績に基づく優先順（`_glossary_overview_sort_key`、C-D2）で並べる。
    資格試験以外の目標・対象カードが無い場合は`NO_GLOSSARY_OVERVIEW_TEXT`を返す。
    禁止語を含むカードは除外する（既存B実装と同じ方針）。`max_chars`を超えない範囲で、
    行の単位で打ち切る（最低1行は含める、`build_glossary_reference`と同じ打ち切り方式）。
    """
    cards = eligible_glossary_cards(session, goal)
    if not cards:
        return NO_GLOSSARY_OVERVIEW_TEXT
    forbidden_keys = question_safety.list_enabled_forbidden_term_keys(session)
    cards = [
        card
        for card in cards
        if not question_safety.contains_any_forbidden_term(
            forbidden_term_search_text(card), forbidden_keys
        )
    ]
    if not cards:
        return NO_GLOSSARY_OVERVIEW_TEXT

    stats_by_card = compute_card_stats(session, [card.id for card in cards])
    weak_accuracy_percent = setting_reader.get_int(session, VOCAB_WEAK_ACCURACY_PERCENT)
    ordered = sorted(
        cards,
        key=lambda card: _glossary_overview_sort_key(card, stats_by_card, weak_accuracy_percent),
    )

    lines: list[str] = []
    total_chars = 0
    for card in ordered:
        line = _format_overview_line(card, stats_by_card[card.id], weak_accuracy_percent)
        if lines and total_chars + len(line) > max_chars:
            break
        lines.append(line)
        total_chars += len(line)
    return "\n".join(lines) if lines else NO_GLOSSARY_OVERVIEW_TEXT
