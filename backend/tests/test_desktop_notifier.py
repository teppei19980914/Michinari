"""notifier のテスト（AppUserModelIDの登録とトーストの組み立て、Phase37）。

デスクトップアプリがトーストを出すにはAppUserModelIDの登録が要る（Microsoft公式）。
登録の中身を`winreg`の偽物（`tests/fake_registry.py`）で検証し、実際のレジストリには
触れない。実際にトーストを画面へ出す処理（`windows_toasts`の呼び出し）は差し替える。
"""

from pathlib import Path

import pytest

from app.constants.desktop import (
    APP_USER_MODEL_ID,
    AUMID_DISPLAY_NAME_VALUE,
    AUMID_ICON_URI_VALUE,
    AUMID_REGISTRY_KEY,
)
from app.desktop import notifier as notifier_module
from app.desktop.assets import resolve_icon_path
from tests.fake_registry import FakeRegistry

DISPLAY_NAME = "ミチナリ"


@pytest.fixture
def registry() -> FakeRegistry:
    return FakeRegistry()


class _FakeToaster:
    """`InteractableWindowsToaster`の代わり。表示せず、渡されたトーストを記録する。"""

    def __init__(self, application_text: str, notifierAUMID: str | None = None) -> None:  # noqa: N803 (ライブラリの引数名に合わせる)
        self.application_text = application_text
        self.aumid = notifierAUMID
        self.shown: list[object] = []

    def show_toast(self, toast: object) -> None:
        self.shown.append(toast)


@pytest.fixture
def fake_toasters(monkeypatch: pytest.MonkeyPatch) -> list[_FakeToaster]:
    created: list[_FakeToaster] = []

    def _factory(application_text: str, notifierAUMID: str | None = None) -> _FakeToaster:  # noqa: N803 (同上)
        toaster = _FakeToaster(application_text, notifierAUMID=notifierAUMID)
        created.append(toaster)
        return toaster

    monkeypatch.setattr(notifier_module, "InteractableWindowsToaster", _factory)
    return created


class TestRegisterAppUserModelId:
    def test_writes_the_display_name(self, registry: FakeRegistry):
        notifier_module.register_app_user_model_id(DISPLAY_NAME, None, registry)

        assert registry.keys[AUMID_REGISTRY_KEY][AUMID_DISPLAY_NAME_VALUE] == DISPLAY_NAME

    def test_writes_the_icon_path_when_the_file_exists(self, registry: FakeRegistry):
        icon_path = resolve_icon_path()

        notifier_module.register_app_user_model_id(DISPLAY_NAME, icon_path, registry)

        assert registry.keys[AUMID_REGISTRY_KEY][AUMID_ICON_URI_VALUE] == str(icon_path)

    def test_skips_the_icon_when_the_file_is_missing(self, registry: FakeRegistry, tmp_path: Path):
        """同梱漏れでも登録自体は成立させること（アイコン無しの通知は出せるため）。"""
        notifier_module.register_app_user_model_id(DISPLAY_NAME, tmp_path / "missing.ico", registry)

        assert AUMID_ICON_URI_VALUE not in registry.keys[AUMID_REGISTRY_KEY]

    def test_uses_the_application_specific_identifier_by_default(self, registry: FakeRegistry):
        """一度配布したら変えない識別子であること（変えると通知設定が引き継がれない）。"""
        notifier_module.register_app_user_model_id(DISPLAY_NAME, None, registry)

        assert APP_USER_MODEL_ID in next(iter(registry.keys))

    def test_honours_a_custom_identifier(self, registry: FakeRegistry):
        notifier_module.register_app_user_model_id(
            DISPLAY_NAME, None, registry, app_user_model_id="Other.App"
        )

        assert r"SOFTWARE\Classes\AppUserModelId\Other.App" in registry.keys


class TestToastNotifier:
    def test_registers_the_identifier_on_construction(
        self, registry: FakeRegistry, fake_toasters: list[_FakeToaster]
    ):
        notifier_module.ToastNotifier(DISPLAY_NAME, None, registry)

        assert registry.keys[AUMID_REGISTRY_KEY][AUMID_DISPLAY_NAME_VALUE] == DISPLAY_NAME
        assert fake_toasters[0].aumid == APP_USER_MODEL_ID

    def test_show_builds_a_toast_with_title_and_body(
        self, registry: FakeRegistry, fake_toasters: list[_FakeToaster]
    ):
        notifier = notifier_module.ToastNotifier(DISPLAY_NAME, None, registry)

        notifier.show("見出し", "本文")

        toast = fake_toasters[0].shown[0]
        assert toast.text_fields == ["見出し", "本文"]

    def test_show_wires_the_click_callback(
        self, registry: FakeRegistry, fake_toasters: list[_FakeToaster]
    ):
        """通知をクリックしたら記録画面を開けるよう、コールバックが結び付くこと。"""
        clicked: list[bool] = []
        notifier = notifier_module.ToastNotifier(DISPLAY_NAME, None, registry)

        notifier.show("見出し", "本文", on_click=lambda: clicked.append(True))
        fake_toasters[0].shown[0].on_activated(object())

        assert clicked == [True]

    def test_show_leaves_the_callback_unset_when_not_given(
        self, registry: FakeRegistry, fake_toasters: list[_FakeToaster]
    ):
        notifier = notifier_module.ToastNotifier(DISPLAY_NAME, None, registry)

        notifier.show("見出し", "本文")

        assert fake_toasters[0].shown[0].on_activated is None

    def test_show_attaches_the_icon_when_available(
        self, registry: FakeRegistry, fake_toasters: list[_FakeToaster]
    ):
        notifier = notifier_module.ToastNotifier(DISPLAY_NAME, resolve_icon_path(), registry)

        notifier.show("見出し", "本文")

        assert fake_toasters[0].shown[0].images

    def test_show_omits_the_icon_when_missing(
        self, registry: FakeRegistry, fake_toasters: list[_FakeToaster], tmp_path: Path
    ):
        notifier = notifier_module.ToastNotifier(DISPLAY_NAME, tmp_path / "missing.ico", registry)

        notifier.show("見出し", "本文")

        assert not fake_toasters[0].shown[0].images
