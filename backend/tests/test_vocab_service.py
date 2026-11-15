"""単語帳サービス層のテスト（開発Todo_単語帳_v1.0 要件A、AI非依存）。"""

import datetime as dt
import random

import pytest
from sqlalchemy import select

from app.constants.app_setting_keys import (
    VOCAB_DECK_MAX_CARDS,
    VOCAB_IMPORT_MAX_ROWS,
    VOCAB_MEANING_MAX_CHARS,
    VOCAB_TERM_MAX_CHARS,
)
from app.constants.enums import VocabQuizMode
from app.models.vocab import VocabAnswerLog, VocabCard, VocabDeck
from app.services import vocab_service
from app.services.exceptions import (
    NotFoundError,
    ValidationError,
    VocabDeckCardLimitExceededError,
    VocabDeckGoalCategoryError,
    VocabImportTooManyRowsError,
)
from tests.diary_helpers import make_exam_goal
from tests.vocab_helpers import (
    make_answer_log,
    make_card,
    make_deck,
    make_reading_goal,
    set_setting,
)

TODAY = dt.datetime(2026, 3, 20, 9, 0, 0)


# ---------------------------------------------------------------------------
# 正規化
# ---------------------------------------------------------------------------


def test_normalize_for_vocab_match_converts_katakana_to_hiragana():
    assert vocab_service.normalize_for_vocab_match("アイウエオ") == "あいうえお"


def test_normalize_for_vocab_match_normalizes_width_case_and_whitespace():
    assert vocab_service.normalize_for_vocab_match(
        " Ｔｅｒｍ 　"
    ) == vocab_service.normalize_for_vocab_match("term")


def test_normalize_for_vocab_match_leaves_hiragana_and_kanji_untouched():
    assert vocab_service.normalize_for_vocab_match("漢字ひらがな") == "漢字ひらがな"


# ---------------------------------------------------------------------------
# デッキCRUD
# ---------------------------------------------------------------------------


def test_create_deck_succeeds_for_exam_goal(seeded_session):
    goal = make_exam_goal(seeded_session)

    deck = vocab_service.create_deck(seeded_session, goal, name="単語帳1", description="説明")

    assert deck.goal_id == goal.id
    assert deck.use_in_ai is True
    assert deck.display_order == 0


def test_create_deck_rejects_non_exam_goal(seeded_session):
    goal = make_reading_goal(seeded_session)

    with pytest.raises(VocabDeckGoalCategoryError):
        vocab_service.create_deck(seeded_session, goal, name="単語帳1", description=None)


def test_create_deck_assigns_incrementing_display_order(seeded_session):
    goal = make_exam_goal(seeded_session)
    vocab_service.create_deck(seeded_session, goal, name="A", description=None)
    second = vocab_service.create_deck(seeded_session, goal, name="B", description=None)

    assert second.display_order == 1


def test_create_deck_display_order_does_not_collide_after_middle_deletion(seeded_session):
    goal = make_exam_goal(seeded_session)
    first = vocab_service.create_deck(seeded_session, goal, name="A", description=None)
    middle = vocab_service.create_deck(seeded_session, goal, name="B", description=None)
    last = vocab_service.create_deck(seeded_session, goal, name="C", description=None)
    vocab_service.delete_deck(seeded_session, middle)

    new_deck = vocab_service.create_deck(seeded_session, goal, name="D", description=None)

    assert new_deck.display_order == 3
    assert new_deck.display_order not in (first.display_order, last.display_order)


def test_get_deck_returns_existing_deck(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)

    assert vocab_service.get_deck(seeded_session, deck.id).id == deck.id


def test_get_deck_raises_not_found_for_unknown_id(seeded_session):
    with pytest.raises(NotFoundError):
        vocab_service.get_deck(seeded_session, 999999)


def test_list_decks_for_goal_orders_by_display_order(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck_b = make_deck(seeded_session, goal, "B")
    deck_b.display_order = 0
    deck_a = make_deck(seeded_session, goal, "A")
    deck_a.display_order = 1
    seeded_session.flush()

    result = vocab_service.list_decks_for_goal(seeded_session, goal.id)

    assert [d.id for d in result] == [deck_b.id, deck_a.id]


def test_update_deck_updates_only_given_fields(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal, "元の名前")

    vocab_service.update_deck(seeded_session, deck, use_in_ai=False)

    assert deck.name == "元の名前"
    assert deck.use_in_ai is False


def test_update_deck_can_update_name_and_description(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal, "元の名前")

    vocab_service.update_deck(seeded_session, deck, name="新しい名前", description="新しい説明")

    assert deck.name == "新しい名前"
    assert deck.description == "新しい説明"


def test_delete_deck_cascades_to_cards_and_answer_logs(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck)
    vocab_service.record_answer(seeded_session, card, VocabQuizMode.FLASH_TERM_TO_MEANING, True)
    deck_id, card_id = deck.id, card.id

    vocab_service.delete_deck(seeded_session, deck)
    seeded_session.commit()

    assert seeded_session.get(VocabDeck, deck_id) is None
    assert seeded_session.get(VocabCard, card_id) is None
    assert (
        seeded_session.scalar(select(VocabAnswerLog).where(VocabAnswerLog.card_id == card_id))
        is None
    )


def test_reorder_decks_applies_given_order(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck_a = make_deck(seeded_session, goal, "A")
    deck_b = make_deck(seeded_session, goal, "B")

    vocab_service.reorder_decks(seeded_session, goal, [deck_b.id, deck_a.id])

    assert deck_b.display_order == 0
    assert deck_a.display_order == 1


def test_reorder_decks_rejects_mismatched_ids(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck_a = make_deck(seeded_session, goal, "A")

    with pytest.raises(ValidationError):
        vocab_service.reorder_decks(seeded_session, goal, [deck_a.id, 999999])


# ---------------------------------------------------------------------------
# カードCRUD
# ---------------------------------------------------------------------------


def test_get_card_returns_existing_card(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck)

    assert vocab_service.get_card(seeded_session, card.id).id == card.id


def test_get_card_raises_not_found_for_unknown_id(seeded_session):
    with pytest.raises(NotFoundError):
        vocab_service.get_card(seeded_session, 999999)


def test_create_card_succeeds(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)

    card = vocab_service.create_card(
        seeded_session, deck, term="用語", meaning="意味", aliases="別名", note="補足"
    )

    assert card.deck_id == deck.id
    assert card.is_checked is False


def test_create_card_display_order_does_not_collide_after_middle_deletion(seeded_session):
    """中間のカードを削除した後に追加したカードが、既存カードの表示順と衝突しないこと
    （`len(既存件数)`による採番は削除後にギャップへ衝突しうるため`max+1`方式にした、
    dry-reviewerレビューで検出・修正、2026-11-15）。"""
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    first = vocab_service.create_card(seeded_session, deck, term="1", meaning="一")
    middle = vocab_service.create_card(seeded_session, deck, term="2", meaning="二")
    last = vocab_service.create_card(seeded_session, deck, term="3", meaning="三")
    assert [first.display_order, middle.display_order, last.display_order] == [0, 1, 2]
    vocab_service.delete_card(seeded_session, middle)

    new_card = vocab_service.create_card(seeded_session, deck, term="4", meaning="四")

    assert new_card.display_order == 3
    assert new_card.display_order not in (first.display_order, last.display_order)


def test_create_card_rejects_empty_term(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)

    with pytest.raises(ValidationError):
        vocab_service.create_card(seeded_session, deck, term="  ", meaning="意味")


def test_create_card_rejects_empty_meaning(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)

    with pytest.raises(ValidationError):
        vocab_service.create_card(seeded_session, deck, term="用語", meaning=" ")


def test_create_card_rejects_term_over_max_chars(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    set_setting(seeded_session, VOCAB_TERM_MAX_CHARS, "5")

    with pytest.raises(ValidationError):
        vocab_service.create_card(seeded_session, deck, term="123456", meaning="意味")


def test_create_card_rejects_meaning_over_max_chars(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    set_setting(seeded_session, VOCAB_MEANING_MAX_CHARS, "5")

    with pytest.raises(ValidationError):
        vocab_service.create_card(seeded_session, deck, term="用語", meaning="123456")


def test_create_card_rejects_when_deck_is_full(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    set_setting(seeded_session, VOCAB_DECK_MAX_CARDS, "1")
    vocab_service.create_card(seeded_session, deck, term="用語1", meaning="意味1")

    with pytest.raises(VocabDeckCardLimitExceededError):
        vocab_service.create_card(seeded_session, deck, term="用語2", meaning="意味2")


def test_create_card_succeeds_at_exactly_the_deck_capacity(seeded_session):
    """上限と同数ならまだ拒否されない境界（`current_count + adding > max_cards`の
    `>`/`>=`取り違いを検知する、test-coverage-reviewerレビューで検出）。"""
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    set_setting(seeded_session, VOCAB_DECK_MAX_CARDS, "2")
    vocab_service.create_card(seeded_session, deck, term="用語1", meaning="意味1")

    card = vocab_service.create_card(seeded_session, deck, term="用語2", meaning="意味2")

    assert card.id is not None


def test_update_card_partial_update_keeps_other_fields(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck, term="元の用語", meaning="元の意味")

    vocab_service.update_card(seeded_session, card, meaning="新しい意味")

    assert card.term == "元の用語"
    assert card.meaning == "新しい意味"


def test_update_card_can_update_term_aliases_and_note(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck, term="元", meaning="意味", aliases=None, note=None)

    vocab_service.update_card(seeded_session, card, term="新しい用語", aliases="別名", note="補足")

    assert card.term == "新しい用語"
    assert card.aliases == "別名"
    assert card.note == "補足"


def test_update_card_validates_existing_term_when_only_meaning_is_given(seeded_session):
    """termを渡さない更新でも、既存のtermが現在の上限を超えていれば拒否する
    （上限を後から下げた場合に、別フィールドの更新だけで古い超過データを素通りさせない）。
    """
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck, term="123456", meaning="意味")
    set_setting(seeded_session, VOCAB_TERM_MAX_CHARS, "3")

    with pytest.raises(ValidationError):
        vocab_service.update_card(seeded_session, card, meaning="新しい意味")


def test_set_card_checked_toggles_flag(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck)

    vocab_service.set_card_checked(seeded_session, card, True)

    assert card.is_checked is True


def test_delete_card_removes_it(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck)
    card_id = card.id

    vocab_service.delete_card(seeded_session, card)

    assert seeded_session.get(VocabCard, card_id) is None


# ---------------------------------------------------------------------------
# 成績集計
# ---------------------------------------------------------------------------


def test_compute_card_stats_with_empty_card_ids_returns_empty_dict(seeded_session):
    assert vocab_service.compute_card_stats(seeded_session, []) == {}


def test_compute_card_stats_for_unanswered_card_has_none_accuracy(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck)

    stats = vocab_service.compute_card_stats(seeded_session, [card.id])[card.id]

    assert stats.correct_count == 0
    assert stats.incorrect_count == 0
    assert stats.accuracy_percent is None
    assert stats.consecutive_incorrect == 0
    assert stats.last_answered_at is None


def test_compute_card_stats_aggregates_correct_and_incorrect(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck)
    vocab_service.record_answer(seeded_session, card, VocabQuizMode.FLASH_TERM_TO_MEANING, True)
    vocab_service.record_answer(seeded_session, card, VocabQuizMode.FLASH_TERM_TO_MEANING, False)
    vocab_service.record_answer(seeded_session, card, VocabQuizMode.FLASH_TERM_TO_MEANING, False)

    stats = vocab_service.compute_card_stats(seeded_session, [card.id])[card.id]

    assert stats.correct_count == 1
    assert stats.incorrect_count == 2
    assert stats.accuracy_percent == pytest.approx(100 / 3)
    assert stats.consecutive_incorrect == 2
    assert stats.last_answered_at is not None


def test_compute_card_stats_consecutive_incorrect_resets_on_recent_correct(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck)
    vocab_service.record_answer(seeded_session, card, VocabQuizMode.FLASH_TERM_TO_MEANING, False)
    vocab_service.record_answer(seeded_session, card, VocabQuizMode.FLASH_TERM_TO_MEANING, False)
    vocab_service.record_answer(seeded_session, card, VocabQuizMode.FLASH_TERM_TO_MEANING, True)

    stats = vocab_service.compute_card_stats(seeded_session, [card.id])[card.id]

    assert stats.consecutive_incorrect == 0


def test_compute_card_stats_handles_multiple_cards_in_one_call(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card1 = make_card(seeded_session, deck, term="1")
    card2 = make_card(seeded_session, deck, term="2")
    vocab_service.record_answer(seeded_session, card1, VocabQuizMode.FLASH_TERM_TO_MEANING, True)

    stats = vocab_service.compute_card_stats(seeded_session, [card1.id, card2.id])

    assert stats[card1.id].correct_count == 1
    assert stats[card2.id].correct_count == 0


def test_count_cards_by_deck_with_empty_list_returns_empty_dict(seeded_session):
    assert vocab_service.count_cards_by_deck(seeded_session, []) == {}


def test_count_cards_by_deck_separates_counts_per_deck(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck_a = make_deck(seeded_session, goal, "A")
    deck_b = make_deck(seeded_session, goal, "B")
    deck_c = make_deck(seeded_session, goal, "C")
    make_card(seeded_session, deck_a, term="1")
    make_card(seeded_session, deck_a, term="2")
    make_card(seeded_session, deck_b, term="3")

    counts = vocab_service.count_cards_by_deck(seeded_session, [deck_a.id, deck_b.id, deck_c.id])

    assert counts == {deck_a.id: 2, deck_b.id: 1}


def test_compute_card_stats_breaks_answered_at_ties_by_id(seeded_session):
    """同一の`answered_at`（マイクロ秒精度の衝突、CODING_RULES.md「タイムスタンプでの
    並び替え」）でも、挿入順（id昇順）で連続誤答数が正しく算出されること。"""
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck)
    same_time = TODAY
    make_answer_log(seeded_session, card, is_correct=True, answered_at=same_time)
    make_answer_log(seeded_session, card, is_correct=False, answered_at=same_time)
    make_answer_log(seeded_session, card, is_correct=False, answered_at=same_time)

    stats = vocab_service.compute_card_stats(seeded_session, [card.id])[card.id]

    assert stats.consecutive_incorrect == 2
    assert stats.correct_count == 1
    assert stats.incorrect_count == 2


def test_record_answer_persists_mode_and_correctness(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck)

    vocab_service.record_answer(seeded_session, card, VocabQuizMode.TYPED_MEANING_TO_TERM, True)

    log = seeded_session.scalar(select(VocabAnswerLog).where(VocabAnswerLog.card_id == card.id))
    assert log.mode == VocabQuizMode.TYPED_MEANING_TO_TERM
    assert log.is_correct is True


# ---------------------------------------------------------------------------
# 一括登録・エクスポート
# ---------------------------------------------------------------------------


def test_parse_bulk_import_parses_tab_separated_rows(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)

    preview = vocab_service.parse_bulk_import(
        seeded_session, deck, "用語1\t意味1\t別名1\t補足1\n用語2\t意味2"
    )

    assert [row.term for row in preview.rows] == ["用語1", "用語2"]
    assert preview.rows[0].aliases == "別名1"
    assert preview.rows[1].aliases is None
    assert preview.errors == []
    assert preview.duplicate_line_numbers == []


def test_parse_bulk_import_falls_back_to_comma_when_no_tab(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)

    preview = vocab_service.parse_bulk_import(seeded_session, deck, "用語1,意味1")

    assert preview.rows[0].term == "用語1"
    assert preview.rows[0].meaning == "意味1"


def test_parse_bulk_import_reports_empty_term_error(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)

    preview = vocab_service.parse_bulk_import(seeded_session, deck, "\t意味1")

    assert preview.rows == []
    assert preview.errors[0].reason == "term is empty"


def test_parse_bulk_import_reports_empty_meaning_error(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)

    preview = vocab_service.parse_bulk_import(seeded_session, deck, "用語1\t")

    assert preview.errors[0].reason == "meaning is empty"


def test_parse_bulk_import_reports_term_too_long(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    set_setting(seeded_session, VOCAB_TERM_MAX_CHARS, "3")

    preview = vocab_service.parse_bulk_import(seeded_session, deck, "12345\t意味")

    assert "term exceeds" in preview.errors[0].reason


def test_parse_bulk_import_reports_meaning_too_long(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    set_setting(seeded_session, VOCAB_MEANING_MAX_CHARS, "3")

    preview = vocab_service.parse_bulk_import(seeded_session, deck, "用語\t12345")

    assert "meaning exceeds" in preview.errors[0].reason


def test_parse_bulk_import_detects_duplicate_against_existing_card(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    make_card(seeded_session, deck, term="アイウ")

    preview = vocab_service.parse_bulk_import(seeded_session, deck, "あいう\t意味")

    assert preview.rows == []
    assert preview.duplicate_line_numbers == [1]


def test_parse_bulk_import_detects_duplicate_within_batch(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)

    preview = vocab_service.parse_bulk_import(seeded_session, deck, "用語\t意味1\n用語\t意味2")

    assert len(preview.rows) == 1
    assert preview.duplicate_line_numbers == [2]


def test_parse_bulk_import_rejects_too_many_rows(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    set_setting(seeded_session, VOCAB_IMPORT_MAX_ROWS, "1")

    with pytest.raises(VocabImportTooManyRowsError):
        vocab_service.parse_bulk_import(seeded_session, deck, "用語1\t意味1\n用語2\t意味2")


def test_parse_bulk_import_accepts_exactly_the_max_row_count(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    set_setting(seeded_session, VOCAB_IMPORT_MAX_ROWS, "2")

    preview = vocab_service.parse_bulk_import(seeded_session, deck, "用語1\t意味1\n用語2\t意味2")

    assert len(preview.rows) == 2


def test_confirm_bulk_import_rejects_too_many_rows_even_without_preview(seeded_session):
    """`parse_bulk_import`を経由せず直接確定APIへ渡された行も、行数上限を再検証すること
    （injection-reviewerレビューで検出：確定APIが信頼境界を素通りしていた、2026-11-15）。"""
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    set_setting(seeded_session, VOCAB_IMPORT_MAX_ROWS, "1")
    rows = [
        vocab_service.VocabImportRow(1, "用語1", "意味1", None, None),
        vocab_service.VocabImportRow(2, "用語2", "意味2", None, None),
    ]

    with pytest.raises(VocabImportTooManyRowsError):
        vocab_service.confirm_bulk_import(seeded_session, deck, rows)


def test_confirm_bulk_import_rejects_term_too_long_even_without_preview(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    set_setting(seeded_session, VOCAB_TERM_MAX_CHARS, "3")
    rows = [vocab_service.VocabImportRow(1, "12345", "意味", None, None)]

    with pytest.raises(ValidationError):
        vocab_service.confirm_bulk_import(seeded_session, deck, rows)


def test_parse_bulk_import_rejects_adversarial_long_line_quickly(seeded_session):
    """ReDoS対策の確認（巨大な1行でも1秒以内に解析が終わること）。"""
    import time

    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    huge_line = ("a" * 5000) + "\t" + ("b" * 5000)

    start = time.monotonic()
    vocab_service.parse_bulk_import(seeded_session, deck, huge_line)
    assert time.monotonic() - start < 1.0


def test_confirm_bulk_import_creates_cards(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    rows = [
        vocab_service.VocabImportRow(1, "用語1", "意味1", None, None),
        vocab_service.VocabImportRow(2, "用語2", "意味2", "別名", "補足"),
    ]

    created = vocab_service.confirm_bulk_import(seeded_session, deck, rows)

    assert created == 2
    assert len(vocab_service.list_cards_for_deck(seeded_session, deck.id)) == 2


def test_confirm_bulk_import_rejects_when_exceeding_deck_capacity(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    set_setting(seeded_session, VOCAB_DECK_MAX_CARDS, "1")
    rows = [
        vocab_service.VocabImportRow(1, "用語1", "意味1", None, None),
        vocab_service.VocabImportRow(2, "用語2", "意味2", None, None),
    ]

    with pytest.raises(VocabDeckCardLimitExceededError):
        vocab_service.confirm_bulk_import(seeded_session, deck, rows)


def test_export_deck_writes_tab_separated_text(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    make_card(seeded_session, deck, term="用語", meaning="意味", aliases="別名", note="補足")

    text = vocab_service.export_deck(seeded_session, deck)

    assert text == "用語\t意味\t別名\t補足\n"


def test_export_deck_empty_deck_returns_empty_string(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)

    assert vocab_service.export_deck(seeded_session, deck) == ""


# ---------------------------------------------------------------------------
# 絞り込み・並び順
# ---------------------------------------------------------------------------


def _stats_for(session, cards):
    return vocab_service.compute_card_stats(session, [c.id for c in cards])


def test_filter_cards_all_returns_everything(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    cards = [make_card(seeded_session, deck, term=str(i)) for i in range(2)]

    result = vocab_service.filter_cards(
        cards, _stats_for(seeded_session, cards), filter_key="ALL", weak_accuracy_percent=70
    )

    assert len(result) == 2


def test_filter_cards_checked_only(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    checked = make_card(seeded_session, deck, term="A", is_checked=True)
    make_card(seeded_session, deck, term="B", is_checked=False)
    cards = vocab_service.list_cards_for_deck(seeded_session, deck.id)

    result = vocab_service.filter_cards(
        cards, _stats_for(seeded_session, cards), filter_key="CHECKED", weak_accuracy_percent=70
    )

    assert [c.id for c in result] == [checked.id]


def test_filter_cards_ever_wrong(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    wrong_card = make_card(seeded_session, deck, term="A")
    make_card(seeded_session, deck, term="B")
    vocab_service.record_answer(
        seeded_session, wrong_card, VocabQuizMode.FLASH_TERM_TO_MEANING, False
    )
    cards = vocab_service.list_cards_for_deck(seeded_session, deck.id)

    result = vocab_service.filter_cards(
        cards, _stats_for(seeded_session, cards), filter_key="EVER_WRONG", weak_accuracy_percent=70
    )

    assert [c.id for c in result] == [wrong_card.id]


def test_filter_cards_consecutive_wrong(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    streak_card = make_card(seeded_session, deck, term="A")
    recovered_card = make_card(seeded_session, deck, term="B")
    vocab_service.record_answer(
        seeded_session, streak_card, VocabQuizMode.FLASH_TERM_TO_MEANING, False
    )
    vocab_service.record_answer(
        seeded_session, recovered_card, VocabQuizMode.FLASH_TERM_TO_MEANING, False
    )
    vocab_service.record_answer(
        seeded_session, recovered_card, VocabQuizMode.FLASH_TERM_TO_MEANING, True
    )
    cards = vocab_service.list_cards_for_deck(seeded_session, deck.id)

    result = vocab_service.filter_cards(
        cards,
        _stats_for(seeded_session, cards),
        filter_key="CONSECUTIVE_WRONG",
        weak_accuracy_percent=70,
    )

    assert [c.id for c in result] == [streak_card.id]


def test_filter_cards_weak(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    weak_card = make_card(seeded_session, deck, term="A")
    strong_card = make_card(seeded_session, deck, term="B")
    vocab_service.record_answer(
        seeded_session, weak_card, VocabQuizMode.FLASH_TERM_TO_MEANING, False
    )
    vocab_service.record_answer(
        seeded_session, strong_card, VocabQuizMode.FLASH_TERM_TO_MEANING, True
    )
    cards = vocab_service.list_cards_for_deck(seeded_session, deck.id)

    result = vocab_service.filter_cards(
        cards, _stats_for(seeded_session, cards), filter_key="WEAK", weak_accuracy_percent=70
    )

    assert [c.id for c in result] == [weak_card.id]


def test_filter_cards_unanswered(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    unanswered = make_card(seeded_session, deck, term="A")
    answered = make_card(seeded_session, deck, term="B")
    vocab_service.record_answer(seeded_session, answered, VocabQuizMode.FLASH_TERM_TO_MEANING, True)
    cards = vocab_service.list_cards_for_deck(seeded_session, deck.id)

    result = vocab_service.filter_cards(
        cards, _stats_for(seeded_session, cards), filter_key="UNANSWERED", weak_accuracy_percent=70
    )

    assert [c.id for c in result] == [unanswered.id]


def test_filter_cards_unknown_filter_raises(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    cards = [make_card(seeded_session, deck)]

    with pytest.raises(ValidationError):
        vocab_service.filter_cards(
            cards, _stats_for(seeded_session, cards), filter_key="NOPE", weak_accuracy_percent=70
        )


def test_sort_cards_registered_order(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    second = make_card(seeded_session, deck, term="B", display_order=1)
    first = make_card(seeded_session, deck, term="A", display_order=0)
    cards = [second, first]

    result = vocab_service.sort_cards(
        cards, _stats_for(seeded_session, cards), sort_key="REGISTERED"
    )

    assert [c.id for c in result] == [first.id, second.id]


def test_sort_cards_accuracy_asc_puts_unanswered_last(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    low_accuracy = make_card(seeded_session, deck, term="low")
    high_accuracy = make_card(seeded_session, deck, term="high")
    unanswered = make_card(seeded_session, deck, term="none")
    vocab_service.record_answer(
        seeded_session, low_accuracy, VocabQuizMode.FLASH_TERM_TO_MEANING, False
    )
    vocab_service.record_answer(
        seeded_session, high_accuracy, VocabQuizMode.FLASH_TERM_TO_MEANING, True
    )
    cards = [unanswered, high_accuracy, low_accuracy]

    result = vocab_service.sort_cards(
        cards, _stats_for(seeded_session, cards), sort_key="ACCURACY_ASC"
    )

    assert [c.id for c in result] == [low_accuracy.id, high_accuracy.id, unanswered.id]


def test_sort_cards_incorrect_count_desc(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    more_wrong = make_card(seeded_session, deck, term="A")
    less_wrong = make_card(seeded_session, deck, term="B")
    vocab_service.record_answer(
        seeded_session, more_wrong, VocabQuizMode.FLASH_TERM_TO_MEANING, False
    )
    vocab_service.record_answer(
        seeded_session, more_wrong, VocabQuizMode.FLASH_TERM_TO_MEANING, False
    )
    vocab_service.record_answer(
        seeded_session, less_wrong, VocabQuizMode.FLASH_TERM_TO_MEANING, False
    )
    cards = [less_wrong, more_wrong]

    result = vocab_service.sort_cards(
        cards, _stats_for(seeded_session, cards), sort_key="INCORRECT_COUNT_DESC"
    )

    assert [c.id for c in result] == [more_wrong.id, less_wrong.id]


def test_sort_cards_consecutive_wrong_desc(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    streaky = make_card(seeded_session, deck, term="A")
    not_streaky = make_card(seeded_session, deck, term="B")
    vocab_service.record_answer(seeded_session, streaky, VocabQuizMode.FLASH_TERM_TO_MEANING, False)
    vocab_service.record_answer(seeded_session, streaky, VocabQuizMode.FLASH_TERM_TO_MEANING, False)
    cards = [not_streaky, streaky]

    result = vocab_service.sort_cards(
        cards, _stats_for(seeded_session, cards), sort_key="CONSECUTIVE_WRONG_DESC"
    )

    assert [c.id for c in result] == [streaky.id, not_streaky.id]


def test_sort_cards_unknown_sort_raises(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    cards = [make_card(seeded_session, deck)]

    with pytest.raises(ValidationError):
        vocab_service.sort_cards(cards, _stats_for(seeded_session, cards), sort_key="NOPE")


# ---------------------------------------------------------------------------
# 出題セッションの並び順
# ---------------------------------------------------------------------------


def test_select_session_cards_random_is_reproducible_with_seeded_rng(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    cards = [make_card(seeded_session, deck, term=str(i), display_order=i) for i in range(5)]
    stats = _stats_for(seeded_session, cards)

    result1 = vocab_service.select_session_cards(
        cards, stats, order_key="RANDOM", question_count=5, rng=random.Random(42)
    )
    result2 = vocab_service.select_session_cards(
        cards, stats, order_key="RANDOM", question_count=5, rng=random.Random(42)
    )

    assert [c.id for c in result1] == [c.id for c in result2]


def test_select_session_cards_truncates_to_question_count(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    cards = [make_card(seeded_session, deck, term=str(i), display_order=i) for i in range(5)]
    stats = _stats_for(seeded_session, cards)

    result = vocab_service.select_session_cards(
        cards, stats, order_key="REGISTERED", question_count=2, rng=random.Random(1)
    )

    assert [c.id for c in result] == [cards[0].id, cards[1].id]


def test_select_session_cards_weak_order_prioritizes_consecutive_then_accuracy(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    weakest = make_card(seeded_session, deck, term="weakest")
    somewhat_weak = make_card(seeded_session, deck, term="somewhat")
    strong = make_card(seeded_session, deck, term="strong")
    vocab_service.record_answer(seeded_session, weakest, VocabQuizMode.FLASH_TERM_TO_MEANING, False)
    vocab_service.record_answer(seeded_session, weakest, VocabQuizMode.FLASH_TERM_TO_MEANING, False)
    vocab_service.record_answer(
        seeded_session, somewhat_weak, VocabQuizMode.FLASH_TERM_TO_MEANING, False
    )
    vocab_service.record_answer(seeded_session, strong, VocabQuizMode.FLASH_TERM_TO_MEANING, True)
    cards = [strong, somewhat_weak, weakest]
    stats = _stats_for(seeded_session, cards)

    result = vocab_service.select_session_cards(
        cards, stats, order_key="WEAK_ORDER", question_count=3, rng=random.Random(1)
    )

    assert [c.id for c in result] == [weakest.id, somewhat_weak.id, strong.id]


def test_select_session_cards_unknown_order_raises(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    cards = [make_card(seeded_session, deck)]
    stats = _stats_for(seeded_session, cards)

    with pytest.raises(ValidationError):
        vocab_service.select_session_cards(cards, stats, order_key="NOPE", question_count=1)


# ---------------------------------------------------------------------------
# 入力式判定
# ---------------------------------------------------------------------------


def test_judge_typed_answer_matches_exact_term(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck, term="アプリケーション")

    assert vocab_service.judge_typed_answer(card, "あぷりけーしょん") is True


def test_judge_typed_answer_matches_hiragana_term_with_katakana_answer(seeded_session):
    """カタカナ→ひらがなの一方向だけでなく、用語がひらがな・回答がカタカナの逆方向でも
    正規化が効くこと（`normalize_for_vocab_match`は双方向に変換するため）。"""
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck, term="あぷりけーしょん")

    assert vocab_service.judge_typed_answer(card, "アプリケーション") is True


def test_judge_typed_answer_matches_alias(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck, term="用語", aliases="別名1\n別名2")

    assert vocab_service.judge_typed_answer(card, "別名2") is True


def test_judge_typed_answer_ignores_blank_alias_lines(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck, term="用語", aliases="\n別名\n")

    assert vocab_service.judge_typed_answer(card, "") is False


def test_judge_typed_answer_rejects_mismatch(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck, term="用語", aliases="別名")

    assert vocab_service.judge_typed_answer(card, "まちがい") is False


# ---------------------------------------------------------------------------
# 4択選択肢の生成
# ---------------------------------------------------------------------------


def test_build_choice_option_ids_returns_four_ids_including_target(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    target = make_card(seeded_session, deck, term="対象", meaning="対象の意味")
    for i in range(3):
        make_card(seeded_session, deck, term=f"他{i}", meaning=f"他の意味{i}")
    cards = vocab_service.list_cards_for_deck(seeded_session, deck.id)

    option_ids = vocab_service.build_choice_option_ids(
        cards, target, field="meaning", rng=random.Random(1)
    )

    assert option_ids is not None
    assert len(option_ids) == 4
    assert target.id in option_ids


def test_build_choice_option_ids_deduplicates_candidates_with_same_normalized_value(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    target = make_card(seeded_session, deck, term="対象", meaning="対象の意味")
    make_card(seeded_session, deck, term="他1", meaning="同じ意味")
    make_card(seeded_session, deck, term="他2", meaning="同じ意味")
    make_card(seeded_session, deck, term="他3", meaning="別の意味")
    cards = vocab_service.list_cards_for_deck(seeded_session, deck.id)

    option_ids = vocab_service.build_choice_option_ids(
        cards, target, field="meaning", rng=random.Random(1)
    )

    assert option_ids is None  # 重複排除後は2種類しか残らず3件に満たない


def test_build_choice_option_ids_returns_none_when_not_enough_distractors(seeded_session):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    target = make_card(seeded_session, deck, term="対象", meaning="対象の意味")
    make_card(seeded_session, deck, term="他1", meaning="意味1")
    cards = vocab_service.list_cards_for_deck(seeded_session, deck.id)

    option_ids = vocab_service.build_choice_option_ids(
        cards, target, field="meaning", rng=random.Random(1)
    )

    assert option_ids is None
