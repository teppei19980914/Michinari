"""常駐アプリとしての起動・停止の取りまとめ（Phase37）。

役割分担は次のとおり。

```
メインスレッド : ログ設定 → DB準備 → サーバスレッド起動 → 通知の準備 → トレイ表示（ここで待機）
サーバスレッド : uvicorn（FastAPI・フロントエンドの静的配信）
監視スレッド   : 記録リマインドの時刻監視（app/desktop/scheduler.py）
```

**Webサーバをメインスレッドから外してある**のは、`pystray`の`Icon.run()`がメインスレッドを
要求するためである（`app/desktop/tray.py`参照）。uvicornは非メインスレッドで動かしても
問題ない。シグナル捕捉は「メインスレッドでなければ何もしない」と実装されているため
（`uvicorn/server.py`の`capture_signals`）、こちらから無効化する必要もない。

「終了」では`Server.should_exit`を立てる。uvicornはこれを受けて新規接続を止め、処理中の
リクエストと実行中のタスクの完了を待ってから停止する（`uvicorn/server.py`の`shutdown`）。
待ち時間の上限は`app_setting`の`server.graceful_shutdown_seconds`で決める。**DBへの書き込みが
途中で打ち切られないのはこの仕組みによる。**
"""

from __future__ import annotations

import ctypes
import logging
import sys
import threading
import time
from pathlib import Path

import uvicorn

from app.constants import locale_keys
from app.constants.app_setting_keys import (
    DESKTOP_LAUNCH_AT_LOGIN,
    DESKTOP_OPEN_BROWSER_ON_STARTUP,
    SERVER_GRACEFUL_SHUTDOWN_SECONDS,
)
from app.constants.desktop import BIND_HOST
from app.database import SessionLocal
from app.desktop import assets, autostart, browser, logging_setup, scheduler, tray
from app.desktop.notifier import ToastNotifier
from app.locales import t
from app.services import notification_service, setting_reader

logger = logging.getLogger(__name__)

#: サーバが待ち受けを始めるまで待つ上限と間隔（秒）。DBのマイグレーションは先に済ませて
#: いるため、ここで待つのはソケットの待ち受け開始だけであり、長くはかからない。
#: `server.graceful_shutdown_seconds`と違って`app_setting`へ出さないのは、これが利用者の
#: 好みで調整する待ち時間ではなく、「起動できたか」を見切るための実装上の上限だからである
#: （設定できるようにすると、短くしすぎて正常な起動まで失敗と判定できてしまう）。
SERVER_STARTUP_TIMEOUT_SECONDS = 30.0
SERVER_STARTUP_INTERVAL_SECONDS = 0.1

#: `MessageBoxW`のフラグ（MB_OK | MB_ICONERROR）。起動失敗をダイアログで知らせるときに使う。
_MESSAGE_BOX_ERROR_FLAGS = 0x00000010


def show_error_dialog(detail: str, log_path: Path) -> None:  # pragma: no cover (GUI表示のため)
    """起動失敗をダイアログで知らせる。

    コンソールを表示しなくなったため、従来`Michinari.bat`の`pause`が担っていた
    「何が起きたかを利用者に伝える」役割をここが引き継ぐ。黙って終了すると、利用者には
    「ダブルクリックしても何も起きない」としか見えない。

    引数:
        detail: 失敗の内容（例外の文字列）。
        log_path: 詳しい記録の場所。
    """
    ctypes.windll.user32.MessageBoxW(
        None,
        t(locale_keys.STARTUP_ERROR_BODY, detail=detail, logPath=str(log_path)),
        t(locale_keys.STARTUP_ERROR_TITLE),
        _MESSAGE_BOX_ERROR_FLAGS,
    )


class ServerThread:
    """uvicornを別スレッドで動かし、行儀よく止められるようにする薄いラッパ。

    使用例:
        >>> server = ServerThread(app, port=8100, graceful_shutdown_seconds=10)  # doctest: +SKIP
        >>> server.start()  # doctest: +SKIP
        >>> server.stop()  # doctest: +SKIP
    """

    def __init__(self, app: object, *, port: int, graceful_shutdown_seconds: int) -> None:
        """
        引数:
            app: ASGIアプリケーション（`app.main.app`）。
            port: 待ち受けポート。
            graceful_shutdown_seconds: 処理中のリクエストの完了を待つ上限秒数。
        """
        self._config = uvicorn.Config(
            app,
            host=BIND_HOST,
            port=port,
            # uvicorn既定のログ設定は標準出力へ書く。コンソールが無い実行形態では
            # 書き込みに失敗しうるため設定させず、こちらのファイル出力へ相乗りさせる
            # （None を渡すと uvicorn は dictConfig を呼ばない。uvicorn/config.py参照）。
            log_config=None,
            timeout_graceful_shutdown=graceful_shutdown_seconds,
        )
        self._server = uvicorn.Server(self._config)
        # デーモンにしないのは、停止処理（処理中のリクエストの完了待ち）を必ず終えてから
        # プロセスを終わらせるため。
        self._thread = threading.Thread(target=self._server.run, name="uvicorn-server")

    def start(self) -> None:
        """サーバスレッドを開始し、待ち受けが始まるまで待つ。

        送出する例外の文言をロケールから引くのは、**これが起動失敗ダイアログの本文として
        そのまま画面に出る**ためである（`app/main.py`の`main`が`str(error)`を
        `show_error_dialog`へ渡す）。とりわけポートの重複は、常駐アプリを二重に起動した
        ときに最も起きやすい失敗である。

        例外:
            RuntimeError: 制限時間内に待ち受けが始まらなかった場合。
        """
        self._thread.start()
        deadline = time.monotonic() + SERVER_STARTUP_TIMEOUT_SECONDS
        while not self._server.started:
            if not self._thread.is_alive():
                raise RuntimeError(t(locale_keys.STARTUP_ERROR_SERVER_START_FAILED))
            if time.monotonic() >= deadline:
                raise RuntimeError(t(locale_keys.STARTUP_ERROR_SERVER_NOT_RESPONDING))
            time.sleep(SERVER_STARTUP_INTERVAL_SECONDS)
        logger.info("サーバの待ち受けを開始しました: port=%s", self._config.port)

    def stop(self) -> None:
        """サーバへ停止を要求し、完全に止まるまで待つ。"""
        logger.info("サーバの停止を要求します")
        self._server.should_exit = True
        self._thread.join()
        logger.info("サーバが停止しました")


def _read_bool_setting(key: str, *, default: bool) -> bool:
    """`app_setting`の真偽値を読み出す（読めない場合も起動を止めない）。"""
    session = SessionLocal()
    try:
        return setting_reader.get_bool(session, key)
    except Exception:
        logger.exception("設定を読み出せませんでした。既定値で継続します: key=%s", key)
        return default
    finally:
        session.close()


def _read_graceful_shutdown_seconds() -> int:
    """終了時の待ち時間の上限（秒）を`app_setting`から読み出す。"""
    session = SessionLocal()
    try:
        return setting_reader.get_int(session, SERVER_GRACEFUL_SHUTDOWN_SECONDS)
    finally:
        session.close()


def build_notify_callback(notifier: ToastNotifier, port: int):
    """判定結果を受け取ってトーストを出す処理を組み立てる。

    文面はロケールキーから解決し、クリックされたらその日の記録画面を開く。ここは
    「判定（notification_service）」「通知の表示（notifier）」「画面のURL（browser）」を
    結ぶ唯一の場所であり、取り違えても各部品のテストでは捕まらないため、この関数自体を
    テストする。
    """

    def notify(decision: notification_service.NotificationDecision) -> None:
        title_key, body_key = decision.message_keys()
        notifier.show(
            t(title_key),
            t(body_key),
            on_click=lambda: browser.open_daily_report(port, decision.logical_date),
        )

    return notify


def run(app: object, port: int) -> int:  # pragma: no cover (常駐起動のためユニットテスト対象外)
    """常駐アプリとして起動し、「終了」が選ばれるまで待機する。

    引数:
        app: ASGIアプリケーション。
        port: 待ち受けポート（`app_setting`の`server.port`）。

    返り値:
        プロセスの終了コード（正常終了なら0）。
    """
    autostart.apply(_read_bool_setting(DESKTOP_LAUNCH_AT_LOGIN, default=False))

    server = ServerThread(
        app, port=port, graceful_shutdown_seconds=_read_graceful_shutdown_seconds()
    )
    server.start()

    if _read_bool_setting(DESKTOP_OPEN_BROWSER_ON_STARTUP, default=True):
        browser.open_app(port)

    icon_path = assets.resolve_icon_path()
    notifier = ToastNotifier(t(locale_keys.NOTIFICATION_SOURCE_NAME), icon_path)
    reminder = scheduler.ReminderScheduler(build_notify_callback(notifier, port))
    reminder.start()

    def quit_app() -> None:
        # `icon`はこの関数の定義より後で束縛されるが、実際に呼ばれるのはメニューが
        # 操作されたとき（＝`icon.run()`の後）なので必ず束縛済みである。
        icon.stop()

    icon = tray.build_icon(
        on_open=lambda: browser.open_app(port), on_quit=quit_app, icon_path=icon_path
    )
    logger.info("通知領域へ常駐します")
    icon.run()  # 「終了」でicon.stop()が呼ばれるまでここで待機する。

    logger.info("終了処理を開始します")
    reminder.stop()
    server.stop()
    return 0


#: 開発者・障害調査向けの起動オプション。配布する実行ファイルはコンソールを持たないが、
#: この指定があれば実行時にコンソールを割り当ててログを流す（`logging_setup.attach_console`）。
#: 別に「コンソール版の実行ファイル」をビルドしない理由は、PyInstallerの同梱物一式が
#: もう1組できて配布物の大きさが倍増するためである。
CONSOLE_OPTION = "--console"


def bootstrap_logging(argv: list[str] | None = None) -> Path:
    """標準出力の差し替えとログ設定を行う（起動の一番最初に呼ぶ）。

    引数:
        argv: コマンドライン引数（既定は`sys.argv`）。`--console`が含まれる場合は
            コンソールを開いてログをそこへも流す。

    返り値:
        ログファイルのパス。
    """
    logging_setup.ensure_standard_streams()
    wants_console = CONSOLE_OPTION in (sys.argv if argv is None else argv)
    to_console = logging_setup.attach_console() if wants_console else False
    return logging_setup.configure(to_console=to_console)
