"""ai/auth のテスト（ロジック・プロンプト編16.2、データ構造編5.8）。"""

import time

from app.ai import auth as ai_auth
from app.ai import client as ai_client


def test_get_status_when_unauthenticated_skips_model_status_call(seeded_session, monkeypatch):
    monkeypatch.setattr(ai_client, "is_authenticated", lambda session: False)

    def _fail(session):
        raise AssertionError("未認証時はモデル稼働状況を取得しないはず")

    monkeypatch.setattr(ai_client, "get_model_status", _fail)

    snapshot = ai_auth.get_status(seeded_session)

    assert snapshot.authenticated is False
    assert snapshot.model_status == {}
    assert snapshot.login_in_progress is False


def test_get_status_when_authenticated_includes_model_status(seeded_session, monkeypatch):
    monkeypatch.setattr(ai_client, "is_authenticated", lambda session: True)
    monkeypatch.setattr(ai_client, "get_model_status", lambda session: {"gpt-5": True})

    snapshot = ai_auth.get_status(seeded_session)

    assert snapshot.authenticated is True
    assert snapshot.model_status == {"gpt-5": True}


def test_get_status_swallows_model_status_error(seeded_session, monkeypatch):
    monkeypatch.setattr(ai_client, "is_authenticated", lambda session: True)

    def _raise(session):
        raise RuntimeError("接続失敗")

    monkeypatch.setattr(ai_client, "get_model_status", _raise)

    snapshot = ai_auth.get_status(seeded_session)

    assert snapshot.authenticated is True
    assert snapshot.model_status == {}


def test_register_pat_without_host_keeps_existing_host(seeded_session, monkeypatch):
    applied = {}

    class _FakeConfigManager:
        pass

    class _FakeAuthManager:
        def __init__(self, config_manager):
            pass

        def is_authenticated(self):
            return False

    monkeypatch.setattr(ai_auth, "ConfigManager", _FakeConfigManager)
    monkeypatch.setattr(ai_auth, "AuthManager", _FakeAuthManager)
    monkeypatch.setattr(
        ai_client,
        "apply_config_snapshot",
        lambda config_manager, snapshot: applied.update(snapshot),
    )

    result = ai_auth.register_pat(seeded_session, host=None, personal_access_token="123|abc")

    assert result is False
    assert "host" not in applied
    assert applied["personal_access_token"] == "123|abc"


def test_register_pat_applies_snapshot_and_returns_auth_state(seeded_session, monkeypatch):
    applied = {}

    class _FakeConfigManager:
        pass

    class _FakeAuthManager:
        def __init__(self, config_manager):
            pass

        def is_authenticated(self):
            return True

    monkeypatch.setattr(ai_auth, "ConfigManager", _FakeConfigManager)
    monkeypatch.setattr(ai_auth, "AuthManager", _FakeAuthManager)
    monkeypatch.setattr(
        ai_client,
        "apply_config_snapshot",
        lambda config_manager, snapshot: applied.update(snapshot),
    )

    result = ai_auth.register_pat(
        seeded_session, host="example.newton-x.net", personal_access_token="123|abc"
    )

    assert result is True
    assert applied["host"] == "example.newton-x.net"
    assert applied["personal_access_token"] == "123|abc"


def test_start_fallback_login_runs_in_background_and_updates_progress_flag(
    seeded_session, monkeypatch
):
    calls = []
    ai_auth._state.in_progress = False

    def _fake_start_browser_login(snapshot):
        calls.append(snapshot)
        return True

    monkeypatch.setattr(ai_client, "start_browser_login", _fake_start_browser_login)

    started = ai_auth.start_fallback_login(seeded_session)
    assert started is True

    deadline = time.monotonic() + 2
    while ai_auth._state.in_progress and time.monotonic() < deadline:
        time.sleep(0.01)

    assert ai_auth._state.in_progress is False
    assert len(calls) == 1


def test_start_fallback_login_clears_progress_flag_even_when_thread_raises(
    seeded_session, monkeypatch
):
    ai_auth._state.in_progress = False

    def _raising_start_browser_login(snapshot):
        raise RuntimeError("ブラウザ起動に失敗")

    monkeypatch.setattr(ai_client, "start_browser_login", _raising_start_browser_login)

    ai_auth.start_fallback_login(seeded_session)

    deadline = time.monotonic() + 2
    while ai_auth._state.in_progress and time.monotonic() < deadline:
        time.sleep(0.01)

    assert ai_auth._state.in_progress is False


def test_start_fallback_login_is_noop_when_already_in_progress(seeded_session):
    ai_auth._state.in_progress = True
    try:
        started = ai_auth.start_fallback_login(seeded_session)
        assert started is False
    finally:
        ai_auth._state.in_progress = False


def test_logout_delegates_to_ai_client(seeded_session, monkeypatch):
    calls = []
    monkeypatch.setattr(ai_client, "logout", lambda session: calls.append(session))

    ai_auth.logout(seeded_session)

    assert calls == [seeded_session]
