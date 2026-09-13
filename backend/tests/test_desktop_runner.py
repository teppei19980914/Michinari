"""runner のテスト（常駐起動の組み立て、Phase37）。

実際のサーバ起動・トレイ表示・ブラウザ起動は対象外（`pragma: no cover`）とし、その周りの
判断を検証する。

- uvicornへ渡す設定（標準出力へログを書かせないこと・終了時の待ち時間）
- 設定の読み出しが失敗しても起動を止めないこと
- `--console`の有無でログの出力先が変わること
"""

import datetime as dt
import logging
import socket
import threading

import pytest

from app import main as main_module
from app.constants import locale_keys
from app.constants.app_setting_keys import (
    DESKTOP_LAUNCH_AT_LOGIN,
    SERVER_GRACEFUL_SHUTDOWN_SECONDS,
)
from app.constants.desktop import BIND_HOST
from app.desktop import runner
from app.locales import t
from app.models.setting import AppSetting
from app.services import notification_service


@pytest.fixture(autouse=True)
def _restore_root_logger():
    """テストがルートロガーを書き換えるため、前後の状態を保存・復元する。"""
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    yield
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    for handler in original_handlers:
        root.addHandler(handler)
    root.setLevel(original_level)


@pytest.fixture
def app_session(seeded_session, monkeypatch: pytest.MonkeyPatch):
    """runnerが内部で開くセッションをテスト用セッションへ差し替える。"""

    class _Proxy:
        def __getattr__(self, name: str):
            return getattr(seeded_session, name)

        def close(self) -> None:
            return None

    monkeypatch.setattr(runner, "SessionLocal", lambda: _Proxy())
    return seeded_session


class TestServerThread:
    def test_does_not_let_uvicorn_configure_logging(self):
        """uvicorn既定のログ設定は標準出力へ書く。コンソールの無い実行形態では危険なため、
        設定させずにこちらのファイル出力へ相乗りさせること。"""
        server = runner.ServerThread(object(), port=8123, graceful_shutdown_seconds=10)

        assert server._config.log_config is None

    def test_passes_the_graceful_shutdown_timeout(self):
        """「終了」時に処理中の書き込みの完了を待つ上限が設定へ伝わること。"""
        server = runner.ServerThread(object(), port=8123, graceful_shutdown_seconds=42)

        assert server._config.timeout_graceful_shutdown == 42

    def test_listens_on_the_given_port(self):
        server = runner.ServerThread(object(), port=8123, graceful_shutdown_seconds=10)

        assert server._config.port == 8123

    def test_uses_a_non_daemon_thread_so_shutdown_completes(self):
        """停止処理（処理中のリクエストの完了待ち）を終えてからプロセスを終わらせること。"""
        server = runner.ServerThread(object(), port=8123, graceful_shutdown_seconds=10)

        assert not server._thread.daemon


class TestReadSettings:
    def test_reads_a_boolean_setting(self, app_session):
        app_session.get(AppSetting, DESKTOP_LAUNCH_AT_LOGIN).value = "true"
        app_session.flush()

        assert runner._read_bool_setting(DESKTOP_LAUNCH_AT_LOGIN, default=False) is True

    def test_falls_back_when_the_setting_is_missing(self, app_session):
        """設定が読めないだけで起動を止めないこと（既定値で続行する）。"""
        assert runner._read_bool_setting("desktop.does_not_exist", default=True) is True

    def test_reads_the_graceful_shutdown_seconds(self, app_session):
        app_session.get(AppSetting, SERVER_GRACEFUL_SHUTDOWN_SECONDS).value = "25"
        app_session.flush()

        assert runner._read_graceful_shutdown_seconds() == 25


class TestBootstrapLogging:
    def test_writes_to_the_log_file_without_a_console(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ):
        """通常起動（オプション無し）ではコンソールへ出さないこと。"""
        recorded: dict = {}
        monkeypatch.setattr(
            runner.logging_setup,
            "configure",
            lambda **kwargs: (recorded.update(kwargs), tmp_path / "michinari.log")[1],
        )

        runner.bootstrap_logging(argv=["Michinari.exe"])

        assert recorded == {"to_console": False}

    def test_opens_a_console_when_the_option_is_given(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ):
        """`--console`付きの起動で、ログが画面にも流れる設定になること。"""
        recorded: dict = {}
        monkeypatch.setattr(runner.logging_setup, "attach_console", lambda: True)
        monkeypatch.setattr(
            runner.logging_setup,
            "configure",
            lambda **kwargs: (recorded.update(kwargs), tmp_path / "michinari.log")[1],
        )

        runner.bootstrap_logging(argv=["Michinari.exe", runner.CONSOLE_OPTION])

        assert recorded == {"to_console": True}

    def test_stays_file_only_when_the_console_cannot_be_opened(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ):
        """コンソールを出せない環境でも起動を続けられること。"""
        recorded: dict = {}
        monkeypatch.setattr(runner.logging_setup, "attach_console", lambda: False)
        monkeypatch.setattr(
            runner.logging_setup,
            "configure",
            lambda **kwargs: (recorded.update(kwargs), tmp_path / "michinari.log")[1],
        )

        runner.bootstrap_logging(argv=["Michinari.exe", runner.CONSOLE_OPTION])

        assert recorded == {"to_console": False}

    def test_replaces_missing_standard_streams(self, tmp_path, monkeypatch: pytest.MonkeyPatch):
        """`--noconsole`で`None`になる標準出力が差し替わること（PyInstaller公式の対処）。"""
        monkeypatch.setattr(runner.logging_setup.sys, "stdout", None)
        monkeypatch.setattr(runner.logging_setup.sys, "stderr", None)
        monkeypatch.setattr(
            runner.logging_setup, "configure", lambda **_kwargs: tmp_path / "michinari.log"
        )

        runner.bootstrap_logging(argv=["Michinari.exe"])

        assert runner.logging_setup.sys.stdout is not None
        assert runner.logging_setup.sys.stderr is not None


class TestServerThreadLifecycle:
    """実際にポートを開いて起動・停止まで通す（Phase37）。

    「終了」を選んでもプロセスが残る、という不具合はユニットテストの組み立て検証では
    捕まらない。uvicornのサーバスレッドは**デーモンではない**ため、`should_exit`が効かず
    スレッドが終わらなければプロセスは永久に残る（利用者からは「終了できない」「タスク
    マネージャーに残り続ける」と見える）。ここだけは実際に起動して停止まで確かめる。

    ポートはOSに空きを割り当てさせるため、利用者が起動中のアプリ（既定8100番）とは
    衝突しない。
    """

    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def test_starts_serving_and_stops_without_leaving_the_thread_alive(self):
        async def _app(scope, receive, send):  # pragma: no cover (起動確認用の最小ASGIアプリ)
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        server = runner.ServerThread(_app, port=self._free_port(), graceful_shutdown_seconds=5)
        server.start()
        assert server._thread.is_alive()

        server.stop()

        assert not server._thread.is_alive()


class TestServerThreadStartFailures:
    """起動できなかったときに、利用者へ何が起きたかを伝えられること（Phase37）。

    ダイアログに出る文言をここが決めている。黙って終了すると、利用者には
    「ダブルクリックしても何も起きない」としか映らない。

    失敗の作り方を実際のポート重複にしないのは、**Windowsでは既に待ち受け中のポートへの
    bindがそのまま成功してしまう**ためである（Linuxのように`EADDRINUSE`にならない）。
    OSの挙動に依存せず「サーバスレッドが落ちた」「時間内に待ち受けが始まらない」の2状態を
    直接作って検証する。
    """

    @staticmethod
    def _server(monkeypatch: pytest.MonkeyPatch, *, alive: bool) -> runner.ServerThread:
        """起動しないサーバスレッドを作る（実際のソケットは開かない）。"""
        monkeypatch.setattr(runner, "SERVER_STARTUP_TIMEOUT_SECONDS", 0.05)
        monkeypatch.setattr(runner, "SERVER_STARTUP_INTERVAL_SECONDS", 0.01)
        server = runner.ServerThread(object(), port=8123, graceful_shutdown_seconds=5)
        monkeypatch.setattr(server._thread, "start", lambda: None)
        monkeypatch.setattr(server._thread, "is_alive", lambda: alive)
        return server

    def test_reports_a_server_thread_that_died(self, monkeypatch: pytest.MonkeyPatch):
        """サーバスレッドが落ちた場合、ロケールの文言で失敗を知らせること。"""
        server = self._server(monkeypatch, alive=False)

        with pytest.raises(RuntimeError) as error:
            server.start()

        assert str(error.value) == t(locale_keys.STARTUP_ERROR_SERVER_START_FAILED)
        # キー文字列がそのまま出ていないこと（ロケール未解決の取りこぼし検出）。
        assert str(error.value) != locale_keys.STARTUP_ERROR_SERVER_START_FAILED

    def test_reports_a_server_that_never_starts_listening(self, monkeypatch: pytest.MonkeyPatch):
        """制限時間を過ぎても待ち受けが始まらない場合を知らせること。"""
        server = self._server(monkeypatch, alive=True)

        with pytest.raises(RuntimeError) as error:
            server.start()

        assert str(error.value) == t(locale_keys.STARTUP_ERROR_SERVER_NOT_RESPONDING)
        assert str(error.value) != locale_keys.STARTUP_ERROR_SERVER_NOT_RESPONDING

    def test_binds_to_every_interface(self):
        """待ち受けホストが定数から来ていること（main.pyからの移設で変わっていないこと）。"""
        server = runner.ServerThread(object(), port=8123, graceful_shutdown_seconds=5)

        assert server._config.host == BIND_HOST


class TestBuildNotifyCallback:
    """判定・通知・画面URLを結ぶ繋ぎ目（Phase37）。

    各部品には個別のテストがあるが、取り違え（見出しと本文の逆転、開く日付の間違い）は
    この関数でしか捕まらない。
    """

    class _FakeNotifier:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []
            self.on_click = None

        def show(self, title: str, body: str, on_click=None) -> None:
            self.calls.append((title, body))
            self.on_click = on_click

    @staticmethod
    def _decision(**overrides):
        defaults = {
            "should_notify": True,
            "logical_date": dt.date(2026, 9, 13),
            "title_key": locale_keys.NOTIFICATION_PLAN_TITLE,
            "body_key": locale_keys.NOTIFICATION_PLAN_BODY,
        }
        return notification_service.NotificationDecision(**{**defaults, **overrides})

    def test_resolves_the_wording_from_the_locale(self):
        notifier = self._FakeNotifier()

        runner.build_notify_callback(notifier, 8100)(self._decision())

        assert notifier.calls == [
            (t(locale_keys.NOTIFICATION_PLAN_TITLE), t(locale_keys.NOTIFICATION_PLAN_BODY))
        ]

    def test_uses_the_buffer_wording_when_the_decision_says_so(self):
        notifier = self._FakeNotifier()

        runner.build_notify_callback(notifier, 8100)(
            self._decision(
                title_key=locale_keys.NOTIFICATION_BUFFER_TITLE,
                body_key=locale_keys.NOTIFICATION_BUFFER_BODY,
            )
        )

        assert notifier.calls == [
            (t(locale_keys.NOTIFICATION_BUFFER_TITLE), t(locale_keys.NOTIFICATION_BUFFER_BODY))
        ]

    def test_clicking_opens_the_record_screen_for_that_logical_date(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """通知の日付ではなく「今日」を開いてしまう退化を防ぐ。"""
        opened: list[str] = []
        monkeypatch.setattr(runner.browser.webbrowser, "open", opened.append)
        notifier = self._FakeNotifier()

        runner.build_notify_callback(notifier, 9999)(
            self._decision(logical_date=dt.date(2026, 1, 5))
        )
        notifier.on_click()

        assert opened == ["http://127.0.0.1:9999/records/2026-01-05/report"]


class TestBootstrapLoggingOrder:
    """標準出力の差し替えが、ログ設定より**先**に行われること（Phase37）。

    順序が逆転すると、`--noconsole`ビルドではログ設定の時点で標準出力へ触れて落ちる
    （`logging_setup`のdocstringが「ログ設定より先に、起動の一番最初に呼ぶこと」と
    強調している要件）。kwargsだけを見るテストでは順序の逆転を検出できない。
    """

    def test_replaces_streams_before_configuring_logging(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ):
        order: list[str] = []
        monkeypatch.setattr(
            runner.logging_setup,
            "ensure_standard_streams",
            lambda: order.append("ensure_standard_streams"),
        )
        monkeypatch.setattr(
            runner.logging_setup,
            "configure",
            lambda **_kwargs: (order.append("configure"), tmp_path / "michinari.log")[1],
        )

        runner.bootstrap_logging(argv=["Michinari.exe"])

        assert order == ["ensure_standard_streams", "configure"]


class TestMain:
    """プロセスの入口（`app/main.py` の `main`）の振る舞い（Phase37）。

    起動に失敗したときにダイアログを出さずに終了すると、利用者には「ダブルクリックしても
    何も起きない」としか映らない。Phase37が潰そうとした事象そのものであるため検証する。
    """

    @pytest.fixture(autouse=True)
    def _stub_bootstrap(self, tmp_path, monkeypatch: pytest.MonkeyPatch):
        self.log_path = tmp_path / "michinari.log"
        monkeypatch.setattr(main_module.desktop_runner, "bootstrap_logging", lambda: self.log_path)
        self.dialogs: list[tuple[str, object]] = []
        monkeypatch.setattr(
            main_module.desktop_runner,
            "show_error_dialog",
            lambda detail, log_path: self.dialogs.append((detail, log_path)),
        )
        self.ai_tasks: list[bool] = []
        monkeypatch.setattr(main_module, "run_ai_startup_tasks", lambda: self.ai_tasks.append(True))

    def test_returns_the_runner_exit_code_on_a_normal_run(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(main_module, "resolve_startup_port", lambda: 8100)
        monkeypatch.setattr(main_module.desktop_runner, "run", lambda _app, _port: 0)

        assert main_module.main() == 0
        assert self.dialogs == []

    def test_passes_the_resolved_port_to_the_runner(self, monkeypatch: pytest.MonkeyPatch):
        received: list[int] = []
        monkeypatch.setattr(main_module, "resolve_startup_port", lambda: 9999)
        monkeypatch.setattr(
            main_module.desktop_runner, "run", lambda _app, port: (received.append(port), 0)[1]
        )

        main_module.main()

        assert received == [9999]

    def test_shows_a_dialog_when_the_database_cannot_be_prepared(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        def _fail() -> int:
            raise RuntimeError("マイグレーションに失敗しました")

        monkeypatch.setattr(main_module, "resolve_startup_port", _fail)

        assert main_module.main() == main_module.STARTUP_FAILURE_EXIT_CODE
        assert self.dialogs == [("マイグレーションに失敗しました", self.log_path)]

    def test_shows_a_dialog_when_the_server_cannot_start(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(main_module, "resolve_startup_port", lambda: 8100)

        def _fail(_app, _port) -> int:
            raise RuntimeError("サーバを起動できません")

        monkeypatch.setattr(main_module.desktop_runner, "run", _fail)

        assert main_module.main() == main_module.STARTUP_FAILURE_EXIT_CODE
        assert self.dialogs == [("サーバを起動できません", self.log_path)]

    def test_runs_the_ai_startup_tasks_without_blocking_startup(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """AI連携は応答待ちが長いため、画面が開くのを待たせないこと（デーモンスレッド）。"""
        threads: list[threading.Thread] = []
        original = main_module.Thread

        def _capture(*args, **kwargs):
            thread = original(*args, **kwargs)
            threads.append(thread)
            return thread

        monkeypatch.setattr(main_module, "Thread", _capture)
        monkeypatch.setattr(main_module, "resolve_startup_port", lambda: 8100)
        monkeypatch.setattr(main_module.desktop_runner, "run", lambda _app, _port: 0)

        main_module.main()
        for thread in threads:
            thread.join(timeout=5)

        assert [thread.daemon for thread in threads] == [True]
        assert self.ai_tasks == [True]

    def test_does_not_start_the_ai_tasks_when_startup_already_failed(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        def _fail() -> int:
            raise RuntimeError("失敗")

        monkeypatch.setattr(main_module, "resolve_startup_port", _fail)

        main_module.main()

        assert self.ai_tasks == []
