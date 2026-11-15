"""単語帳APIのテスト（開発Todo_単語帳_v1.0 要件A）。"""

from app.constants.app_setting_keys import VOCAB_IMPORT_MAX_ROWS
from app.constants.enums import VocabQuizMode
from app.services import vocab_service
from tests.diary_helpers import make_exam_goal
from tests.vocab_helpers import make_card, make_deck, make_reading_goal, set_setting

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


def test_get_vocab_deck_returns_deck(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    deck = make_deck(seeded_session, goal, "単語帳")

    response = client.get(f"/api/v1/vocab-decks/{deck.id}")

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "単語帳"


def test_get_vocab_deck_unknown_id_returns_404(client):
    response = client.get("/api/v1/vocab-decks/999999")
    assert response.status_code == 404


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
