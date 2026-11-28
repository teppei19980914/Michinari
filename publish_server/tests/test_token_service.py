"""app/services/token_service.py のテスト（D-19・D-21）。"""

import pytest

from app.models.account import PublishAccount
from app.services import token_service
from app.services.exceptions import TokenNotFoundError
from app.services.token_hashing import hash_token


@pytest.fixture
def account(db_session) -> PublishAccount:
    acc = PublishAccount(username="token_user", password_hash="x")
    db_session.add(acc)
    db_session.commit()
    return acc


@pytest.fixture
def other_account(db_session) -> PublishAccount:
    acc = PublishAccount(username="other_user", password_hash="x")
    db_session.add(acc)
    db_session.commit()
    return acc


def test_issue_token_returns_plaintext_once_and_stores_only_hash(db_session, account):
    raw_token, token = token_service.issue_token(db_session, account)

    assert raw_token != token.token_hash
    assert token.token_hash == hash_token(raw_token)
    assert token.revoked_at is None


def test_list_tokens_orders_newest_first(db_session, account):
    _, first = token_service.issue_token(db_session, account)
    _, second = token_service.issue_token(db_session, account)

    tokens = token_service.list_tokens(db_session, account)

    assert [t.id for t in tokens] == [second.id, first.id]


def test_list_tokens_excludes_other_accounts(db_session, account, other_account):
    token_service.issue_token(db_session, other_account)

    assert token_service.list_tokens(db_session, account) == []


def test_revoke_token_sets_revoked_at(db_session, account):
    _, token = token_service.issue_token(db_session, account)

    token_service.revoke_token(db_session, account, token.id)

    db_session.refresh(token)
    assert token.revoked_at is not None


def test_revoke_token_is_idempotent(db_session, account):
    _, token = token_service.issue_token(db_session, account)
    token_service.revoke_token(db_session, account, token.id)
    first_revoked_at = token.revoked_at

    token_service.revoke_token(db_session, account, token.id)

    assert token.revoked_at == first_revoked_at


def test_revoke_token_rejects_other_accounts_token(db_session, account, other_account):
    _, token = token_service.issue_token(db_session, other_account)

    with pytest.raises(TokenNotFoundError):
        token_service.revoke_token(db_session, account, token.id)


def test_revoke_token_rejects_unknown_id(db_session, account):
    with pytest.raises(TokenNotFoundError):
        token_service.revoke_token(db_session, account, 999999)


def test_verify_token_returns_account_and_updates_last_used(db_session, account):
    raw_token, _ = token_service.issue_token(db_session, account)

    verified = token_service.verify_token(db_session, raw_token)

    assert verified is not None
    assert verified.id == account.id


def test_verify_token_returns_none_for_unknown_token(db_session):
    assert token_service.verify_token(db_session, "never-issued-token") is None


def test_verify_token_returns_none_for_revoked_token(db_session, account):
    raw_token, token = token_service.issue_token(db_session, account)
    token_service.revoke_token(db_session, account, token.id)

    assert token_service.verify_token(db_session, raw_token) is None
