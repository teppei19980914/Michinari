"""app/services/account_service.py のテスト（D-16・D-17、STRIDE分析5章）。"""

from datetime import timedelta

import pytest
from argon2 import PasswordHasher

from app.models.account import PublishAccount
from app.models.base import utcnow
from app.services import account_service
from app.services.exceptions import (
    AccountLockedError,
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


def test_authenticate_locks_account_after_max_attempts(db_session, monkeypatch):
    monkeypatch.setenv("PUBLISH_LOGIN_MAX_ATTEMPTS", "2")
    account_service.create_account(db_session, "erin", "correct-horse-battery")

    for _ in range(2):
        with pytest.raises(InvalidCredentialsError):
            account_service.authenticate(db_session, "erin", "wrong-password")

    with pytest.raises(AccountLockedError):
        account_service.authenticate(db_session, "erin", "correct-horse-battery")


def test_authenticate_allows_retry_after_lock_expires(db_session):
    account_service.create_account(db_session, "frank", "correct-horse-battery")
    account = db_session.query(PublishAccount).filter_by(username="frank").first()
    account.failed_login_count = 99
    account.locked_until = utcnow() - timedelta(minutes=1)
    db_session.commit()

    authenticated = account_service.authenticate(db_session, "frank", "correct-horse-battery")
    assert authenticated.username == "frank"


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
