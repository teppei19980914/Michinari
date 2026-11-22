"""単語帳APIのテスト（開発Todo_単語帳_v1.0 要件A・要件B）。"""

import datetime as dt

from app.constants.app_setting_keys import (
    MILESTONE_VOCAB_MASTERED_TERMS_THRESHOLDS,
    VOCAB_IMPORT_MAX_ROWS,
    VOCAB_MASTERY_STREAK,
)
from app.constants.enums import GoalCategory, VocabQuizMode
from app.models.quiz import QuizQuestion
from app.models.vocab import VocabCard
from app.services import milestone_service_common, vocab_service
from tests.diary_helpers import make_exam_goal
from tests.quiz_helpers import stub_quiz_ai
from tests.vocab_helpers import (
    make_answer_log,
    make_card,
    make_deck,
    make_reading_goal,
    set_setting,
)

#: 日次報告の確定は前日までしか遡れない（BACKDATE_LIMIT_EXCEEDED）ため、提案系テストの
#: 記録日は固定の過去日ではなく実行時の「今日」を基準にする（test_api_records_exam.py等の
#: 既存方針と同じ、CODING_RULES.md「タイムスタンプでの並び替え」とは別件だが同根の時間依存
#: バグ〈2026-11-22、日付経過により"2026-11-20"固定値が失敗するようになり検出〉への対策）。
RECORD_DATE = dt.date.today().isoformat()

# ---------------------------------------------------------------------------
# デッキ
# ---------------------------------------------------------------------------


def test_create_vocab_deck_succeeds_for_exam_goal(seeded_session, client):
    goal = make_exam_goal(seeded_session)

    response = client.post(
        f"/api/v1/goals/{goal.id}/vocab-decks", json={"name": "単語帳1", "description": "説明"}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "単語帳1"
    assert body["use_in_ai"] is True
    assert body["card_count"] == 0


def test_create_vocab_deck_rejects_reading_goal(seeded_session, client):
    goal = make_reading_goal(seeded_session)

    response = client.post(f"/api/v1/goals/{goal.id}/vocab-decks", json={"name": "単語帳1"})

    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "VOCAB_DECK_GOAL_CATEGORY"


def test_create_vocab_deck_unknown_goal_returns_404(client):
    response = client.post("/api/v1/goals/999999/vocab-decks", json={"name": "単語帳1"})
    assert response.status_code == 404


def test_list_vocab_decks_returns_decks_for_goal(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    make_deck(seeded_session, goal, "A")
    other_goal = make_exam_goal(seeded_session, name="別の目標")
    make_deck(seeded_session, other_goal, "B")

    response = client.get(f"/api/v1/goals/{goal.id}/vocab-decks")

    assert response.status_code == 200
    names = [deck["name"] for deck in response.json()]
    assert names == ["A"]


def test_list_vocab_decks_reports_each_decks_own_card_count(seeded_session, client):
    """複数デッキ分のcard_countが、デッキごとに正しく区別して返ること
    （一括集計〈count_cards_by_deck〉が他デッキの件数を混ぜないことの確認）。"""
    goal = make_exam_goal(seeded_session)
    deck_a = make_deck(seeded_session, goal, "A")
    deck_b = make_deck(seeded_session, goal, "B")
    make_card(seeded_session, deck_a, term="1")
    make_card(seeded_session, deck_a, term="2")
    make_card(seeded_session, deck_b, term="3")

    response = client.get(f"/api/v1/goals/{goal.id}/vocab-decks")

    assert response.status_code == 200
    counts = {deck["name"]: deck["card_count"] for deck in response.json()}
    assert counts == {"A": 2, "B": 1}


def test_list_vocab_decks_reports_each_decks_own_mastered_card_count(seeded_session, client):
    """開発Todo_単語帳_v1.0 要件E E-U6：デッキごとの習得数が区別して返ること
    （`compute_mastered_card_counts_by_deck`が他デッキの習得数を混ぜないことの確認）。"""
    set_setting(seeded_session, VOCAB_MASTERY_STREAK, "1")
    goal = make_exam_goal(seeded_session)
    deck_a = make_deck(seeded_session, goal, "A")
    deck_b = make_deck(seeded_session, goal, "B")
    mastered_card = make_card(seeded_session, deck_a, term="習得済み")
    make_card(seeded_session, deck_b, term="未習得")
    make_answer_log(
        seeded_session, mastered_card, is_correct=True, answered_at=dt.datetime(2026, 1, 1)
    )

    response = client.get(f"/api/v1/goals/{goal.id}/vocab-decks")

    assert response.status_code == 200
    counts = {deck["name"]: deck["mastered_card_count"] for deck in response.json()}
    assert counts == {"A": 1, "B": 0}


def test_get_vocab_deck_returns_deck(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal, "単語帳")

    response = client.get(f"/api/v1/vocab-decks/{deck.id}")

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "単語帳"


def test_get_vocab_deck_unknown_id_returns_404(client):
    response = client.get("/api/v1/vocab-decks/999999")
    assert response.status_code == 404


def test_get_vocab_deck_reports_session_question_count_default_and_max(seeded_session, client):
    """出題開始フォームの初期値・上限として画面へ渡す`vocab.session_default_questions`・
    `vocab.session_max_questions`が単語帳詳細のレスポンスに反映されること（軽微1の再現
    テスト。設定値を変更した場合も反映されること）。"""
    from app.constants.app_setting_keys import (
        VOCAB_SESSION_DEFAULT_QUESTIONS,
        VOCAB_SESSION_MAX_QUESTIONS,
    )

    set_setting(seeded_session, VOCAB_SESSION_DEFAULT_QUESTIONS, "15")
    set_setting(seeded_session, VOCAB_SESSION_MAX_QUESTIONS, "50")
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)

    response = client.get(f"/api/v1/vocab-decks/{deck.id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_default_questions"] == 15
    assert body["session_max_questions"] == 50


def test_update_vocab_deck_changes_fields(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal, "元の名前")

    response = client.patch(f"/api/v1/vocab-decks/{deck.id}", json={"use_in_ai": False})

    assert response.status_code == 200, response.text
    assert response.json()["use_in_ai"] is False


def test_update_vocab_deck_unknown_id_returns_404(client):
    response = client.patch("/api/v1/vocab-decks/999999", json={"name": "x"})
    assert response.status_code == 404


def test_delete_vocab_deck_removes_it(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)

    response = client.delete(f"/api/v1/vocab-decks/{deck.id}")

    assert response.status_code == 200
    assert client.get(f"/api/v1/vocab-decks/{deck.id}").status_code == 404


def test_delete_vocab_deck_unknown_id_returns_404(client):
    assert client.delete("/api/v1/vocab-decks/999999").status_code == 404


def test_reorder_vocab_decks_applies_order(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    deck_a = make_deck(seeded_session, goal, "A")
    deck_b = make_deck(seeded_session, goal, "B")

    response = client.put(
        f"/api/v1/goals/{goal.id}/vocab-decks/order",
        json={"ordered_deck_ids": [deck_b.id, deck_a.id]},
    )

    assert response.status_code == 200, response.text
    decks = client.get(f"/api/v1/goals/{goal.id}/vocab-decks").json()
    assert [d["id"] for d in decks] == [deck_b.id, deck_a.id]


def test_reorder_vocab_decks_mismatched_ids_returns_400(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    make_deck(seeded_session, goal, "A")

    response = client.put(
        f"/api/v1/goals/{goal.id}/vocab-decks/order", json={"ordered_deck_ids": [999999]}
    )

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# カード
# ---------------------------------------------------------------------------


def test_create_vocab_card_succeeds(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)

    response = client.post(
        f"/api/v1/vocab-decks/{deck.id}/cards",
        json={"term": "用語", "meaning": "意味", "aliases": "別名", "note": "補足"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["term"] == "用語"
    assert body["accuracy_percent"] is None


def test_create_vocab_card_unknown_deck_returns_404(client):
    response = client.post(
        "/api/v1/vocab-decks/999999/cards", json={"term": "用語", "meaning": "意味"}
    )
    assert response.status_code == 404


def test_create_vocab_card_rejects_xss_payload_as_plain_text(seeded_session, client):
    """用語・意味はプレーンテキストとして保存・返却されること（画面側は生HTML解釈をしない
    方針だが、APIが文字列をそのまま保存・返すこと自体は確認する）。"""
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    payload_text = "<img src=x onerror=alert(1)>"

    response = client.post(
        f"/api/v1/vocab-decks/{deck.id}/cards", json={"term": payload_text, "meaning": "意味"}
    )

    assert response.status_code == 200, response.text
    assert response.json()["term"] == payload_text


def test_list_vocab_cards_includes_stats(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck)
    vocab_service.record_answer(seeded_session, card, VocabQuizMode.FLASH_TERM_TO_MEANING, True)

    response = client.get(f"/api/v1/vocab-decks/{deck.id}/cards")

    assert response.status_code == 200
    body = response.json()[0]
    assert body["correct_count"] == 1
    assert body["accuracy_percent"] == 100.0


def test_list_vocab_cards_includes_is_mastered(seeded_session, client):
    """開発Todo_単語帳_v1.0 要件E E-U1：直近`vocab.mastery_streak`回がすべて正解のカードは
    `is_mastered=True`、未達は`False`。"""
    set_setting(seeded_session, VOCAB_MASTERY_STREAK, "2")
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    mastered_card = make_card(seeded_session, deck, term="習得済み")
    unmastered_card = make_card(seeded_session, deck, term="未習得")
    make_answer_log(
        seeded_session, mastered_card, is_correct=True, answered_at=dt.datetime(2026, 1, 1, 9)
    )
    make_answer_log(
        seeded_session, mastered_card, is_correct=True, answered_at=dt.datetime(2026, 1, 1, 10)
    )
    make_answer_log(
        seeded_session, unmastered_card, is_correct=True, answered_at=dt.datetime(2026, 1, 1)
    )

    response = client.get(f"/api/v1/vocab-decks/{deck.id}/cards")

    assert response.status_code == 200
    is_mastered_by_term = {card["term"]: card["is_mastered"] for card in response.json()}
    assert is_mastered_by_term == {"習得済み": True, "未習得": False}


def test_list_vocab_cards_filter_unmastered_excludes_mastered_cards(seeded_session, client):
    set_setting(seeded_session, VOCAB_MASTERY_STREAK, "1")
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    mastered_card = make_card(seeded_session, deck, term="習得済み")
    make_card(seeded_session, deck, term="未習得")
    make_answer_log(
        seeded_session, mastered_card, is_correct=True, answered_at=dt.datetime(2026, 1, 1)
    )

    response = client.get(
        f"/api/v1/vocab-decks/{deck.id}/cards", params={"filter": "UNMASTERED"}
    )

    assert response.status_code == 200
    terms = [card["term"] for card in response.json()]
    assert terms == ["未習得"]


def test_list_vocab_cards_unknown_sort_returns_400(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    make_card(seeded_session, deck)

    response = client.get(f"/api/v1/vocab-decks/{deck.id}/cards", params={"sort": "NOPE"})

    assert response.status_code == 400


def test_update_vocab_card_changes_fields(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck, term="元の用語")

    response = client.patch(f"/api/v1/vocab-cards/{card.id}", json={"term": "新しい用語"})

    assert response.status_code == 200, response.text
    assert response.json()["term"] == "新しい用語"


def test_update_vocab_card_unknown_id_returns_404(client):
    response = client.patch("/api/v1/vocab-cards/999999", json={"term": "x"})
    assert response.status_code == 404


def test_check_vocab_card_toggles_flag(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck)

    response = client.patch(f"/api/v1/vocab-cards/{card.id}/check", json={"is_checked": True})

    assert response.status_code == 200, response.text
    assert response.json()["is_checked"] is True


def test_delete_vocab_card_removes_it(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck)

    response = client.delete(f"/api/v1/vocab-cards/{card.id}")

    assert response.status_code == 200
    assert client.get(f"/api/v1/vocab-decks/{deck.id}/cards").json() == []


def test_delete_vocab_card_unknown_id_returns_404(client):
    assert client.delete("/api/v1/vocab-cards/999999").status_code == 404


# ---------------------------------------------------------------------------
# 一括登録・エクスポート
# ---------------------------------------------------------------------------


def test_preview_vocab_import_returns_rows_and_errors(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)

    response = client.post(
        f"/api/v1/vocab-decks/{deck.id}/cards/import-preview",
        json={"text": "用語1\t意味1\n\t意味のみ"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["rows"]) == 1
    assert len(body["errors"]) == 1


def test_preview_vocab_import_unknown_deck_returns_404(client):
    response = client.post("/api/v1/vocab-decks/999999/cards/import-preview", json={"text": "a\tb"})
    assert response.status_code == 404


def test_preview_vocab_import_too_many_rows_returns_400(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    set_setting(seeded_session, VOCAB_IMPORT_MAX_ROWS, "1")

    response = client.post(
        f"/api/v1/vocab-decks/{deck.id}/cards/import-preview",
        json={"text": "用語1\t意味1\n用語2\t意味2"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VOCAB_IMPORT_TOO_MANY_ROWS"


def test_preview_vocab_import_adversarial_repetition_completes_quickly(seeded_session, client):
    """ReDoS対策の回帰確認（敵対的な繰り返し入力でも1秒以内に応答すること）。"""
    import time

    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    adversarial_text = "\n".join(f"{'a' * 100}\t{'b' * 100}" for _ in range(400))

    start = time.monotonic()
    response = client.post(
        f"/api/v1/vocab-decks/{deck.id}/cards/import-preview", json={"text": adversarial_text}
    )
    assert time.monotonic() - start < 1.0
    assert response.status_code == 200


def test_confirm_vocab_import_creates_cards(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)

    response = client.post(
        f"/api/v1/vocab-decks/{deck.id}/cards/import",
        json={"rows": [{"term": "用語1", "meaning": "意味1"}]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["created_count"] == 1


def test_confirm_vocab_import_unknown_deck_returns_404(client):
    response = client.post(
        "/api/v1/vocab-decks/999999/cards/import", json={"rows": [{"term": "a", "meaning": "b"}]}
    )
    assert response.status_code == 404


def test_export_vocab_deck_returns_tab_separated_text(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    make_card(seeded_session, deck, term="用語", meaning="意味")

    response = client.get(f"/api/v1/vocab-decks/{deck.id}/export")

    assert response.status_code == 200
    assert response.json()["text"] == "用語\t意味\t\t\n"


def test_export_vocab_deck_unknown_id_returns_404(client):
    assert client.get("/api/v1/vocab-decks/999999/export").status_code == 404


# ---------------------------------------------------------------------------
# 出題セッション・解答
# ---------------------------------------------------------------------------


def _make_deck_with_cards(session, count: int):
    goal = make_exam_goal(session)
    deck = make_deck(session, goal)
    cards = [make_card(session, deck, term=f"用語{i}", meaning=f"意味{i}") for i in range(count)]
    return deck, cards


def test_start_quiz_session_flash_mode_reveals_meaning(seeded_session, client):
    deck, cards = _make_deck_with_cards(seeded_session, 2)

    response = client.post(
        f"/api/v1/vocab-decks/{deck.id}/quiz-sessions",
        json={"mode": "FLASH_TERM_TO_MEANING", "question_count": 2},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["questions"]) == 2
    assert body["questions"][0]["reveal"] is not None


def test_start_quiz_session_flash_meaning_to_term_reveals_term(seeded_session, client):
    deck, cards = _make_deck_with_cards(seeded_session, 1)

    response = client.post(
        f"/api/v1/vocab-decks/{deck.id}/quiz-sessions",
        json={"mode": "FLASH_MEANING_TO_TERM", "question_count": 1},
    )

    assert response.status_code == 200, response.text
    question = response.json()["questions"][0]
    assert question["prompt"] == cards[0].meaning
    assert question["reveal"] == cards[0].term


def test_start_quiz_session_unmastered_filter_excludes_mastered_cards(seeded_session, client):
    """filter=UNMASTERED で出題を開始したとき、習得済み（直近`vocab.mastery_streak`回正解）
    のカードが出題されないこと（不具合1の再現テスト。`start_vocab_quiz_session`が
    `vocab_service.filter_cards`へ`mastered_card_ids`を渡していないと、一覧APIでは
    絞り込めるのに出題では習得済みカードも出てしまう）。"""
    set_setting(seeded_session, VOCAB_MASTERY_STREAK, "1")
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    mastered = make_card(seeded_session, deck, term="習得済み", meaning="習得済みの意味")
    unmastered = make_card(seeded_session, deck, term="未習得", meaning="未習得の意味")
    make_answer_log(seeded_session, mastered, is_correct=True, answered_at=dt.datetime(2026, 1, 1))

    response = client.post(
        f"/api/v1/vocab-decks/{deck.id}/quiz-sessions",
        json={"mode": "FLASH_TERM_TO_MEANING", "filter": "UNMASTERED", "question_count": 10},
    )

    assert response.status_code == 200, response.text
    card_ids = [q["card_id"] for q in response.json()["questions"]]
    assert card_ids == [unmastered.id]
    assert mastered.id not in card_ids


def test_start_quiz_session_unknown_deck_returns_404(client):
    """存在しない単語帳IDで出題を始めても404になること（軽微2の再現テスト。他の単語帳APIは
    全て`get_deck`/`get_card`で404化しているが、`start_vocab_quiz_session`だけ漏れていた）。"""
    response = client.post(
        "/api/v1/vocab-decks/999999/quiz-sessions",
        json={"mode": "FLASH_TERM_TO_MEANING", "question_count": 1},
    )

    assert response.status_code == 404


def test_start_quiz_session_choice_meaning_to_term_shows_term_options(seeded_session, client):
    deck, cards = _make_deck_with_cards(seeded_session, 5)

    response = client.post(
        f"/api/v1/vocab-decks/{deck.id}/quiz-sessions",
        json={"mode": "CHOICE_MEANING_TO_TERM", "question_count": 1},
    )

    assert response.status_code == 200, response.text
    question = response.json()["questions"][0]
    assert question["prompt"] in [c.meaning for c in cards]
    option_texts = {opt["text"] for opt in question["options"]}
    assert option_texts <= {c.term for c in cards}


def test_start_quiz_session_choice_mode_excludes_cards_without_enough_distractors(
    seeded_session, client
):
    """誤答選択肢が3つ作れないカードは出題から外し、除外件数を返す。"""
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    target = make_card(seeded_session, deck, term="対象", meaning="対象の意味")
    # 他のカードの意味をすべて同じにして、正規化後の誤答候補が1種類しかない状態を作る。
    for i in range(3):
        make_card(seeded_session, deck, term=f"他{i}", meaning="同じ意味")

    response = client.post(
        f"/api/v1/vocab-decks/{deck.id}/quiz-sessions",
        json={"mode": "CHOICE_TERM_TO_MEANING", "question_count": 4},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["excluded_count"] >= 1
    assert target.id not in [q["card_id"] for q in body["questions"]]


def test_start_quiz_session_typed_mode_does_not_reveal_term(seeded_session, client):
    deck, cards = _make_deck_with_cards(seeded_session, 1)

    response = client.post(
        f"/api/v1/vocab-decks/{deck.id}/quiz-sessions",
        json={"mode": "TYPED_MEANING_TO_TERM", "question_count": 1},
    )

    assert response.status_code == 200, response.text
    question = response.json()["questions"][0]
    assert question["reveal"] is None
    assert question["options"] is None


def test_start_quiz_session_choice_mode_returns_four_options(seeded_session, client):
    deck, cards = _make_deck_with_cards(seeded_session, 5)

    response = client.post(
        f"/api/v1/vocab-decks/{deck.id}/quiz-sessions",
        json={"mode": "CHOICE_TERM_TO_MEANING", "question_count": 1},
    )

    assert response.status_code == 200, response.text
    question = response.json()["questions"][0]
    assert len(question["options"]) == 4
    assert question["card_id"] in [opt["card_id"] for opt in question["options"]]
    assert question["reveal"] is None


def test_start_quiz_session_choice_mode_rejects_deck_with_fewer_than_four_cards(
    seeded_session, client
):
    deck, cards = _make_deck_with_cards(seeded_session, 3)

    response = client.post(
        f"/api/v1/vocab-decks/{deck.id}/quiz-sessions",
        json={"mode": "CHOICE_TERM_TO_MEANING", "question_count": 1},
    )

    assert response.status_code == 400


def test_start_quiz_session_question_count_over_limit_returns_400(seeded_session, client):
    deck, cards = _make_deck_with_cards(seeded_session, 1)

    response = client.post(
        f"/api/v1/vocab-decks/{deck.id}/quiz-sessions",
        json={"mode": "FLASH_TERM_TO_MEANING", "question_count": 10_000},
    )

    assert response.status_code == 400


def test_start_quiz_session_question_count_zero_returns_400(seeded_session, client):
    """上限超過だけでなく下限（0・負数）側の境界も拒否されること（`question_count < 1 or
    question_count > max_questions`の`or`の片方しか検証されていなかった、
    test-coverage-reviewerレビューで検出）。"""
    deck, cards = _make_deck_with_cards(seeded_session, 1)

    response = client.post(
        f"/api/v1/vocab-decks/{deck.id}/quiz-sessions",
        json={"mode": "FLASH_TERM_TO_MEANING", "question_count": 0},
    )

    assert response.status_code == 400


def test_start_quiz_session_question_count_at_exact_max_succeeds(seeded_session, client):
    deck, cards = _make_deck_with_cards(seeded_session, 1)

    response = client.post(
        f"/api/v1/vocab-decks/{deck.id}/quiz-sessions",
        json={"mode": "FLASH_TERM_TO_MEANING", "question_count": 100},
    )

    assert response.status_code == 200, response.text


def test_list_vocab_cards_does_not_mix_in_another_decks_cards(seeded_session, client):
    deck_a, _ = _make_deck_with_cards(seeded_session, 2)
    deck_b, cards_b = _make_deck_with_cards(seeded_session, 1)

    response = client.get(f"/api/v1/vocab-decks/{deck_a.id}/cards")

    assert response.status_code == 200
    returned_ids = {card["id"] for card in response.json()}
    assert cards_b[0].id not in returned_ids


def test_choice_quiz_session_never_offers_another_decks_cards_as_options(seeded_session, client):
    """4択の誤答選択肢に他デッキのカードが混ざらないこと（`build_choice_option_ids`へ
    渡す候補プールがAPI層で単一デッキに絞られていることの確認）。"""
    deck_a, cards_a = _make_deck_with_cards(seeded_session, 4)
    deck_b, cards_b = _make_deck_with_cards(seeded_session, 4)
    deck_b_ids = {card.id for card in cards_b}

    response = client.post(
        f"/api/v1/vocab-decks/{deck_a.id}/quiz-sessions",
        json={"mode": "CHOICE_TERM_TO_MEANING", "question_count": 4},
    )

    assert response.status_code == 200, response.text
    for question in response.json()["questions"]:
        option_ids = {opt["card_id"] for opt in question["options"]}
        assert option_ids.isdisjoint(deck_b_ids)


def test_answer_vocab_card_flash_mode_records_self_judged_result(seeded_session, client):
    deck, cards = _make_deck_with_cards(seeded_session, 1)

    response = client.post(
        f"/api/v1/vocab-cards/{cards[0].id}/answer",
        json={"mode": "FLASH_TERM_TO_MEANING", "self_judged_correct": True},
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_correct"] is True


def test_answer_vocab_card_flash_mode_requires_self_judged_correct(seeded_session, client):
    deck, cards = _make_deck_with_cards(seeded_session, 1)

    response = client.post(
        f"/api/v1/vocab-cards/{cards[0].id}/answer", json={"mode": "FLASH_TERM_TO_MEANING"}
    )

    assert response.status_code == 400


def test_answer_vocab_card_typed_mode_judges_server_side(seeded_session, client):
    deck, cards = _make_deck_with_cards(seeded_session, 1)

    response = client.post(
        f"/api/v1/vocab-cards/{cards[0].id}/answer",
        json={"mode": "TYPED_MEANING_TO_TERM", "answer_text": cards[0].term},
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_correct"] is True


def test_answer_vocab_card_typed_mode_requires_answer_text(seeded_session, client):
    deck, cards = _make_deck_with_cards(seeded_session, 1)

    response = client.post(
        f"/api/v1/vocab-cards/{cards[0].id}/answer", json={"mode": "TYPED_MEANING_TO_TERM"}
    )

    assert response.status_code == 400


def test_answer_vocab_card_choice_mode_correct_when_selected_matches_target(seeded_session, client):
    deck, cards = _make_deck_with_cards(seeded_session, 4)

    response = client.post(
        f"/api/v1/vocab-cards/{cards[0].id}/answer",
        json={"mode": "CHOICE_TERM_TO_MEANING", "selected_card_id": cards[0].id},
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_correct"] is True


def test_answer_vocab_card_choice_mode_incorrect_when_selected_differs(seeded_session, client):
    deck, cards = _make_deck_with_cards(seeded_session, 4)

    response = client.post(
        f"/api/v1/vocab-cards/{cards[0].id}/answer",
        json={"mode": "CHOICE_TERM_TO_MEANING", "selected_card_id": cards[1].id},
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_correct"] is False


def test_answer_vocab_card_choice_mode_requires_selected_card_id(seeded_session, client):
    deck, cards = _make_deck_with_cards(seeded_session, 4)

    response = client.post(
        f"/api/v1/vocab-cards/{cards[0].id}/answer", json={"mode": "CHOICE_TERM_TO_MEANING"}
    )

    assert response.status_code == 400


def test_answer_vocab_card_unknown_id_returns_404(client):
    response = client.post(
        "/api/v1/vocab-cards/999999/answer",
        json={"mode": "FLASH_TERM_TO_MEANING", "self_judged_correct": True},
    )
    assert response.status_code == 404


def test_answer_vocab_card_does_not_affect_todays_quiz_tables(seeded_session, client):
    """単語帳の問題集での解答は、今日の復習の仕組み（quiz_answer_log）に影響しないこと
    （開発Todo §0 U4）。"""
    from app.models.quiz import QuizAnswerLog

    deck, cards = _make_deck_with_cards(seeded_session, 1)

    client.post(
        f"/api/v1/vocab-cards/{cards[0].id}/answer",
        json={"mode": "FLASH_TERM_TO_MEANING", "self_judged_correct": True},
    )

    assert seeded_session.query(QuizAnswerLog).count() == 0


# ---------------------------------------------------------------------------
# セッション終了時の節目判定（開発Todo_単語帳_v1.0 要件E E-U3）
# ---------------------------------------------------------------------------


def test_complete_vocab_quiz_session_records_milestone_when_threshold_reached(
    seeded_session, client
):
    set_setting(seeded_session, VOCAB_MASTERY_STREAK, "1")
    set_setting(seeded_session, MILESTONE_VOCAB_MASTERED_TERMS_THRESHOLDS, "1")
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck)
    make_answer_log(seeded_session, card, is_correct=True, answered_at=dt.datetime(2026, 1, 1))

    response = client.post(f"/api/v1/vocab-decks/{deck.id}/quiz-sessions/complete")

    assert response.status_code == 200, response.text
    pending = client.get(f"/api/v1/goals/{goal.id}/milestones/pending-celebrations").json()
    keys = {(m["milestone_type"], m["milestone_key"]) for m in pending}
    assert ("VOCAB_MASTERED_TERMS", "1") in keys


def test_complete_vocab_quiz_session_unknown_deck_returns_404(client):
    response = client.post("/api/v1/vocab-decks/999999/quiz-sessions/complete")
    assert response.status_code == 404


def test_complete_vocab_quiz_session_does_not_double_record_with_later_record_finalize(
    seeded_session, client
):
    """セッション終了時の判定と、その後の記録確定時の判定（`detect_and_record_for_category`）
    の両方を実行しても、節目が二重に記録されないこと（開発Todo_単語帳_v1.0 要件E 完了条件）。"""
    set_setting(seeded_session, VOCAB_MASTERY_STREAK, "1")
    set_setting(seeded_session, MILESTONE_VOCAB_MASTERED_TERMS_THRESHOLDS, "1")
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck)
    make_answer_log(seeded_session, card, is_correct=True, answered_at=dt.datetime(2026, 1, 1))

    response = client.post(f"/api/v1/vocab-decks/{deck.id}/quiz-sessions/complete")
    assert response.status_code == 200, response.text
    milestone_service_common.detect_and_record_for_category(
        seeded_session, GoalCategory.EXAM, dt.date(2026, 1, 2)
    )
    seeded_session.commit()

    achievements = client.get(f"/api/v1/goals/{goal.id}/milestones").json()
    keys = [
        (a["milestone_type"], a["milestone_key"])
        for a in achievements
        if a["milestone_type"] == "VOCAB_MASTERED_TERMS"
    ]
    assert keys == [("VOCAB_MASTERED_TERMS", "1")]


def test_update_vocab_card_deletes_its_quiz_questions(seeded_session, client):
    """用語・意味・別名を編集したら、そのカードを出典とする今日の復習の問題を削除すること
    （開発Todo_単語帳_v1.0 要件B。古い内容のまま出題し続けない）。"""
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck, term="元の用語")
    seeded_session.add(
        QuizQuestion(
            vocab_card_id=card.id,
            question_text="問題文",
            choice_1="A",
            choice_2="B",
            choice_3="C",
            choice_4="D",
            correct_choice_index=0,
            explanation="解説",
            interval_index=0,
            next_due_date=dt.date.today(),
        )
    )
    seeded_session.commit()

    response = client.patch(f"/api/v1/vocab-cards/{card.id}", json={"term": "新しい用語"})

    assert response.status_code == 200, response.text
    assert seeded_session.query(QuizQuestion).count() == 0


def _make_card_with_quiz_question(session, card, *, interval_index: int = 3):
    question = QuizQuestion(
        vocab_card_id=card.id,
        question_text="問題文",
        choice_1="A",
        choice_2="B",
        choice_3="C",
        choice_4="D",
        correct_choice_index=0,
        explanation="解説",
        interval_index=interval_index,
        next_due_date=dt.date.today(),
    )
    session.add(question)
    session.commit()
    return question


def test_update_vocab_card_note_only_change_keeps_quiz_questions(seeded_session, client):
    """補足（note）だけを変える更新では、今日の復習の問題（間隔の進み具合を含む）が
    消えないこと（不具合3の再現テスト。要件Bの仕様は「用語・意味・別名を編集したら削除する」
    であり、補足はその対象外）。"""
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck, term="用語", meaning="意味", note="元の補足")
    _make_card_with_quiz_question(seeded_session, card, interval_index=3)

    response = client.patch(
        f"/api/v1/vocab-cards/{card.id}",
        json={"term": "用語", "meaning": "意味", "note": "新しい補足"},
    )

    assert response.status_code == 200, response.text
    question = seeded_session.query(QuizQuestion).one()
    assert question.interval_index == 3


def test_update_vocab_card_resending_same_values_keeps_quiz_questions(seeded_session, client):
    """term・meaning・aliasesを変更前と同じ値で送り直した場合は、内容が変わっていないため
    問題を削除しないこと（不具合3）。"""
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck, term="用語", meaning="意味", aliases="別名")
    _make_card_with_quiz_question(seeded_session, card)

    response = client.patch(
        f"/api/v1/vocab-cards/{card.id}",
        json={"term": "用語", "meaning": "意味", "aliases": "別名"},
    )

    assert response.status_code == 200, response.text
    assert seeded_session.query(QuizQuestion).count() == 1


def test_check_vocab_card_keeps_quiz_questions(seeded_session, client):
    """チェックの切り替え（`PATCH /vocab-cards/{id}/check`）は今日の復習の問題を削除しないこと
    （不具合3、既存の`check_vocab_card`エンドポイントはそもそも削除を呼ばないことの回帰防止）。
    """
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck, term="用語", meaning="意味")
    _make_card_with_quiz_question(seeded_session, card)

    response = client.patch(f"/api/v1/vocab-cards/{card.id}/check", json={"is_checked": True})

    assert response.status_code == 200, response.text
    assert seeded_session.query(QuizQuestion).count() == 1


def test_update_vocab_card_meaning_change_deletes_quiz_questions(seeded_session, client):
    """意味を変えた更新では今日の復習の問題が削除されること（不具合3、term以外のフィールド
    の横展開確認）。"""
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck, term="用語", meaning="元の意味")
    _make_card_with_quiz_question(seeded_session, card)

    response = client.patch(
        f"/api/v1/vocab-cards/{card.id}", json={"term": "用語", "meaning": "新しい意味"}
    )

    assert response.status_code == 200, response.text
    assert seeded_session.query(QuizQuestion).count() == 0


def test_update_vocab_card_aliases_change_deletes_quiz_questions(seeded_session, client):
    """別名を変えた更新では今日の復習の問題が削除されること（不具合3、term以外のフィールド
    の横展開確認）。"""
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck, term="用語", meaning="意味", aliases="元の別名")
    _make_card_with_quiz_question(seeded_session, card)

    response = client.patch(
        f"/api/v1/vocab-cards/{card.id}",
        json={"term": "用語", "meaning": "意味", "aliases": "新しい別名"},
    )

    assert response.status_code == 200, response.text
    assert seeded_session.query(QuizQuestion).count() == 0


def test_generate_vocab_deck_quiz_creates_questions(seeded_session, client, monkeypatch):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck, term="SMTP", meaning="メール送信の仕組み")
    stub_quiz_ai(
        monkeypatch,
        (
            "問題: SMTPの役割は？\n"
            "選択肢1: a\n選択肢2: SMTPはメール送信の役割を持つ\n選択肢3: c\n選択肢4: d\n"
            f"正解: 2\n解説: 説明\n出典: #{card.id}"
        ),
    )

    response = client.post(f"/api/v1/vocab-decks/{deck.id}/quiz/generate")

    assert response.status_code == 200, response.text
    assert response.json()["created"] == 1


def test_generate_vocab_deck_quiz_returns_zero_when_use_in_ai_is_false(
    seeded_session, client, monkeypatch
):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal, use_in_ai=False)
    make_card(seeded_session, deck, term="SMTP", meaning="メール送信の仕組み")
    calls = stub_quiz_ai(monkeypatch, "")

    response = client.post(f"/api/v1/vocab-decks/{deck.id}/quiz/generate")

    assert response.status_code == 200, response.text
    assert response.json()["created"] == 0
    assert calls == []


def test_generate_vocab_deck_quiz_unknown_deck_returns_404(client):
    response = client.post("/api/v1/vocab-decks/999999/quiz/generate")
    assert response.status_code == 404


def _finalize_exam_diary(client, goal_id: int, record_date: str, diary_learned: str) -> None:
    client.post(
        f"/api/v1/records/{record_date}/finalize",
        json={
            "study_logs": [],
            "diary_entries": [
                {"goal_id": goal_id, "diary_body": "", "diary_learned": diary_learned}
            ],
            "mood": None,
        },
    )


def test_generate_vocab_term_suggestions_creates_pending_list(seeded_session, client, monkeypatch):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    _finalize_exam_diary(client, goal.id, RECORD_DATE, "TCPを学んだ。")
    stub_quiz_ai(monkeypatch, "TCP")

    response = client.post(
        f"/api/v1/goals/{goal.id}/vocab-suggestions", json={"record_date": RECORD_DATE}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert [s["term"] for s in body["suggestions"]] == ["TCP"]
    assert body["default_deck_id"] == deck.id


def test_generate_vocab_term_suggestions_unknown_goal_returns_404(client):
    response = client.post(
        "/api/v1/goals/999999/vocab-suggestions", json={"record_date": RECORD_DATE}
    )
    assert response.status_code == 404


def test_list_vocab_term_suggestions_unknown_goal_returns_404(client):
    response = client.get(
        "/api/v1/goals/999999/vocab-suggestions", params={"record_date": RECORD_DATE}
    )
    assert response.status_code == 404


def test_list_vocab_term_suggestions_returns_pending_for_the_date(
    seeded_session, client, monkeypatch
):
    goal = make_exam_goal(seeded_session)
    make_deck(seeded_session, goal)
    _finalize_exam_diary(client, goal.id, RECORD_DATE, "TCPを学んだ。")
    stub_quiz_ai(monkeypatch, "TCP")
    client.post(f"/api/v1/goals/{goal.id}/vocab-suggestions", json={"record_date": RECORD_DATE})

    response = client.get(
        f"/api/v1/goals/{goal.id}/vocab-suggestions", params={"record_date": RECORD_DATE}
    )

    assert response.status_code == 200, response.text
    assert [s["term"] for s in response.json()["suggestions"]] == ["TCP"]


def test_accept_vocab_term_suggestion_creates_card(seeded_session, client, monkeypatch):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    _finalize_exam_diary(client, goal.id, RECORD_DATE, "TCPを学んだ。")
    stub_quiz_ai(monkeypatch, "TCP")
    suggestion_id = client.post(
        f"/api/v1/goals/{goal.id}/vocab-suggestions", json={"record_date": RECORD_DATE}
    ).json()["suggestions"][0]["id"]

    response = client.post(
        f"/api/v1/goals/{goal.id}/vocab-suggestions/{suggestion_id}/accept",
        json={"deck_id": deck.id, "term": "TCP", "meaning": "通信の仕組み", "aliases": None},
    )

    assert response.status_code == 200, response.text
    assert response.json()["term"] == "TCP"
    assert seeded_session.query(VocabCard).filter(VocabCard.deck_id == deck.id).count() == 1
    assert (
        client.get(
            f"/api/v1/goals/{goal.id}/vocab-suggestions", params={"record_date": RECORD_DATE}
        ).json()["suggestions"]
        == []
    )


def test_accept_vocab_term_suggestion_unknown_id_returns_404(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal)

    response = client.post(
        f"/api/v1/goals/{goal.id}/vocab-suggestions/999999/accept",
        json={"deck_id": deck.id, "term": "x", "meaning": "y", "aliases": None},
    )

    assert response.status_code == 404


def test_accept_vocab_term_suggestion_rejects_other_goals_deck(
    seeded_session, client, monkeypatch
):
    """他の目標の単語帳を追加先に指定できないこと（goal_idの不一致を拒否、開発Todo §0.8 D-U）。"""
    goal = make_exam_goal(seeded_session)
    other_goal = make_exam_goal(seeded_session, name="別の資格目標")
    other_deck = make_deck(seeded_session, other_goal)
    _finalize_exam_diary(client, goal.id, RECORD_DATE, "TCPを学んだ。")
    stub_quiz_ai(monkeypatch, "TCP")
    suggestion_id = client.post(
        f"/api/v1/goals/{goal.id}/vocab-suggestions", json={"record_date": RECORD_DATE}
    ).json()["suggestions"][0]["id"]

    response = client.post(
        f"/api/v1/goals/{goal.id}/vocab-suggestions/{suggestion_id}/accept",
        json={"deck_id": other_deck.id, "term": "TCP", "meaning": "y", "aliases": None},
    )

    assert response.status_code == 404


def test_accept_vocab_term_suggestion_rejects_other_goals_suggestion(
    seeded_session, client, monkeypatch
):
    """他の目標の提案IDを操作できないこと（goal_idの不一致を拒否）。"""
    goal = make_exam_goal(seeded_session)
    other_goal = make_exam_goal(seeded_session, name="別の資格目標")
    other_deck = make_deck(seeded_session, other_goal)
    _finalize_exam_diary(client, goal.id, RECORD_DATE, "TCPを学んだ。")
    stub_quiz_ai(monkeypatch, "TCP")
    suggestion_id = client.post(
        f"/api/v1/goals/{goal.id}/vocab-suggestions", json={"record_date": RECORD_DATE}
    ).json()["suggestions"][0]["id"]

    response = client.post(
        f"/api/v1/goals/{other_goal.id}/vocab-suggestions/{suggestion_id}/accept",
        json={"deck_id": other_deck.id, "term": "TCP", "meaning": "y", "aliases": None},
    )

    assert response.status_code == 404


def test_dismiss_vocab_term_suggestion_marks_dismissed(seeded_session, client, monkeypatch):
    goal = make_exam_goal(seeded_session)
    make_deck(seeded_session, goal)
    _finalize_exam_diary(client, goal.id, RECORD_DATE, "TCPを学んだ。")
    stub_quiz_ai(monkeypatch, "TCP")
    suggestion_id = client.post(
        f"/api/v1/goals/{goal.id}/vocab-suggestions", json={"record_date": RECORD_DATE}
    ).json()["suggestions"][0]["id"]

    response = client.post(
        f"/api/v1/goals/{goal.id}/vocab-suggestions/{suggestion_id}/dismiss"
    )

    assert response.status_code == 200, response.text
    assert (
        client.get(
            f"/api/v1/goals/{goal.id}/vocab-suggestions", params={"record_date": RECORD_DATE}
        ).json()["suggestions"]
        == []
    )


def test_dismiss_vocab_term_suggestion_rejects_other_goals_suggestion(
    seeded_session, client, monkeypatch
):
    goal = make_exam_goal(seeded_session)
    other_goal = make_exam_goal(seeded_session, name="別の資格目標")
    make_deck(seeded_session, goal)
    _finalize_exam_diary(client, goal.id, RECORD_DATE, "TCPを学んだ。")
    stub_quiz_ai(monkeypatch, "TCP")
    suggestion_id = client.post(
        f"/api/v1/goals/{goal.id}/vocab-suggestions", json={"record_date": RECORD_DATE}
    ).json()["suggestions"][0]["id"]

    response = client.post(
        f"/api/v1/goals/{other_goal.id}/vocab-suggestions/{suggestion_id}/dismiss"
    )

    assert response.status_code == 404
