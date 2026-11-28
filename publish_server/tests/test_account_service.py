"""app/services/account_service.py のテスト（D-16・D-17、STRIDE分析5章）。"""

from datetime import timedelta

import pytest
from argon2 import PasswordHasher

from app.models.account import PublishAccount
from app.models.base import utcnow
from app.services import account_service
from app.services.exceptions import (
    InvalidCredentialsError,
    UsernameAlreadyExistsError,
    ValidationError,
)


def test_validate_username_accepts_allowed_pattern():
    account_service.validate_username("user_name-1.2")


@pytest.mark.parametrize(
    "username",
    ["ab", "a" * 65, "invalid user", "ユーザー名", "user;drop table"],
)
def test_validate_username_rejects_invalid_values(username):
    with pytest.raises(ValidationError):
        account_service.validate_username(username)


@pytest.mark.parametrize("password", ["short", "a" * 257])
def test_validate_password_rejects_invalid_length(password):
    with pytest.raises(ValidationError):
        account_service.validate_password(password)


def test_create_account_hashes_password(db_session):
    account = account_service.create_account(db_session, "alice", "correct-horse-battery")
    assert account.id is not None
    assert account.password_hash != "correct-horse-battery"
    assert account.password_hash.startswith("$argon2id$")


def test_create_account_rejects_duplicate_username(db_session):
    account_service.create_account(db_session, "bob", "correct-horse-battery")
    with pytest.raises(UsernameAlreadyExistsError):
        account_service.create_account(db_session, "bob", "another-password-1")


def test_authenticate_success_resets_failure_count(db_session):
    account_service.create_account(db_session, "carol", "correct-horse-battery")
    account = db_session.query(PublishAccount).filter_by(username="carol").first()
    account.failed_login_count = 3
    db_session.commit()

    authenticated = account_service.authenticate(db_session, "carol", "correct-horse-battery")

    assert authenticated.username == "carol"
    assert authenticated.failed_login_count == 0


def test_authenticate_unknown_username_raises_invalid_credentials(db_session):
    with pytest.raises(InvalidCredentialsError):
        account_service.authenticate(db_session, "no-such-user", "whatever-password")


def test_authenticate_wrong_password_increments_failure_count(db_session):
    account_service.create_account(db_session, "dave", "correct-horse-battery")

    with pytest.raises(InvalidCredentialsError):
        account_service.authenticate(db_session, "dave", "wrong-password")

    account = db_session.query(PublishAccount).filter_by(username="dave").first()
    assert account.failed_login_count == 1


def test_authenticate_locks_account_and_rejects_even_the_correct_password(db_session, monkeypatch):
    """ロック中は、正しいパスワードでも同じ`InvalidCredentialsError`で拒否する。

    専用のACCOUNT_LOCKEDコードを返さないのは、総当たりで対象ユーザー名の存在有無が
    判別できてしまうため（STRIDE分析5章、auth-reviewerレビュー2026-11-28 CRITICAL指摘）。
    """
    monkeypatch.setenv("PUBLISH_LOGIN_MAX_ATTEMPTS", "2")
    account_service.create_account(db_session, "erin", "correct-horse-battery")

    for _ in range(2):
        with pytest.raises(InvalidCredentialsError):
            account_service.authenticate(db_session, "erin", "wrong-password")

    with pytest.raises(InvalidCredentialsError):
        account_service.authenticate(db_session, "erin", "correct-horse-battery")

    account = db_session.query(PublishAccount).filter_by(username="erin").first()
    assert account.locked_until is not None
    assert account.failed_login_count == 2


def test_authenticate_allows_retry_after_lock_expires(db_session):
    account_service.create_account(db_session, "frank", "correct-horse-battery")
    account = db_session.query(PublishAccount).filter_by(username="frank").first()
    account.failed_login_count = 99
    account.locked_until = utcnow() - timedelta(minutes=1)
    db_session.commit()

    authenticated = account_service.authenticate(db_session, "frank", "correct-horse-battery")
    assert authenticated.username == "frank"


def test_authenticate_resets_failure_count_when_lock_naturally_expires(db_session, monkeypatch):
    """ロック解除直後の1回の失敗で即再ロックされないこと（永続DoS対策、
    auth-reviewerレビュー2026-11-28 HIGH指摘）。

    解除前のカウンタ（上限5）を引き継いだまま1回失敗しただけで再ロックされると、
    15分おきに1回ずつ失敗を送るだけで本人が正しいパスワードでログインできる隙を
    与えずに対象アカウントを恒久的にロックし続けられてしまう。
    """
    monkeypatch.setenv("PUBLISH_LOGIN_MAX_ATTEMPTS", "5")
    account_service.create_account(db_session, "mallory", "correct-horse-battery")
    account = db_session.query(PublishAccount).filter_by(username="mallory").first()
    account.failed_login_count = 5
    account.locked_until = utcnow() - timedelta(seconds=1)
    db_session.commit()

    with pytest.raises(InvalidCredentialsError):
        account_service.authenticate(db_session, "mallory", "wrong-password")

    db_session.refresh(account)
    assert account.failed_login_count == 1
    assert account.locked_until is None

    # まだロックされていないため、正しいパスワードなら成功する。
    authenticated = account_service.authenticate(db_session, "mallory", "correct-horse-battery")
    assert authenticated.username == "mallory"


def test_authenticate_succeeds_across_different_unicode_normalization_forms(db_session):
    """NFC/NFDなど異なる正規化形式でも同一パスワードとして扱う
    （開発Todo_Web公開_v1.0 単位1テスト観点「Unicode正規化」、test-coverage-reviewerレビュー
    2026-11-28 HIGH指摘で追加）。

    「é」はNFCでは単一コードポイント(U+00E9)、NFDでは「e」(U+0065)+結合アクセント
    (U+0301)の2コードポイントになる。見た目・意味は同じパスワードである。
    """
    import unicodedata

    nfc_password = unicodedata.normalize("NFC", "café-horse-battery")
    nfd_password = unicodedata.normalize("NFD", "café-horse-battery")
    assert nfc_password != nfd_password  # 前提：実際に異なるバイト列であることの確認

    account_service.create_account(db_session, "nabil", nfc_password)

    authenticated = account_service.authenticate(db_session, "nabil", nfd_password)
    assert authenticated.username == "nabil"


def test_create_account_with_nfd_password_then_login_with_nfc_password(db_session):
    """逆方向（NFDで作成→NFCでログイン）も同一パスワードとして扱う。"""
    import unicodedata

    nfc_password = unicodedata.normalize("NFC", "café-horse-battery")
    nfd_password = unicodedata.normalize("NFD", "café-horse-battery")

    account_service.create_account(db_session, "olga", nfd_password)

    authenticated = account_service.authenticate(db_session, "olga", nfc_password)
    assert authenticated.username == "olga"


def test_authenticate_rehashes_outdated_hash(db_session):
    weak_hasher = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    account = PublishAccount(
        username="grace", password_hash=weak_hasher.hash("correct-horse-battery")
    )
    db_session.add(account)
    db_session.commit()
    old_hash = account.password_hash

    account_service.authenticate(db_session, "grace", "correct-horse-battery")

    db_session.refresh(account)
    assert account.password_hash != old_hash
    assert account.password_hash.startswith("$argon2id$")
