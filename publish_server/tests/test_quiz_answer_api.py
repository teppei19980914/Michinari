"""問題への回答APIの統合テスト（開発Todo_Web公開_v1.0 単位2、D-07・D-08・D-18）。

正誤判定・冪等性・差し替え後の無効化・情報漏洩チェック（D-07）・CSRF・認可境界を検証する。
"""

from app.constants.security import CSRF_HEADER_NAME
from tests.publish_helpers import (
    bearer_header,
    create_and_login,
    issue_api_token,
    publish_full_set,
    quiz_payload,
)


def _published_question_id(client) -> int:
    deck_id = client.get("/api/v1/view/vocab-decks").json()[0]["id"]
    return client.get(f"/api/v1/view/vocab/{deck_id}/quiz").json()[0]["id"]


# ---- 正常系（正誤判定・情報漏洩チェック） -------------------------------------


def test_answering_correctly_returns_is_correct_true_with_explanation(client):
    csrf = create_and_login(client, "alice")
    token = issue_api_token(client, csrf)
    publish_full_set(client, token)  # correct_choice_index=0
    question_id = _published_question_id(client)

    response = client.post(
        f"/api/v1/view/quiz/{question_id}/answer",
        json={"chosen_index": 0, "client_answer_uuid": "uuid-correct-1"},
        headers={CSRF_HEADER_NAME: csrf},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_correct"] is True
    assert body["correct_choice_index"] == 0
    assert body["explanation"] == "appleはりんごです。"


def test_answering_incorrectly_returns_is_correct_false(client):
    csrf = create_and_login(client, "bob")
    token = issue_api_token(client, csrf)
    publish_full_set(client, token)  # correct_choice_index=0
    question_id = _published_question_id(client)

    response = client.post(
        f"/api/v1/view/quiz/{question_id}/answer",
        json={"chosen_index": 1, "client_answer_uuid": "uuid-wrong-1"},
        headers={CSRF_HEADER_NAME: csrf},
    )

    assert response.status_code == 200
    assert response.json()["is_correct"] is False


def test_answering_twice_with_same_client_uuid_is_idempotent(client):
    csrf = create_and_login(client, "carol")
    token = issue_api_token(client, csrf)
    publish_full_set(client, token)
    question_id = _published_question_id(client)
    body = {"chosen_index": 0, "client_answer_uuid": "uuid-retry-1"}

    first = client.post(
        f"/api/v1/view/quiz/{question_id}/answer", json=body, headers={CSRF_HEADER_NAME: csrf}
    )
    second = client.post(
        f"/api/v1/view/quiz/{question_id}/answer", json=body, headers={CSRF_HEADER_NAME: csrf}
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()

    from app.database import session_scope
    from app.models.quiz_answer_record import QuizAnswerRecord

    with session_scope() as session:
        count = (
            session.query(QuizAnswerRecord)
            .filter(QuizAnswerRecord.client_answer_uuid == "uuid-retry-1")
            .count()
        )
    assert count == 1


# ---- 差し替え後に古い版の問題へ回答できないこと -------------------------------


def test_answering_question_invalidated_by_replace_is_rejected(client):
    csrf = create_and_login(client, "dave")
    token = issue_api_token(client, csrf)
    publish_full_set(client, token)
    old_question_id = _published_question_id(client)

    client.put(
        "/api/v1/publish/quiz/1",
        json=quiz_payload(local_question_id=2),
        headers=bearer_header(token),
    )

    response = client.post(
        f"/api/v1/view/quiz/{old_question_id}/answer",
        json={"chosen_index": 0, "client_answer_uuid": "uuid-old-question"},
        headers={CSRF_HEADER_NAME: csrf},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_answering_newly_published_question_after_replace_succeeds(client):
    """差し替えで旧問題IDが無効化される一方、新しい問題には正しく回答できることを確認する
    （test-coverage-reviewerレビュー2026-11-28指摘：旧ID無効化のみでは新IDの動作は未検証）。
    """
    csrf = create_and_login(client, "dave2")
    token = issue_api_token(client, csrf)
    publish_full_set(client, token)

    client.put(
        "/api/v1/publish/quiz/1",
        json=quiz_payload(local_question_id=2, correct_choice_index=1),
        headers=bearer_header(token),
    )
    new_question_id = _published_question_id(client)

    response = client.post(
        f"/api/v1/view/quiz/{new_question_id}/answer",
        json={"chosen_index": 1, "client_answer_uuid": "uuid-new-question"},
        headers={CSRF_HEADER_NAME: csrf},
    )

    assert response.status_code == 200
    assert response.json()["is_correct"] is True


def test_answering_question_after_unpublish_quiz_is_rejected(client):
    csrf = create_and_login(client, "erin")
    token = issue_api_token(client, csrf)
    publish_full_set(client, token)
    question_id = _published_question_id(client)
    client.delete("/api/v1/publish/quiz/1", headers=bearer_header(token))

    response = client.post(
        f"/api/v1/view/quiz/{question_id}/answer",
        json={"chosen_index": 0, "client_answer_uuid": "uuid-after-unpublish"},
        headers={CSRF_HEADER_NAME: csrf},
    )

    assert response.status_code == 404


def test_answering_question_after_unpublish_vocab_cascades_to_quiz_is_rejected(client):
    """単語帳の公開停止が、API経由でも問題へのカスケード削除として伝わることを確認する
    （test-coverage-reviewerレビュー2026-11-28指摘：ORM直接削除のカスケード検証
    〈test_cascade_delete.py〉だけでは、publish_service.delete_vocab_deckの経路を通した
    回帰を検知できない）。
    """
    csrf = create_and_login(client, "erin2")
    token = issue_api_token(client, csrf)
    publish_full_set(client, token)
    question_id = _published_question_id(client)

    client.delete("/api/v1/publish/vocab/1", headers=bearer_header(token))

    response = client.post(
        f"/api/v1/view/quiz/{question_id}/answer",
        json={"chosen_index": 0, "client_answer_uuid": "uuid-after-unpublish-vocab"},
        headers={CSRF_HEADER_NAME: csrf},
    )

    assert response.status_code == 404


# ---- 異常系・不正入力 ---------------------------------------------------------


def test_answering_nonexistent_question_is_rejected(client):
    csrf = create_and_login(client, "frank")

    response = client.post(
        "/api/v1/view/quiz/999999/answer",
        json={"chosen_index": 0, "client_answer_uuid": "uuid-nonexistent"},
        headers={CSRF_HEADER_NAME: csrf},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_answering_with_out_of_range_chosen_index_is_rejected(client):
    csrf = create_and_login(client, "grace")
    token = issue_api_token(client, csrf)
    publish_full_set(client, token)
    question_id = _published_question_id(client)

    response = client.post(
        f"/api/v1/view/quiz/{question_id}/answer",
        json={"chosen_index": 9, "client_answer_uuid": "uuid-out-of-range"},
        headers={CSRF_HEADER_NAME: csrf},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# ---- 認可境界（D-21、IDOR） ---------------------------------------------------


def test_answering_other_accounts_question_is_rejected(client):
    csrf_a = create_and_login(client, "heidi")
    token_a = issue_api_token(client, csrf_a)
    publish_full_set(client, token_a)
    question_id = _published_question_id(client)

    csrf_b = create_and_login(client, "ivan")

    response = client.post(
        f"/api/v1/view/quiz/{question_id}/answer",
        json={"chosen_index": 0, "client_answer_uuid": "uuid-cross-account"},
        headers={CSRF_HEADER_NAME: csrf_b},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_answering_with_client_answer_uuid_already_used_by_other_account_is_rejected(client):
    """`client_answer_uuid`の冪等性チェックはaccount_idも条件に含めるため（auth-reviewer
    レビュー2026-11-28指摘）、他アカウントが先に使った値を新規回答で使うと一意制約違反を
    専用のドメイン例外に変換して拒否する。
    """
    csrf_a = create_and_login(client, "heidi2")
    token_a = issue_api_token(client, csrf_a)
    publish_full_set(client, token_a)
    question_id_a = _published_question_id(client)
    client.post(
        f"/api/v1/view/quiz/{question_id_a}/answer",
        json={"chosen_index": 0, "client_answer_uuid": "uuid-shared-across-accounts"},
        headers={CSRF_HEADER_NAME: csrf_a},
    )

    csrf_b = create_and_login(client, "ivan2")
    token_b = issue_api_token(client, csrf_b)
    publish_full_set(client, token_b)
    question_id_b = _published_question_id(client)

    response = client.post(
        f"/api/v1/view/quiz/{question_id_b}/answer",
        json={"chosen_index": 0, "client_answer_uuid": "uuid-shared-across-accounts"},
        headers={CSRF_HEADER_NAME: csrf_b},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DUPLICATE_CLIENT_ANSWER_UUID"


# ---- 認証突破試行（セッション・CSRF） -----------------------------------------


def test_answering_without_session_is_rejected(client):
    response = client.post(
        "/api/v1/view/quiz/1/answer",
        json={"chosen_index": 0, "client_answer_uuid": "uuid-no-session"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_REQUIRED"


def test_answering_without_csrf_header_is_rejected(client):
    csrf = create_and_login(client, "judy")
    token = issue_api_token(client, csrf)
    publish_full_set(client, token)
    question_id = _published_question_id(client)

    response = client.post(
        f"/api/v1/view/quiz/{question_id}/answer",
        json={"chosen_index": 0, "client_answer_uuid": "uuid-no-csrf"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"
