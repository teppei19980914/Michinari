"""locales のテスト（バックエンドが出す文言の解決、Phase37）。

トレイ・通知・起動失敗ダイアログの文言は`frontend/src/locales/ja.json`に置き、Pythonから
同じファイルを読む。**`app/constants/locale_keys.py`に並ぶキーが実在すること**をここで
検証する。キーの綴りを間違えても`t()`はキー文字列をそのまま返して動き続けてしまい、
画面に`desktop.tray.open`と表示されるまで気付けないためである。

解決規則が`frontend/src/locales/t.ts`と揃っていること（未解決時はキーを返す、`{{var}}`を
置換する）も合わせて確認する。
"""

import json

import pytest

from app import locales
from app.constants import locale_keys

#: `locale_keys`が公開している全キー（定数を1つ増やしたら自動的に検証対象へ入る）。
ALL_LOCALE_KEYS = sorted(
    value
    for name, value in vars(locale_keys).items()
    if not name.startswith("_") and isinstance(value, str)
)


def test_locale_keys_module_exposes_keys():
    """定数の抽出が空振りしていないこと（この表が空だと下の検証が素通りする）。"""
    assert ALL_LOCALE_KEYS


@pytest.mark.parametrize("key", ALL_LOCALE_KEYS)
def test_every_locale_key_resolves_to_a_message(key: str):
    """`locale_keys`の全キーが`ja.json`に実在すること。"""
    resolved = locales.t(key)

    assert resolved != key, f"ロケールファイルに {key} がありません"
    assert resolved.strip()


def test_locale_file_exists_at_the_expected_path():
    path = locales.resolve_locale_path()

    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8"))


def test_startup_error_body_uses_both_placeholders():
    """起動失敗ダイアログが、原因とログの場所の両方を差し込めること。"""
    resolved = locales.t(locale_keys.STARTUP_ERROR_BODY, detail="原因", logPath="C:/log.txt")

    assert "原因" in resolved
    assert "C:/log.txt" in resolved
    assert "{{" not in resolved


class TestT:
    """`frontend/src/locales/t.ts`と同じ解決規則であること。"""

    def test_returns_the_key_when_it_is_missing(self):
        assert locales.t("desktop.tray.does_not_exist") == "desktop.tray.does_not_exist"

    def test_returns_the_key_when_it_points_at_a_group(self):
        """途中の階層（辞書）で止まるキーは文字列ではないため、キーをそのまま返すこと。"""
        assert locales.t("desktop.tray") == "desktop.tray"

    def test_returns_the_key_when_traversing_through_a_string(self):
        assert locales.t("desktop.tray.open.deeper") == "desktop.tray.open.deeper"

    def test_leaves_text_untouched_without_variables(self):
        assert locales.t(locale_keys.TRAY_QUIT) == "終了"


class TestLoadMessages:
    def test_returns_empty_dict_when_the_file_is_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ):
        """同梱漏れでもアプリが起動できること（文言はキー表示になるが動き続ける）。"""
        missing = tmp_path / "存在しない.json"
        locales.load_messages.cache_clear()
        monkeypatch.setattr(
            locales, "resolve_locale_path", lambda locale=locales.DEFAULT_LOCALE: missing
        )

        assert locales.load_messages("missing-locale") == {}

        locales.load_messages.cache_clear()

    def test_returns_empty_dict_when_the_file_is_broken(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ):
        broken = tmp_path / "broken.json"
        broken.write_text("{ これはJSONではない", encoding="utf-8")
        locales.load_messages.cache_clear()
        monkeypatch.setattr(
            locales, "resolve_locale_path", lambda locale=locales.DEFAULT_LOCALE: broken
        )

        assert locales.load_messages("broken-locale") == {}

        locales.load_messages.cache_clear()
