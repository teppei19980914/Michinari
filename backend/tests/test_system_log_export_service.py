"""system_log_export_service のテスト（仕様書6.14 SC-15、Phase40 診断ログ出力）。

`log_dir`を関数の既定引数として受け取れる設計のため（logging_setup.configureと同じ
パターン）、monkeypatchは不要でtmp_pathを直接渡すだけで完結させる。
"""

import datetime as dt

import pytest

from app.services import system_log_export_service
from app.services.exceptions import ValidationError


def _write_log(path, *lines: str) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestExportLogs:
    def test_filters_lines_within_the_requested_date_range(self, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        _write_log(
            log_dir / "michinari.log",
            "2026-09-20 09:00:00,000 INFO     [-] app: 範囲外の行(前)",
            "2026-09-22 09:00:00,000 INFO     [abc123] app: 範囲内の行",
            "2026-09-25 09:00:00,000 INFO     [-] app: 範囲外の行(後)",
        )

        result = system_log_export_service.export_logs(
            dt.date(2026, 9, 21), dt.date(2026, 9, 23), log_dir=log_dir
        )

        assert "範囲内の行" in result
        assert "範囲外の行(前)" not in result
        assert "範囲外の行(後)" not in result

    def test_keeps_continuation_lines_with_their_primary_line(self, tmp_path):
        """スタックトレース等、行頭にタイムスタンプが無い継続行は直前の主行に従う。"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        _write_log(
            log_dir / "michinari.log",
            "2026-09-22 09:00:00,000 ERROR    [-] app: 未分類の例外を捕捉しました",
            "Traceback (most recent call last):",
            '  File "app.py", line 1, in <module>',
            "2026-09-25 09:00:00,000 INFO     [-] app: 範囲外の行",
            "この行も範囲外の主行に従うため除外される",
        )

        result = system_log_export_service.export_logs(
            dt.date(2026, 9, 22), dt.date(2026, 9, 22), log_dir=log_dir
        )

        assert "未分類の例外を捕捉しました" in result
        assert "Traceback" in result
        assert "app.py" in result
        assert "範囲外の行" not in result
        assert "この行も範囲外の主行に従うため除外される" not in result

    def test_combines_rotated_generations_in_chronological_order(self, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        _write_log(
            log_dir / "michinari.log.2",
            "2026-09-21 08:00:00,000 INFO     [-] app: 最古世代",
        )
        _write_log(
            log_dir / "michinari.log.1",
            "2026-09-22 08:00:00,000 INFO     [-] app: 直前世代",
        )
        _write_log(
            log_dir / "michinari.log",
            "2026-09-23 08:00:00,000 INFO     [-] app: 最新",
        )

        result = system_log_export_service.export_logs(
            dt.date(2026, 9, 21), dt.date(2026, 9, 23), log_dir=log_dir
        )

        assert result.index("最古世代") < result.index("直前世代") < result.index("最新")

    def test_missing_generation_files_are_skipped(self, tmp_path):
        """一部の世代ファイルが存在しなくても（ローテーション直後等）エラーにしない。"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        _write_log(
            log_dir / "michinari.log",
            "2026-09-23 08:00:00,000 INFO     [-] app: 最新のみ存在",
        )

        result = system_log_export_service.export_logs(
            dt.date(2026, 9, 23), dt.date(2026, 9, 23), log_dir=log_dir
        )

        assert "最新のみ存在" in result

    def test_returns_empty_string_when_no_matching_logs(self, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        _write_log(
            log_dir / "michinari.log",
            "2026-09-01 08:00:00,000 INFO     [-] app: 対象外",
        )

        result = system_log_export_service.export_logs(
            dt.date(2026, 9, 23), dt.date(2026, 9, 23), log_dir=log_dir
        )

        assert result == ""

    def test_returns_empty_string_when_log_dir_does_not_exist(self, tmp_path):
        result = system_log_export_service.export_logs(
            dt.date(2026, 9, 23), dt.date(2026, 9, 23), log_dir=tmp_path / "no-such-dir"
        )

        assert result == ""

    def test_rejects_date_to_before_date_from(self, tmp_path):
        with pytest.raises(ValidationError):
            system_log_export_service.export_logs(
                dt.date(2026, 9, 23), dt.date(2026, 9, 20), log_dir=tmp_path
            )
