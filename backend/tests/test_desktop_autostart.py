"""autostart のテスト（Windows起動時の自動起動、実装スコープB、Phase37）。

完了条件「自動起動の有効／無効がスタートアップ登録に反映される」を、`winreg`の偽物
（`tests/fake_registry.py`）への書き込み内容で検証する。実際のレジストリには触れない。
"""

import pytest

from app.constants.desktop import LAUNCH_AT_LOGIN_REGISTRY_KEY, LAUNCH_AT_LOGIN_VALUE_NAME
from app.desktop import autostart
from tests.fake_registry import FakeRegistry

EXE_PATH = r"C:\Michinari\Michinari.exe"


@pytest.fixture
def registry() -> FakeRegistry:
    return FakeRegistry()


@pytest.fixture
def frozen(monkeypatch: pytest.MonkeyPatch):
    """配布パッケージ（`sys.frozen`）として起動している状態を模す。"""
    monkeypatch.setattr(autostart.sys, "frozen", True, raising=False)


class TestResolveLaunchCommand:
    def test_wraps_the_path_in_quotes(self):
        """インストール先にスペースを含んでもWindowsがパスを途中で切らないこと。"""
        command = autostart.resolve_launch_command(r"C:\Program Files\Michinari\Michinari.exe")
        assert command == r'"C:\Program Files\Michinari\Michinari.exe"'

    def test_defaults_to_the_running_executable(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(autostart.sys, "executable", EXE_PATH)
        assert autostart.resolve_launch_command() == f'"{EXE_PATH}"'


class TestIsSupported:
    def test_true_when_frozen(self, frozen):
        assert autostart.is_supported()

    def test_false_when_running_from_source(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(autostart.sys, "frozen", False, raising=False)
        assert not autostart.is_supported()


class TestEnableAndDisable:
    def test_enable_writes_the_run_entry(self, registry: FakeRegistry):
        autostart.enable(registry, executable=EXE_PATH)

        assert registry.keys[LAUNCH_AT_LOGIN_REGISTRY_KEY][LAUNCH_AT_LOGIN_VALUE_NAME] == (
            f'"{EXE_PATH}"'
        )

    def test_enable_refreshes_a_stale_path(self, registry: FakeRegistry):
        """フォルダを移動した利用者の登録が古いパスのまま残らないこと。"""
        autostart.enable(registry, executable=r"C:\Old\Michinari.exe")
        autostart.enable(registry, executable=EXE_PATH)

        assert registry.keys[LAUNCH_AT_LOGIN_REGISTRY_KEY][LAUNCH_AT_LOGIN_VALUE_NAME] == (
            f'"{EXE_PATH}"'
        )

    def test_disable_removes_the_run_entry(self, registry: FakeRegistry):
        autostart.enable(registry, executable=EXE_PATH)
        autostart.disable(registry)

        assert LAUNCH_AT_LOGIN_VALUE_NAME not in registry.keys[LAUNCH_AT_LOGIN_REGISTRY_KEY]

    def test_disable_is_silent_when_nothing_is_registered(self, registry: FakeRegistry):
        """未登録の状態で解除しても失敗しないこと（利用者から見た結果は同じため）。"""
        autostart.disable(registry)

        assert registry.keys == {}


class TestIsEnabled:
    def test_false_when_the_key_is_absent(self, registry: FakeRegistry):
        assert not autostart.is_enabled(registry)

    def test_false_when_the_key_exists_without_the_value(self, registry: FakeRegistry):
        registry.keys[LAUNCH_AT_LOGIN_REGISTRY_KEY] = {"OtherApp": "x"}
        assert not autostart.is_enabled(registry)

    def test_true_after_enabling(self, registry: FakeRegistry):
        autostart.enable(registry, executable=EXE_PATH)
        assert autostart.is_enabled(registry)


class TestApply:
    def test_registers_when_enabled(self, registry: FakeRegistry, frozen):
        assert autostart.apply(True, registry, executable=EXE_PATH)
        assert autostart.is_enabled(registry)

    def test_unregisters_when_disabled(self, registry: FakeRegistry, frozen):
        autostart.enable(registry, executable=EXE_PATH)

        assert autostart.apply(False, registry, executable=EXE_PATH)
        assert not autostart.is_enabled(registry)

    def test_does_nothing_when_running_from_source(
        self, registry: FakeRegistry, monkeypatch: pytest.MonkeyPatch
    ):
        """Pythonインタプリタのパスを登録してしまわないこと。"""
        monkeypatch.setattr(autostart.sys, "frozen", False, raising=False)

        assert not autostart.apply(True, registry, executable=EXE_PATH)
        assert registry.keys == {}
