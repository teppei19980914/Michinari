"""logging_setup のテスト（コンソールの無い実行形態への備え、Phase37）。

`--noconsole`でビルドした実行ファイルでは`sys.stdout`/`sys.stderr`が`None`になる
（PyInstaller公式）。この状態で標準出力へ書こうとするとアプリが落ちるため、差し替えと
ログのファイル出力が確実に行われることを確かめる。ログはコンソールが無い環境で唯一の
障害調査の手がかりでもある。
"""

import logging

import pytest

from app.constants.desktop import LOG_BACKUP_COUNT, LOG_FILE_NAME, LOG_MAX_BYTES
from app.desktop import logging_setup


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


class TestEnsureStandardStreams:
    def test_replaces_none_stdout_and_stderr(self, monkeypatch: pytest.MonkeyPatch):
        """`None`のままだと`sys.stderr.flush`等で落ちるため、書ける対象へ差し替えること。"""
        monkeypatch.setattr(logging_setup.sys, "stdout", None)
        monkeypatch.setattr(logging_setup.sys, "stderr", None)

        logging_setup.ensure_standard_streams()

        assert logging_setup.sys.stdout is not None
        assert logging_setup.sys.stderr is not None
        # 書き込んでも例外にならないことまで確かめる（差し替えの目的がこれであるため）。
        logging_setup.sys.stdout.write("x")
        logging_setup.sys.stderr.flush()

    def test_keeps_existing_streams(self, monkeypatch: pytest.MonkeyPatch):
        """既に使える標準出力がある場合（ソースからの起動）は奪わないこと。"""
        sentinel = object()
        monkeypatch.setattr(logging_setup.sys, "stdout", sentinel)
        monkeypatch.setattr(logging_setup.sys, "stderr", sentinel)

        logging_setup.ensure_standard_streams()

        assert logging_setup.sys.stdout is sentinel
        assert logging_setup.sys.stderr is sentinel


class TestResolveLogPath:
    def test_places_the_file_in_the_given_directory(self, tmp_path):
        assert logging_setup.resolve_log_path(tmp_path) == tmp_path / LOG_FILE_NAME


class TestConfigure:
    def test_creates_the_directory_and_writes_to_the_file(self, tmp_path):
        log_dir = tmp_path / "logs"

        log_path = logging_setup.configure(log_dir)
        logging.getLogger(__name__).info("テスト出力")
        for handler in logging.getLogger().handlers:
            handler.flush()

        assert log_path == log_dir / LOG_FILE_NAME
        assert "テスト出力" in log_path.read_text(encoding="utf-8")

    def test_replaces_existing_handlers(self, tmp_path):
        """標準出力向けのハンドラが残ると、コンソールの無い環境で書き込みに失敗しうる。"""
        root = logging.getLogger()
        root.addHandler(logging.StreamHandler())

        logging_setup.configure(tmp_path)

        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0], logging.handlers.RotatingFileHandler)

    def test_rotates_with_the_configured_limits(self, tmp_path):
        logging_setup.configure(tmp_path)

        handler = logging.getLogger().handlers[0]
        assert handler.maxBytes == LOG_MAX_BYTES
        assert handler.backupCount == LOG_BACKUP_COUNT

    def test_adds_a_console_handler_when_requested(self, tmp_path):
        """開発者向けの`--console`でログが画面にも流れること。"""
        logging_setup.configure(tmp_path, to_console=True)

        handlers = logging.getLogger().handlers
        assert len(handlers) == 2
        assert any(
            isinstance(handler, logging.StreamHandler)
            and not isinstance(handler, logging.FileHandler)
            for handler in handlers
        )

    def test_applies_the_requested_level(self, tmp_path):
        logging_setup.configure(tmp_path, level=logging.WARNING)

        assert logging.getLogger().level == logging.WARNING


class TestPreserveLoggingState:
    """alembicの`fileConfig()`による副作用（ハンドラ差し替え・`disabled`化）からの復元。"""

    def test_restores_handlers_and_level(self):
        """pytest自体がルートロガーへハンドラを付けているため、`with`直前の状態
        （既存ハンドラを含む）を基準に、追加分だけが元へ戻ることを確かめる。
        """
        root = logging.getLogger()
        handlers_before = list(root.handlers)
        level_before = root.level
        extra_handler = logging.StreamHandler()
        try:
            with logging_setup.preserve_logging_state():
                root.addHandler(extra_handler)
                root.setLevel(logging.CRITICAL)

            assert root.handlers == handlers_before
            assert root.level == level_before
        finally:
            root.removeHandler(extra_handler)

    def test_restores_the_disabled_flag_for_a_logger_present_at_restore(self):
        """`fileConfig()`が既存ロガーを`disabled=True`にする副作用を模し、元へ戻ること。"""
        logger_obj = logging.getLogger("michinari.test.preserve_logging_state.kept")
        logger_obj.disabled = False

        with logging_setup.preserve_logging_state():
            logger_obj.disabled = True

        assert logger_obj.disabled is False

    def test_skips_restore_for_a_logger_removed_during_the_block(self):
        """スナップショット後に対象ロガーが`loggerDict`から消えていても例外にしないこと
        （復元時点で`logging.Logger`でなければ復元をスキップする分岐）。
        """
        logger_name = "michinari.test.preserve_logging_state.removed"
        logging.getLogger(logger_name).disabled = False
        root = logging.getLogger()

        with logging_setup.preserve_logging_state():
            del root.manager.loggerDict[logger_name]

        assert logger_name not in root.manager.loggerDict
