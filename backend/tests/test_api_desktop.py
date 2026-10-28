"""`POST /desktop/autostart/sync`のテスト（開発Todo リマインド導線 D6〜D8）。

保存済みの`desktop.launch_at_login`を今すぐWindowsレジストリへ反映する「今すぐ反映」API。
実際のレジストリには触れず、`app.api.desktop.autostart`の関数を差し替えて検証する。
"""

import pytest

from app.api import desktop as desktop_api


def test_sync_reports_unsupported_when_not_running_as_a_packaged_app(client):
    """開発環境（ソース起動）では失敗ではなく`supported=False`を返すこと（D7）。"""
    response = client.post("/api/v1/desktop/autostart/sync")

    assert response.status_code == 200
    body = response.json()
    assert body["supported"] is False
    assert body["applied"] is False
    assert body["launch_at_login"] is False


def test_sync_reads_the_currently_saved_value(client):
    client.patch("/api/v1/settings", json={"desktop": {"launch_at_login": True}})

    response = client.post("/api/v1/desktop/autostart/sync")

    assert response.json()["launch_at_login"] is True


def test_sync_applies_when_supported(client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(desktop_api.autostart, "is_supported", lambda: True)
    monkeypatch.setattr(desktop_api.autostart, "apply", lambda enabled: True)

    response = client.post("/api/v1/desktop/autostart/sync")

    body = response.json()
    assert body["supported"] is True
    assert body["applied"] is True


def test_sync_reports_not_applied_when_the_registry_write_fails(
    client, monkeypatch: pytest.MonkeyPatch
):
    """レジストリ書き込みの失敗（OSError）を外へ投げず、applied=falseで返すこと（D7）。"""
    monkeypatch.setattr(desktop_api.autostart, "is_supported", lambda: True)

    def _raise(enabled: bool) -> bool:
        raise OSError("registry write failed")

    monkeypatch.setattr(desktop_api.autostart, "apply", _raise)

    response = client.post("/api/v1/desktop/autostart/sync")

    assert response.status_code == 200
    body = response.json()
    assert body["supported"] is True
    assert body["applied"] is False
