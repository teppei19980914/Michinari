"""tray のテスト（通知領域のアイコンとメニュー、実装スコープA、Phase37）。

`Icon.run()`（表示・メッセージループ）はユニットテストの対象外とし、組み立てた内容
（メニュー項目・既定動作・ツールチップ）と、アイコン画像の読み込みを検証する。
"""

from pathlib import Path

import pystray
import pytest

from app.constants import locale_keys
from app.desktop import tray
from app.desktop.assets import resolve_icon_path
from app.locales import t


@pytest.fixture
def icon() -> pystray.Icon:
    return tray.build_icon(
        on_open=lambda: None, on_quit=lambda: None, icon_path=resolve_icon_path()
    )


class TestLoadIconImage:
    def test_loads_the_bundled_icon(self):
        image = tray.load_icon_image(resolve_icon_path())

        assert image.size[0] > 0

    def test_falls_back_when_the_icon_cannot_be_read(self, tmp_path: Path):
        """アイコンが欠けただけでアプリを起動できなくしないこと。"""
        image = tray.load_icon_image(tmp_path / "missing.ico")

        assert image.size == tray.FALLBACK_ICON_SIZE


class TestBuildIcon:
    def test_shows_the_application_name_as_the_tooltip(self, icon: pystray.Icon):
        assert icon.title == t(locale_keys.TRAY_TOOLTIP)

    def test_offers_open_and_quit(self, icon: pystray.Icon):
        labels = [str(item.text) for item in icon.menu]

        assert labels == [t(locale_keys.TRAY_OPEN), t(locale_keys.TRAY_QUIT)]

    def test_open_is_the_default_action(self, icon: pystray.Icon):
        """Windowsではアイコンの左クリックで既定の項目が呼ばれる（＝画面が開く）。"""
        items = list(icon.menu)

        assert items[0].default
        assert not items[1].default

    def test_open_invokes_the_callback(self):
        opened: list[bool] = []
        icon = tray.build_icon(
            on_open=lambda: opened.append(True),
            on_quit=lambda: None,
            icon_path=resolve_icon_path(),
        )

        list(icon.menu)[0](icon)

        assert opened == [True]

    def test_quit_invokes_the_callback(self):
        quit_calls: list[bool] = []
        icon = tray.build_icon(
            on_open=lambda: None,
            on_quit=lambda: quit_calls.append(True),
            icon_path=resolve_icon_path(),
        )

        list(icon.menu)[1](icon)

        assert quit_calls == [True]
