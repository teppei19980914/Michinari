"""ai/client のテスト（ロジック・プロンプト編16.1〜16.2・16.6、実装フェーズ分割計画書Phase5）。

実際のNewtonX ADK（newtonx_adk）へは接続しない。app.ai.client がインポートしている
NewtonXClient/ConfigManager/AuthManager をフェイクに差し替えてテストする。
"""

import pytest
from newtonx_adk.exceptions import (
    APIError,
    AuthenticationError,
    ChatError,
    ConfigurationError,
)

from app.ai import client as ai_client
from app.ai.exceptions import AiAuthRequiredError, AiConfigError, AiError, AiTimeoutError


class FakeConfigManager:
    def __init__(self):
        self.updates: dict[str, object] = {}

    def update_config(self, **kwargs):
        self.updates.update(kwargs)


class FakeAuthManager:
    instances: list["FakeAuthManager"] = []

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logged_out = False
        FakeAuthManager.instances.append(self)

    def is_authenticated(self):
        return True

    def logout(self):
        self.logged_out = True


class FakeNewtonXClient:
    last_instance: "FakeNewtonXClient | None" = None

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.authenticate_called = False
        self.send_message_kwargs: dict | None = None
        self.model_status_result = {"gpt-5": True}
        self.assistants_result = [{"uid": "a1", "name": "アシスタントA"}]
        self.send_message_result: str | None = "AIからの応答"
        self.create_chat_result: str | None = "chat-uid-1"
        self.raise_on: Exception | None = None
        FakeNewtonXClient.last_instance = self

    def _maybe_raise(self):
        if self.raise_on is not None:
            raise self.raise_on

    def authenticate(self):
        self.authenticate_called = True
        return True

    def get_model_status(self):
        self._maybe_raise()
        return self.model_status_result

    def get_assistants(self):
        self._maybe_raise()
        return self.assistants_result

    def create_chat_in_folder_by_name(self, assistant_uid, folder_name, title=None):
        self._maybe_raise()
        return self.create_chat_result

    def send_message(self, chat_uid, message, knowledge_search, web_search):
        self._maybe_raise()
        self.send_message_kwargs = {
            "chat_uid": chat_uid,
            "message": message,
            "knowledge_search": knowledge_search,
            "web_search": web_search,
        }
        return self.send_message_result


@pytest.fixture(autouse=True)
def _patch_adk(monkeypatch):
    FakeAuthManager.instances.clear()
    monkeypatch.setattr(ai_client, "ConfigManager", FakeConfigManager)
    monkeypatch.setattr(ai_client, "AuthManager", FakeAuthManager)
    monkeypatch.setattr(ai_client, "NewtonXClient", FakeNewtonXClient)


# --- _translate_error ---


def test_translate_error_maps_authentication_error():
    result = ai_client._translate_error(
        AuthenticationError("認証切れ"), elapsed_seconds=1.0, timeout_seconds=60
    )
    assert isinstance(result, AiAuthRequiredError)


def test_translate_error_maps_configuration_error():
    result = ai_client._translate_error(
        ConfigurationError("設定不備"), elapsed_seconds=1.0, timeout_seconds=60
    )
    assert isinstance(result, AiConfigError)


def test_translate_error_maps_to_timeout_when_elapsed_exceeds_setting():
    result = ai_client._translate_error(
        APIError("通信失敗"), elapsed_seconds=61.0, timeout_seconds=60
    )
    assert isinstance(result, AiTimeoutError)


def test_translate_error_maps_to_timeout_when_message_mentions_timeout():
    result = ai_client._translate_error(
        APIError("Connection timeout occurred"), elapsed_seconds=1.0, timeout_seconds=60
    )
    assert isinstance(result, AiTimeoutError)


def test_translate_error_maps_chat_error_to_ai_error_with_retry_hint():
    result = ai_client._translate_error(
        ChatError("チャット失敗"), elapsed_seconds=1.0, timeout_seconds=60
    )
    assert isinstance(result, AiError)
    assert "再試行" in str(result)


def test_translate_error_maps_unknown_exception_to_ai_error():
    result = ai_client._translate_error(
        ValueError("想定外"), elapsed_seconds=1.0, timeout_seconds=60
    )
    assert isinstance(result, AiError)


# --- 各API呼び出し ---


def test_is_authenticated_delegates_to_auth_manager(seeded_session):
    assert ai_client.is_authenticated(seeded_session) is True


def test_get_model_status_returns_client_result(seeded_session):
    result = ai_client.get_model_status(seeded_session)
    assert result == {"gpt-5": True}


def test_get_model_status_translates_error(seeded_session, monkeypatch):
    class _ErrorClient(FakeNewtonXClient):
        def get_model_status(self):
            raise AuthenticationError("未認証")

    monkeypatch.setattr(ai_client, "NewtonXClient", _ErrorClient)
    with pytest.raises(AiAuthRequiredError):
        ai_client.get_model_status(seeded_session)


def test_get_assistants_returns_client_result(seeded_session):
    result = ai_client.get_assistants(seeded_session)
    assert result == [{"uid": "a1", "name": "アシスタントA"}]


def test_get_assistants_excludes_unsupported_assistants(seeded_session, monkeypatch):
    class _ClientWithUnsupportedAssistants(FakeNewtonXClient):
        def __init__(self, config_manager):
            super().__init__(config_manager)
            self.assistants_result = [
                {"uid": "a1", "name": "アシスタントA"},
                {"uid": "a2", "name": "GPT-4o mini"},
                {"uid": "a3", "name": "GPT-4o"},
            ]

    monkeypatch.setattr(ai_client, "NewtonXClient", _ClientWithUnsupportedAssistants)

    result = ai_client.get_assistants(seeded_session)

    assert result == [{"uid": "a1", "name": "アシスタントA"}]


def test_create_chat_in_folder_by_name_returns_chat_uid(seeded_session):
    chat_uid = ai_client.create_chat_in_folder_by_name(
        seeded_session, assistant_uid="asst-1", folder_name="フォルダ", title="タイトル"
    )
    assert chat_uid == "chat-uid-1"


def test_send_message_disables_web_search_and_knowledge_search_explicitly(seeded_session):
    """Web検索・ナレッジ検索の明示的無効化（Phase5完了条件）。"""
    result = ai_client.send_message(seeded_session, chat_uid="chat-1", message="こんにちは")

    sent = FakeNewtonXClient.last_instance.send_message_kwargs
    assert sent["knowledge_search"] is False
    assert sent["web_search"] is False
    assert sent["chat_uid"] == "chat-1"
    assert sent["message"] == "こんにちは"
    assert result.response_text == "AIからの応答"
    assert result.latency_ms >= 0


def test_send_message_raises_ai_error_when_response_is_none(seeded_session, monkeypatch):
    class _NoneResponseClient(FakeNewtonXClient):
        def send_message(self, chat_uid, message, knowledge_search, web_search):
            return None

    monkeypatch.setattr(ai_client, "NewtonXClient", _NoneResponseClient)
    with pytest.raises(AiError):
        ai_client.send_message(seeded_session, chat_uid="chat-1", message="こんにちは")


def test_logout_calls_auth_manager_logout(seeded_session):
    ai_client.logout(seeded_session)
    assert FakeAuthManager.instances[-1].logged_out is True


def test_start_browser_login_uses_snapshot_and_calls_authenticate(seeded_session):
    snapshot = ai_client.read_config_snapshot(seeded_session)
    result = ai_client.start_browser_login(snapshot)
    assert result is True
    assert FakeNewtonXClient.last_instance.authenticate_called is True


def test_read_config_snapshot_excludes_pat(seeded_session):
    snapshot = ai_client.read_config_snapshot(seeded_session)
    assert "personal_access_token" not in snapshot
    assert "timeout" in snapshot
    assert "max_retries" in snapshot


def test_read_config_snapshot_includes_host_and_identity_when_set(seeded_session):
    from app.constants.app_setting_keys import (
        AI_API_BASE_URL,
        AI_CLIENT_ID,
        AI_HOST,
        AI_TENANT_ID,
    )
    from app.models.setting import AppSetting

    for key, value in (
        (AI_HOST, "example.newton-x.net"),
        (AI_CLIENT_ID, "client-1"),
        (AI_TENANT_ID, "tenant-1"),
        (AI_API_BASE_URL, "https://example.newton-x.net/api"),
    ):
        seeded_session.query(AppSetting).filter_by(key=key).update({"value": value})
    seeded_session.flush()

    snapshot = ai_client.read_config_snapshot(seeded_session)

    assert snapshot["host"] == "example.newton-x.net"
    assert snapshot["client_id"] == "client-1"
    assert snapshot["tenant_id"] == "tenant-1"
    assert snapshot["api_base_url"] == "https://example.newton-x.net/api"


def test_get_assistants_translates_error(seeded_session, monkeypatch):
    class _ErrorClient(FakeNewtonXClient):
        def get_assistants(self):
            raise AuthenticationError("未認証")

    monkeypatch.setattr(ai_client, "NewtonXClient", _ErrorClient)
    with pytest.raises(AiAuthRequiredError):
        ai_client.get_assistants(seeded_session)


def test_create_chat_in_folder_by_name_translates_error(seeded_session, monkeypatch):
    class _ErrorClient(FakeNewtonXClient):
        def create_chat_in_folder_by_name(self, assistant_uid, folder_name, title=None):
            raise AuthenticationError("未認証")

    monkeypatch.setattr(ai_client, "NewtonXClient", _ErrorClient)
    with pytest.raises(AiAuthRequiredError):
        ai_client.create_chat_in_folder_by_name(
            seeded_session, assistant_uid="asst-1", folder_name="フォルダ", title="タイトル"
        )


def test_create_chat_in_folder_by_name_raises_ai_error_when_result_is_empty(
    seeded_session, monkeypatch
):
    class _EmptyResultClient(FakeNewtonXClient):
        def create_chat_in_folder_by_name(self, assistant_uid, folder_name, title=None):
            return None

    monkeypatch.setattr(ai_client, "NewtonXClient", _EmptyResultClient)
    with pytest.raises(AiError):
        ai_client.create_chat_in_folder_by_name(
            seeded_session, assistant_uid="asst-1", folder_name="フォルダ", title="タイトル"
        )


def test_send_message_translates_error(seeded_session, monkeypatch):
    class _ErrorClient(FakeNewtonXClient):
        def send_message(self, chat_uid, message, knowledge_search, web_search):
            raise AuthenticationError("未認証")

    monkeypatch.setattr(ai_client, "NewtonXClient", _ErrorClient)
    with pytest.raises(AiAuthRequiredError):
        ai_client.send_message(seeded_session, chat_uid="chat-1", message="こんにちは")
