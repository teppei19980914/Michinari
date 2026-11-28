"""app/services/session_service.py のテスト（D-18）。"""

from datetime import timedelta

import pytest

from app.models.account import PublishAccount
from app.models.base import utcnow
from app.models.session import PublishSession
from app.services import session_service
from app.services.exceptions import SessionRequiredError


@pytest.fixture
def account(db_session) -> PublishAccount:
    acc = PublishAccount(username="session_user", password_hash="x")
    db_session.add(acc)
    db_session.commit()
    return acc


def test_create_session_returns_distinct_raw_token_and_csrf_token(db_session, account):
    issued = session_service.create_session(db_session, account)
    assert issued.raw_token != issued.csrf_token
    assert len(issued.raw_token) > 20

    row = db_session.get(PublishSession, session_service._hash_token(issued.raw_token))
    assert row is not None
    assert row.account_id == account.id
    assert row.csrf_token == issued.csrf_token


def test_get_valid_session_returns_row_and_updates_last_seen(db_session, account):
    issued = session_service.create_session(db_session, account)

    row = session_service.get_valid_session(db_session, issued.raw_token)

    assert row.account_id == account.id
    assert row.last_seen_at is not None


def test_get_valid_session_rejects_unknown_token(db_session):
    with pytest.raises(SessionRequiredError):
        session_service.get_valid_session(db_session, "unknown-token-value")


def test_get_valid_session_rejects_expired_session(db_session, account):
    issued = session_service.create_session(db_session, account)
    row = db_session.get(PublishSession, session_service._hash_token(issued.raw_token))
    row.expires_at = utcnow() - timedelta(seconds=1)
    db_session.commit()

    with pytest.raises(SessionRequiredError):
        session_service.get_valid_session(db_session, issued.raw_token)


def test_delete_session_removes_row(db_session, account):
    issued = session_service.create_session(db_session, account)

    session_service.delete_session(db_session, issued.raw_token)

    assert db_session.get(PublishSession, session_service._hash_token(issued.raw_token)) is None


def test_delete_session_is_idempotent_for_unknown_token(db_session):
    session_service.delete_session(db_session, "never-existed-token")
