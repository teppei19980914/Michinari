"""閲覧API（ガント・単語帳・問題一覧）の統合テスト（開発Todo_Web公開_v1.0 単位2）。

認可境界（IDOR）・公開停止後の挙動・情報漏洩チェック（D-07）を中心に検証する。
"""

from tests.publish_helpers import (
    bearer_header,
    create_and_login,
    gantt_payload,
    issue_api_token,
    publish_full_set,
    vocab_payload,
)

# ---- 正常系 ------------------------------------------------------------------


def test_view_goals_and_gantt_detail_round_trips_uploaded_content(client):
    csrf = create_and_login(client, "alice")
    token = issue_api_token(client, csrf)
    client.put("/api/v1/publish/gantt/1", json=gantt_payload("資格A"), headers=bearer_header(token))

    goals = client.get("/api/v1/view/goals").json()
    assert len(goals) == 1
    assert goals[0]["goal_name"] == "資格A"

    detail = client.get(f"/api/v1/view/gantt/{goals[0]['id']}").json()
    assert detail["local_goal_id"] == 1
    assert detail["items"][0]["title"] == "第1章"
    assert detail["columns"][0]["name"] == "メモ"
    assert detail["cells"][0]["value"] == "進捗良好"


def test_view_vocab_decks_and_detail_round_trips_uploaded_content(client):
    csrf = create_and_login(client, "bob")
    token = issue_api_token(client, csrf)
    client.put(
        "/api/v1/publish/vocab/1", json=vocab_payload("英単語"), headers=bearer_header(token)
    )

    decks = client.get("/api/v1/view/vocab-decks").json()
    assert len(decks) == 1
    assert decks[0]["deck_name"] == "英単語"
    assert decks[0]["card_count"] == 1

    detail = client.get(f"/api/v1/view/vocab/{decks[0]['id']}").json()
    assert detail["cards"][0]["term"] == "apple"


def test_view_quiz_list_round_trips_uploaded_questions(client):
    csrf = create_and_login(client, "carol")
    token = issue_api_token(client, csrf)
    publish_full_set(client, token)
    deck_id = client.get("/api/v1/view/vocab-decks").json()[0]["id"]

    questions = client.get(f"/api/v1/view/vocab/{deck_id}/quiz").json()

    assert len(questions) == 1
    assert questions[0]["question_text"] == "appleの意味は？"
    assert questions[0]["choice_1"] == "りんご"


# ---- 情報漏洩チェック（D-07必須） --------------------------------------------


def test_quiz_list_does_not_leak_correct_choice_index_or_explanation(client):
    csrf = create_and_login(client, "dave")
    token = issue_api_token(client, csrf)
    publish_full_set(client, token)
    deck_id = client.get("/api/v1/view/vocab-decks").json()[0]["id"]

    questions = client.get(f"/api/v1/view/vocab/{deck_id}/quiz").json()

    assert "correct_choice_index" not in questions[0]
    assert "explanation" not in questions[0]


# ---- 認可境界（D-21、IDOR） ---------------------------------------------------


def test_viewing_other_accounts_gantt_snapshot_is_rejected(client):
    csrf_a = create_and_login(client, "erin")
    token_a = issue_api_token(client, csrf_a)
    client.put("/api/v1/publish/gantt/1", json=gantt_payload(), headers=bearer_header(token_a))
    snapshot_id = client.get("/api/v1/view/goals").json()[0]["id"]

    create_and_login(client, "frank")

    response = client.get(f"/api/v1/view/gantt/{snapshot_id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_viewing_other_accounts_vocab_deck_is_rejected(client):
    csrf_a = create_and_login(client, "grace")
    token_a = issue_api_token(client, csrf_a)
    client.put("/api/v1/publish/vocab/1", json=vocab_payload(), headers=bearer_header(token_a))
    deck_id = client.get("/api/v1/view/vocab-decks").json()[0]["id"]

    create_and_login(client, "heidi")

    response = client.get(f"/api/v1/view/vocab/{deck_id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_viewing_other_accounts_quiz_list_is_rejected(client):
    csrf_a = create_and_login(client, "ivan")
    token_a = issue_api_token(client, csrf_a)
    publish_full_set(client, token_a)
    deck_id = client.get("/api/v1/view/vocab-decks").json()[0]["id"]

    create_and_login(client, "judy")

    response = client.get(f"/api/v1/view/vocab/{deck_id}/quiz")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# ---- 公開停止後の挙動 ---------------------------------------------------------


def test_after_unpublish_gantt_view_returns_404(client):
    csrf = create_and_login(client, "karl")
    token = issue_api_token(client, csrf)
    client.put("/api/v1/publish/gantt/1", json=gantt_payload(), headers=bearer_header(token))
    snapshot_id = client.get("/api/v1/view/goals").json()[0]["id"]
    client.delete("/api/v1/publish/gantt/1", headers=bearer_header(token))

    response = client.get(f"/api/v1/view/gantt/{snapshot_id}")

    assert response.status_code == 404


def test_after_unpublish_vocab_view_returns_404(client):
    csrf = create_and_login(client, "leo")
    token = issue_api_token(client, csrf)
    client.put("/api/v1/publish/vocab/1", json=vocab_payload(), headers=bearer_header(token))
    deck_id = client.get("/api/v1/view/vocab-decks").json()[0]["id"]
    client.delete("/api/v1/publish/vocab/1", headers=bearer_header(token))

    response = client.get(f"/api/v1/view/vocab/{deck_id}")

    assert response.status_code == 404


# ---- 認証突破試行 -------------------------------------------------------------


def test_viewing_goals_without_session_is_rejected(client):
    response = client.get("/api/v1/view/goals")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_REQUIRED"


def test_viewing_vocab_decks_without_session_is_rejected(client):
    response = client.get("/api/v1/view/vocab-decks")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_REQUIRED"
