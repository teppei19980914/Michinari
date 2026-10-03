"""ブラウザで画面を開く（Phase37）。

画面を開く入口は3つある（起動時の自動起動・トレイメニューの「ミチナリを開く」・通知の
クリック）。URLの組み立てを1箇所へ集約し、ポート番号やパスの書き方がばらけないようにする
（CLAUDE.md DRYの原則）。
"""

from __future__ import annotations

import datetime as dt
import logging
import webbrowser

from app.constants.desktop import DAILY_REPORT_PATH_TEMPLATE, LOCAL_HOST

logger = logging.getLogger(__name__)


def app_url(port: int, path: str = "") -> str:
    """アプリの画面URLを組み立てる。

    引数:
        port: サーバの待ち受けポート（`app_setting`の`server.port`）。
        path: `/records/2026-09-13/report`のような画面のパス。省略時はトップ画面。

    返り値:
        `http://127.0.0.1:8100/...`形式のURL。

    使用例:
        >>> app_url(8100)
        'http://127.0.0.1:8100'
        >>> app_url(8100, "/calendar")
        'http://127.0.0.1:8100/calendar'
    """
    return f"http://{LOCAL_HOST}:{port}{path}"


def daily_report_url(port: int, target_date: dt.date) -> str:
    """記録画面（日次報告）のURLを組み立てる。

    引数:
        port: サーバの待ち受けポート。
        target_date: 記録する日付（論理的な本日）。

    返り値:
        記録画面のURL。

    使用例:
        >>> import datetime as dt
        >>> daily_report_url(8100, dt.date(2026, 9, 13))
        'http://127.0.0.1:8100/records/2026-09-13/report'
    """
    return app_url(port, DAILY_REPORT_PATH_TEMPLATE.format(date=target_date.isoformat()))


def open_app(port: int) -> None:
    """既定のブラウザでトップ画面を開く。"""
    logger.info("ブラウザで画面を開きます: port=%s", port)
    webbrowser.open(app_url(port))


def open_daily_report(port: int, target_date: dt.date) -> None:
    """既定のブラウザで記録画面を開く（通知のクリックから呼ばれる）。"""
    logger.info("ブラウザで記録画面を開きます: date=%s", target_date)
    webbrowser.open(daily_report_url(port, target_date))
