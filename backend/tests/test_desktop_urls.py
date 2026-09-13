"""browser のテスト（画面URLの組み立てとフロントエンドのルート定義との整合、Phase37）。

通知をクリックしたときに開く先が404にならないよう、Python側のパス定義
（`app/constants/desktop.py`の`DAILY_REPORT_PATH_TEMPLATE`）と、フロントエンドの
`frontend/src/constants/routes.ts`の`ROUTES.dailyReport`が同じ形であることを機械的に
確かめる。言語が違うため値そのものを共有できず、片方だけ変更されうるためである。
"""

import datetime as dt
import re

import pytest

from app.config import REPO_ROOT
from app.constants.desktop import DAILY_REPORT_PATH_TEMPLATE, LOCAL_HOST
from app.desktop import assets, browser
from app.services import notification_service

ROUTES_PATH = REPO_ROOT / "frontend" / "src" / "constants" / "routes.ts"
DESKTOP_SETTINGS_TS_PATH = (
    REPO_ROOT / "frontend" / "src" / "features" / "settings" / "desktopSettings.ts"
)


class TestAppUrl:
    def test_builds_the_top_page_url(self):
        assert browser.app_url(8100) == "http://127.0.0.1:8100"

    def test_appends_the_given_path(self):
        assert browser.app_url(8100, "/calendar") == "http://127.0.0.1:8100/calendar"

    def test_always_targets_the_loopback_address(self):
        """サーバは全インタフェースで待ち受けるが、開くのは常に自端末であること。"""
        assert LOCAL_HOST in browser.app_url(1234)
        assert "0.0.0.0" not in browser.app_url(1234)

    def test_uses_the_given_port(self):
        assert browser.app_url(9999) == "http://127.0.0.1:9999"


class TestDailyReportUrl:
    def test_builds_the_record_screen_url(self):
        url = browser.daily_report_url(8100, dt.date(2026, 9, 13))

        assert url == "http://127.0.0.1:8100/records/2026-09-13/report"

    def test_formats_the_date_as_iso(self):
        """月日が1桁の日でもゼロ埋めされること（フロントのルートがその形を期待する）。"""
        url = browser.daily_report_url(8100, dt.date(2026, 1, 5))

        assert url.endswith("/records/2026-01-05/report")


def test_daily_report_path_matches_the_frontend_route_definition():
    """`ROUTES.dailyReport`（routes.ts）とPython側のパス定義が一致すること。"""
    source = ROUTES_PATH.read_text(encoding="utf-8")
    match = re.search(r"dailyReport:\s*\(date:\s*string\)\s*=>\s*`([^`]+)`", source)

    assert match is not None, "routes.ts の ROUTES.dailyReport を読み取れませんでした"
    # routes.ts はテンプレートリテラル（`/records/${date}/report`）、Python側は
    # str.format（/records/{date}/report）で書くため、表記だけ揃えて比較する。
    assert match.group(1).replace("${date}", "{date}") == DAILY_REPORT_PATH_TEMPLATE


def test_icon_exists_at_the_path_the_app_resolves():
    """トレイ・通知・exeが参照するアイコンが実在すること（同梱漏れの検出）。"""
    icon_path = assets.resolve_icon_path()

    assert icon_path.is_file()
    assert icon_path.suffix == ".ico"


class TestOpenInBrowser:
    """既定のブラウザを開く処理（Phase37）。

    `webbrowser.open` は差し替えられるため、実ブラウザを起動せずに「どのURLを開くか」まで
    検証できる。URLの組み立てだけをテストしていると、`open_daily_report` がトップ画面を
    開いてしまう取り違えを見逃す。
    """

    def test_open_app_opens_the_top_page(self, monkeypatch: pytest.MonkeyPatch):
        opened: list[str] = []
        monkeypatch.setattr(browser.webbrowser, "open", opened.append)

        browser.open_app(8100)

        assert opened == ["http://127.0.0.1:8100"]

    def test_open_daily_report_opens_the_record_screen(self, monkeypatch: pytest.MonkeyPatch):
        opened: list[str] = []
        monkeypatch.setattr(browser.webbrowser, "open", opened.append)

        browser.open_daily_report(8100, dt.date(2026, 9, 13))

        assert opened == ["http://127.0.0.1:8100/records/2026-09-13/report"]


def test_notification_time_pattern_matches_the_frontend_validation():
    """通知時刻の受け付ける形式が、画面側の判定と一致すること。

    `frontend/src/features/settings/desktopSettings.ts` とサーバ側で同じ規則を別々に
    持っている。片方だけ緩めると「画面では保存できるのにサーバが弾く」（またはその逆）に
    なるため、画面ルートの整合（上の突き合わせ）と同じ方式で機械的に確かめる。
    """
    source = DESKTOP_SETTINGS_TS_PATH.read_text(encoding="utf-8")
    match = re.search(r"export const NOTIFICATION_TIME_PATTERN = /(.+)/\n", source)

    assert match is not None, "desktopSettings.ts の NOTIFICATION_TIME_PATTERN を読み取れません"
    assert match.group(1) == notification_service.NOTIFICATION_TIME_PATTERN.pattern
