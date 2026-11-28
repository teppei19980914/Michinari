"""公開API（アップロード・差し替え・公開停止）の統合テスト（開発Todo_Web公開_v1.0 単位2）。

正常系・異常系・不正入力・認証突破試行を一通り検証する。認可境界（IDOR）・情報漏洩
チェック（D-07）はtest_view_api.py・test_quiz_answer_api.pyで検証する（閲覧・回答側の
確認観点のため）。
"""

from app.constants.security import CSRF_HEADER_NAME
from tests.publish_helpers import (
    bearer_header,
    create_and_login,
    gantt_payload,
    issue_api_token,
    quiz_payload,
    vocab_payload,
)

# ---- 正常系 ------------------------------------------------------------------


def test_upload_gantt_then_replace_upserts_same_snapshot(client):
    csrf = create_and_login(client, "alice")
    token = issue_api_token(client, csrf)
    headers = bearer_header(token)

    first = client.put("/api/v1/publish/gantt/1", json=gantt_payload("資格A"), headers=headers)
    assert first.status_code == 204

    goals_after_first = client.get("/api/v1/view/goals").json()
    assert len(goals_after_first) == 1
    snapshot_id = goals_after_first[0]["id"]

    second = client.put(
        "/api/v1/publish/gantt/1", json=gantt_payload("資格A改訂版"), headers=headers
    )
    assert second.status_code == 204

    goals_after_second = client.get("/api/v1/view/goals").json()
    assert len(goals_after_second) == 1
    assert goals_after_second[0]["id"] == snapshot_id
    assert goals_after_second[0]["goal_name"] == "資格A改訂版"


def test_upload_vocab_then_replace_upserts_same_deck(client):
    csrf = create_and_login(client, "bob")
    token = issue_api_token(client, csrf)
    headers = bearer_header(token)

    client.put("/api/v1/publish/vocab/1", json=vocab_payload("英単語"), headers=headers)
    deck_id = client.get("/api/v1/view/vocab-decks").json()[0]["id"]

    client.put("/api/v1/publish/vocab/1", json=vocab_payload("英単語改訂版"), headers=headers)
    decks_after = client.get("/api/v1/view/vocab-decks").json()
    assert len(decks_after) == 1
    assert decks_after[0]["id"] == deck_id
    assert decks_after[0]["deck_name"] == "英単語改訂版"


def test_upload_quiz_requires_existing_vocab_deck_then_succeeds(client):
    csrf = create_and_login(client, "carol")
    token = issue_api_token(client, csrf)
    headers = bearer_header(token)

    client.put("/api/v1/publish/vocab/1", json=vocab_payload(), headers=headers)
    response = client.put("/api/v1/publish/quiz/1", json=quiz_payload(), headers=headers)

    assert response.status_code == 204


def test_delete_gantt_removes_snapshot(client):
    csrf = create_and_login(client, "dave")
    token = issue_api_token(client, csrf)
    headers = bearer_header(token)
    client.put("/api/v1/publish/gantt/1", json=gantt_payload(), headers=headers)

    response = client.delete("/api/v1/publish/gantt/1", headers=headers)

    assert response.status_code == 204
    assert client.get("/api/v1/view/goals").json() == []


def test_delete_vocab_removes_deck_and_cascades_quiz(client):
    csrf = create_and_login(client, "erin")
    token = issue_api_token(client, csrf)
    headers = bearer_header(token)
    client.put("/api/v1/publish/vocab/1", json=vocab_payload(), headers=headers)
    client.put("/api/v1/publish/quiz/1", json=quiz_payload(), headers=headers)

    response = client.delete("/api/v1/publish/vocab/1", headers=headers)

    assert response.status_code == 204
    assert client.get("/api/v1/view/vocab-decks").json() == []


def test_delete_quiz_only_keeps_vocab_deck(client):
    csrf = create_and_login(client, "frank")
    token = issue_api_token(client, csrf)
    headers = bearer_header(token)
    client.put("/api/v1/publish/vocab/1", json=vocab_payload(), headers=headers)
    client.put("/api/v1/publish/quiz/1", json=quiz_payload(), headers=headers)
    deck_id = client.get("/api/v1/view/vocab-decks").json()[0]["id"]

    response = client.delete("/api/v1/publish/quiz/1", headers=headers)

    assert response.status_code == 204
    assert client.get("/api/v1/view/vocab-decks").json()[0]["id"] == deck_id
    assert client.get(f"/api/v1/view/vocab/{deck_id}/quiz").json() == []


def test_unpublish_nonexistent_items_is_idempotent(client):
    csrf = create_and_login(client, "grace")
    token = issue_api_token(client, csrf)
    headers = bearer_header(token)

    assert client.delete("/api/v1/publish/gantt/999", headers=headers).status_code == 204
    assert client.delete("/api/v1/publish/vocab/999", headers=headers).status_code == 204
    assert client.delete("/api/v1/publish/quiz/999", headers=headers).status_code == 204


# ---- 異常系（D-20：サイズ・件数・文字数上限） ---------------------------------


def test_upload_gantt_exceeding_snapshot_size_limit_is_rejected(client, monkeypatch):
    csrf = create_and_login(client, "heidi")
    token = issue_api_token(client, csrf)
    headers = bearer_header(token)
    payload = gantt_payload()
    # ASCII文字で正確なバイト数を制御する（日本語はUTF-8で1文字3バイトのため、サイズの
    # 境界判定とボディサイズ防御ミドルウェア（×2倍の閾値）の両方を正確に切り分けるため）。
    payload["items"][0]["description"] = "a" * 1999

    monkeypatch.setenv("PUBLISH_MAX_SNAPSHOT_BYTES", "2000")
    response = client.put("/api/v1/publish/gantt/1", json=payload, headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "SNAPSHOT_TOO_LARGE"


def test_upload_vocab_exceeding_card_count_limit_is_rejected(client, monkeypatch):
    csrf = create_and_login(client, "ivan")
    token = issue_api_token(client, csrf)
    headers = bearer_header(token)
    payload = vocab_payload()
    payload["cards"].append(dict(payload["cards"][0], local_card_id=2))

    monkeypatch.setenv("PUBLISH_MAX_VOCAB_CARDS", "1")
    response = client.put("/api/v1/publish/vocab/1", json=payload, headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "TOO_MANY_ITEMS"


def test_upload_quiz_exceeding_question_count_limit_is_rejected(client, monkeypatch):
    csrf = create_and_login(client, "judy")
    token = issue_api_token(client, csrf)
    headers = bearer_header(token)
    client.put("/api/v1/publish/vocab/1", json=vocab_payload(), headers=headers)
    payload = quiz_payload()
    payload["questions"].append(dict(payload["questions"][0], local_question_id=2))

    monkeypatch.setenv("PUBLISH_MAX_QUIZ_QUESTIONS", "1")
    response = client.put("/api/v1/publish/quiz/1", json=payload, headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "TOO_MANY_ITEMS"


def test_upload_field_exceeding_char_limit_is_rejected(client):
    csrf = create_and_login(client, "karl")
    token = issue_api_token(client, csrf)
    headers = bearer_header(token)
    payload = gantt_payload()
    payload["items"][0]["title"] = "a" * 2001

    response = client.put("/api/v1/publish/gantt/1", json=payload, headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_upload_quiz_without_published_vocab_deck_is_rejected(client):
    csrf = create_and_login(client, "leo")
    token = issue_api_token(client, csrf)
    headers = bearer_header(token)

    response = client.put("/api/v1/publish/quiz/1", json=quiz_payload(), headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VOCAB_DECK_NOT_PUBLISHED"


def test_upload_quiz_with_local_card_id_not_in_published_deck_is_rejected(client):
    """D-03・STRIDE分析5章「サーバ側でも二重検証（`vocab_card_id`必須チェック）」：
    テーマ由来等、単語帳由来以外の問題が混入した場合（`local_card_id`がデッキのカード一覧に
    存在しない）はサーバ側で拒否する。"""
    csrf = create_and_login(client, "quinn")
    token = issue_api_token(client, csrf)
    headers = bearer_header(token)
    client.put("/api/v1/publish/vocab/1", json=vocab_payload(), headers=headers)
    payload = quiz_payload(local_card_id=999)

    response = client.put("/api/v1/publish/quiz/1", json=payload, headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "QUESTION_NOT_FROM_VOCAB_CARD"


def test_upload_quiz_partially_invalid_source_rejects_entire_batch_without_touching_existing(
    client,
):
    """1件でも出所不明の問題が混ざっていれば全体を拒否し、既存の公開済み問題も
    削除・差し替えされず残ることを確認する（検証が削除処理より前に行われるため）。"""
    csrf = create_and_login(client, "quinn2")
    token = issue_api_token(client, csrf)
    headers = bearer_header(token)
    client.put("/api/v1/publish/vocab/1", json=vocab_payload(), headers=headers)
    client.put("/api/v1/publish/quiz/1", json=quiz_payload(), headers=headers)
    deck_id = client.get("/api/v1/view/vocab-decks").json()[0]["id"]
    existing_question_id = client.get(f"/api/v1/view/vocab/{deck_id}/quiz").json()[0]["id"]

    mixed_payload = quiz_payload()
    mixed_payload["questions"].append(
        dict(mixed_payload["questions"][0], local_question_id=2, local_card_id=999)
    )
    response = client.put("/api/v1/publish/quiz/1", json=mixed_payload, headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "QUESTION_NOT_FROM_VOCAB_CARD"
    questions_after = client.get(f"/api/v1/view/vocab/{deck_id}/quiz").json()
    assert len(questions_after) == 1
    assert questions_after[0]["id"] == existing_question_id


# ---- 不正入力 ----------------------------------------------------------------


def test_upload_gantt_with_malformed_json_structure_is_rejected(client):
    csrf = create_and_login(client, "mia")
    token = issue_api_token(client, csrf)
    headers = bearer_header(token)
    broken_payload = {"goal_name": "資格A"}  # items/columns/cellsが欠落

    response = client.put("/api/v1/publish/gantt/1", json=broken_payload, headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_upload_quiz_with_out_of_range_correct_choice_index_is_rejected(client):
    csrf = create_and_login(client, "nick")
    token = issue_api_token(client, csrf)
    headers = bearer_header(token)
    client.put("/api/v1/publish/vocab/1", json=vocab_payload(), headers=headers)
    payload = quiz_payload(correct_choice_index=4)

    response = client.put("/api/v1/publish/quiz/1", json=payload, headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_gantt_title_with_sqli_and_xss_payload_is_stored_as_plain_text(client):
    csrf = create_and_login(client, "oscar")
    token = issue_api_token(client, csrf)
    headers = bearer_header(token)
    payload = gantt_payload()
    payload["items"][0]["title"] = "x'; DROP TABLE published_gantt_snapshot; --"
    payload["items"][0]["description"] = "<script>alert('xss')</script>"

    upload_response = client.put("/api/v1/publish/gantt/1", json=payload, headers=headers)
    assert upload_response.status_code == 204

    snapshot_id = client.get("/api/v1/view/goals").json()[0]["id"]
    detail = client.get(f"/api/v1/view/gantt/{snapshot_id}").json()
    assert detail["items"][0]["title"] == payload["items"][0]["title"]
    assert detail["items"][0]["description"] == payload["items"][0]["description"]


# ---- 認証突破試行 -------------------------------------------------------------


def test_upload_without_authorization_header_is_rejected(client):
    response = client.put("/api/v1/publish/gantt/1", json=gantt_payload())

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "API_TOKEN_INVALID"


def test_upload_with_non_bearer_authorization_header_is_rejected(client):
    response = client.put(
        "/api/v1/publish/gantt/1",
        json=gantt_payload(),
        headers={"Authorization": "Basic dGVzdDp0ZXN0"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "API_TOKEN_INVALID"


def test_upload_with_empty_bearer_token_is_rejected(client):
    response = client.put(
        "/api/v1/publish/gantt/1", json=gantt_payload(), headers={"Authorization": "Bearer    "}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "API_TOKEN_INVALID"


def test_upload_with_unknown_token_is_rejected(client):
    response = client.put(
        "/api/v1/publish/gantt/1",
        json=gantt_payload(),
        headers=bearer_header("not-a-real-token-value"),
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "API_TOKEN_INVALID"


def test_upload_with_revoked_token_is_rejected(client):
    csrf = create_and_login(client, "peggy")
    token = issue_api_token(client, csrf)
    token_id = client.get("/api/v1/auth/tokens").json()[0]["id"]
    client.delete(f"/api/v1/auth/tokens/{token_id}", headers={CSRF_HEADER_NAME: csrf})

    response = client.put(
        "/api/v1/publish/gantt/1", json=gantt_payload(), headers=bearer_header(token)
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "API_TOKEN_INVALID"
