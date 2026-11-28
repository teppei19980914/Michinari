"""認証APIの統合テスト（開発Todo_Web公開_v1.0 単位1 テスト観点）。

正常系・異常系・認可境界・不正入力・認証突破試行を一通り検証する。
"""

from app.constants.security import CSRF_HEADER_NAME, SESSION_COOKIE_NAME


def _create_and_login(client, username: str, password: str = "correct-horse-battery") -> str:
    create_response = client.post(
        "/api/v1/auth/account", json={"username": username, "password": password}
    )
    assert create_response.status_code == 201, create_response.text

    login_response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert login_response.status_code == 200, login_response.text
    return login_response.json()["csrf_token"]


# ---- 正常系 ----------------------------------------------------------------


def test_create_account_returns_201_without_leaking_password_hash(client):
    response = client.post(
        "/api/v1/auth/account", json={"username": "alice", "password": "correct-horse-battery"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "alice"
    assert "password" not in body
    assert "password_hash" not in body


def test_login_sets_secure_httponly_samesite_cookie_and_returns_csrf(client):
    client.post(
        "/api/v1/auth/account", json={"username": "bob", "password": "correct-horse-battery"}
    )

    response = client.post(
        "/api/v1/auth/login", json={"username": "bob", "password": "correct-horse-battery"}
    )

    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert SESSION_COOKIE_NAME in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "secure" in set_cookie.lower()
    assert "samesite=strict" in set_cookie.lower()
    body = response.json()
    assert body["account"]["username"] == "bob"
    assert len(body["csrf_token"]) > 10


def test_health_check_returns_200(client):
    assert client.get("/health").status_code == 200


def test_full_account_lifecycle(client):
    csrf_token = _create_and_login(client, "carol")

    issue_response = client.post("/api/v1/auth/tokens", headers={CSRF_HEADER_NAME: csrf_token})
    assert issue_response.status_code == 201
    token_value = issue_response.json()["token"]
    assert len(token_value) > 10

    list_response = client.get("/api/v1/auth/tokens")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    logout_response = client.post("/api/v1/auth/logout", headers={CSRF_HEADER_NAME: csrf_token})
    assert logout_response.status_code == 204

    after_logout = client.get("/api/v1/auth/tokens")
    assert after_logout.status_code == 401
    assert after_logout.json()["error"]["code"] == "SESSION_REQUIRED"


# ---- 異常系 ----------------------------------------------------------------


def test_create_account_rejects_duplicate_username(client):
    client.post(
        "/api/v1/auth/account", json={"username": "dave", "password": "correct-horse-battery"}
    )

    response = client.post(
        "/api/v1/auth/account", json={"username": "dave", "password": "another-password-1"}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "USERNAME_ALREADY_EXISTS"


def test_login_unknown_user_returns_generic_invalid_credentials(client):
    response = client.post(
        "/api/v1/auth/login", json={"username": "no-such-user", "password": "whatever-password"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_wrong_password_returns_same_generic_code_as_unknown_user(client):
    client.post(
        "/api/v1/auth/account", json={"username": "erin", "password": "correct-horse-battery"}
    )

    response = client.post(
        "/api/v1/auth/login", json={"username": "erin", "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


# ---- 認可境界（D-21） --------------------------------------------------------


def test_token_list_does_not_leak_other_accounts_tokens(client):
    csrf_a = _create_and_login(client, "frank")
    client.post("/api/v1/auth/tokens", headers={CSRF_HEADER_NAME: csrf_a})

    csrf_b = _create_and_login(client, "grace")

    response = client.get("/api/v1/auth/tokens")
    assert response.status_code == 200
    assert response.json() == []
    # csrf_bが未使用警告にならないことの確認（ログイン切り替え自体が境界検証の前提）。
    assert csrf_b


def test_revoke_token_rejects_other_accounts_token(client):
    csrf_a = _create_and_login(client, "heidi")
    token_id = client.post("/api/v1/auth/tokens", headers={CSRF_HEADER_NAME: csrf_a}).json()["id"]

    csrf_b = _create_and_login(client, "ivan")

    response = client.delete(f"/api/v1/auth/tokens/{token_id}", headers={CSRF_HEADER_NAME: csrf_b})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# ---- 不正入力 ---------------------------------------------------------------


def test_username_with_sqli_payload_is_rejected_by_charset_validation(client):
    response = client.post(
        "/api/v1/auth/account",
        json={"username": "x'; DROP TABLE publish_account; --", "password": "correct-horse-1"},
    )

    assert response.status_code == 400


def test_password_with_xss_payload_is_stored_as_plain_text_not_executed(client):
    xss_payload_value = "<script>alert('xss')</script>"
    response = client.post(
        "/api/v1/auth/account", json={"username": "judy", "password": xss_payload_value}
    )
    assert response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login", json={"username": "judy", "password": xss_payload_value}
    )
    assert login_response.status_code == 200


def test_oversized_username_is_rejected(client):
    response = client.post(
        "/api/v1/auth/account", json={"username": "a" * 1000, "password": "correct-horse-1"}
    )
    assert response.status_code == 400


def test_oversized_password_is_rejected(client):
    response = client.post(
        "/api/v1/auth/account", json={"username": "karl", "password": "a" * 10000}
    )
    assert response.status_code == 400


# ---- 認証突破試行 -----------------------------------------------------------


def test_login_lockout_after_max_attempts_rejects_even_correct_password_with_same_code(
    client, monkeypatch
):
    """ロック中は、正しいパスワードでも「不在ユーザー」と同じ401/INVALID_CREDENTIALSで
    拒否する（専用のACCOUNT_LOCKEDコードは使わない。理由はtest_account_service.pyの
    同種テストのdocstring参照、auth-reviewerレビュー2026-11-28 CRITICAL指摘）。
    """
    monkeypatch.setenv("PUBLISH_LOGIN_MAX_ATTEMPTS", "2")
    client.post(
        "/api/v1/auth/account", json={"username": "leo", "password": "correct-horse-battery"}
    )

    for _ in range(2):
        response = client.post(
            "/api/v1/auth/login", json={"username": "leo", "password": "wrong-password"}
        )
        assert response.status_code == 401

    locked_response = client.post(
        "/api/v1/auth/login", json={"username": "leo", "password": "correct-horse-battery"}
    )
    assert locked_response.status_code == 401
    assert locked_response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_succeeds_via_api_after_lock_naturally_expires(client, monkeypatch):
    """ロック解除後は、同じAPI経由で正しいパスワードのログインがCookie発行まで含めて
    成功すること（サービス層のみでなくAPI層でも確認、test-coverage-reviewerレビュー
    2026-11-28 LOW指摘）。"""
    monkeypatch.setenv("PUBLISH_LOGIN_MAX_ATTEMPTS", "1")
    client.post(
        "/api/v1/auth/account", json={"username": "nina", "password": "correct-horse-battery"}
    )
    locked_response = client.post(
        "/api/v1/auth/login", json={"username": "nina", "password": "wrong-password"}
    )
    assert locked_response.status_code == 401

    from datetime import timedelta

    from app.database import session_scope
    from app.models.account import PublishAccount
    from app.models.base import utcnow

    with session_scope() as session:
        account = session.query(PublishAccount).filter_by(username="nina").first()
        account.locked_until = utcnow() - timedelta(seconds=1)

    response = client.post(
        "/api/v1/auth/login", json={"username": "nina", "password": "correct-horse-battery"}
    )
    assert response.status_code == 200
    assert "csrf_token" in response.json()


def test_logout_without_session_cookie_is_rejected(client):
    response = client.post("/api/v1/auth/logout", headers={CSRF_HEADER_NAME: "whatever-value"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_REQUIRED"


def test_logout_without_csrf_header_is_rejected(client):
    _create_and_login(client, "mia")

    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"


def test_issue_token_with_wrong_csrf_value_is_rejected(client):
    _create_and_login(client, "nick")

    response = client.post("/api/v1/auth/tokens", headers={CSRF_HEADER_NAME: "wrong-value"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"


def test_revoked_token_cannot_be_verified(client):
    csrf_token = _create_and_login(client, "oscar")
    issued = client.post("/api/v1/auth/tokens", headers={CSRF_HEADER_NAME: csrf_token}).json()

    revoke_response = client.delete(
        f"/api/v1/auth/tokens/{issued['id']}", headers={CSRF_HEADER_NAME: csrf_token}
    )
    assert revoke_response.status_code == 204

    # verify_tokenは単位2のアップロードAPIが使う想定（単位1では未配線）だが、失効が
    # 即時に反映されることはここで直接検証する（D-19「失効後もキャッシュされた
    # トークンで操作継続」STRIDE対策）。
    import app.database as database_module
    from app.services import token_service

    with database_module.session_scope() as session:
        assert token_service.verify_token(session, issued["token"]) is None
