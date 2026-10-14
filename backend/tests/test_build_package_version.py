"""配布パッケージビルドスクリプトのうち、配布バージョンの読み書き/確定
（read_current_version/write_version/resolve_version）・uv.lock同期（sync_lock_file）の
テスト（scripts/build_package.py参照）。実装フェーズ分割計画書S02、test_build_package.py
からの分割（決定事項S7）。
"""

import subprocess
from pathlib import Path

import build_package
import pytest
from build_package import read_current_version, resolve_version, sync_lock_file, write_version


def test_read_current_version_reads_pyproject_project_version(tmp_path: Path) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        '[project]\nname = "michinari-backend"\nversion = "0.1.0"\n', encoding="utf-8"
    )

    assert read_current_version(pyproject_path) == "0.1.0"


def test_write_version_replaces_only_the_version_line(tmp_path: Path) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        '[project]\nname = "michinari-backend"\nversion = "0.1.0"\ndescription = "バックエンド"\n',
        encoding="utf-8",
    )

    write_version(pyproject_path, "0.2.0")

    updated = pyproject_path.read_text(encoding="utf-8")
    assert 'version = "0.2.0"' in updated
    assert 'name = "michinari-backend"' in updated
    assert 'description = "バックエンド"' in updated


def test_write_version_raises_when_version_line_is_missing(tmp_path: Path) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text('[project]\nname = "michinari-backend"\n', encoding="utf-8")

    with pytest.raises(ValueError):
        write_version(pyproject_path, "0.2.0")


def test_sync_lock_file_succeeds_on_first_try(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`write_version`の直後にuv.lockを追従させる（2026-09-19、1.7.1リリースで
    uv.lockの追従漏れが発覚した不具合の再発防止）。"""
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(build_package.subprocess, "run", fake_run)
    sleep_calls: list[float] = []
    monkeypatch.setattr(build_package.time, "sleep", sleep_calls.append)

    sync_lock_file(tmp_path)

    assert calls == [["uv", "lock"]]
    assert sleep_calls == []


def test_sync_lock_file_retries_after_transient_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OneDriveロックのような一時的な失敗の後に成功すれば例外を送出しない
    （discard_previous_packageと同じ再試行方針、CLAUDE.md DRYの原則）。"""
    call_count = 0

    def flaky_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="locked")
        return subprocess.CompletedProcess(args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(build_package.subprocess, "run", flaky_run)
    sleep_calls: list[float] = []
    monkeypatch.setattr(build_package.time, "sleep", sleep_calls.append)

    sync_lock_file(tmp_path)

    assert call_count == 3
    assert sleep_calls == [build_package.RMTREE_RETRY_DELAY_SECONDS] * 2


def test_sync_lock_file_raises_when_all_retries_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    call_count = 0

    def always_fail_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="locked")

    monkeypatch.setattr(build_package.subprocess, "run", always_fail_run)
    monkeypatch.setattr(build_package.time, "sleep", lambda _seconds: None)

    with pytest.raises(SystemExit, match="uv.lock"):
        sync_lock_file(tmp_path)

    assert call_count == build_package.RMTREE_RETRY_ATTEMPTS


def test_resolve_version_returns_the_explicitly_entered_value(tmp_path: Path) -> None:
    inputs = iter(["0.2.0"])

    result = resolve_version("0.1.0", prompt=lambda _: next(inputs))

    assert result == "0.2.0"


def test_resolve_version_reprompts_when_input_is_blank(tmp_path: Path) -> None:
    inputs = iter(["", "   ", "0.2.0"])

    result = resolve_version("0.1.0", prompt=lambda _: next(inputs))

    assert result == "0.2.0"


def test_resolve_version_rejects_characters_unsafe_for_toml_and_filenames(tmp_path: Path) -> None:
    """バージョンはpyproject.tomlのTOML文字列・zipファイル名へそのまま埋め込まれるため、
    `"`（TOML破損）や`/`（パス区切り混入）を含む入力は拒否し再入力を求める。"""
    inputs = iter(['0.2.0" \nmalicious = "x', "../../evil", "0.2.0"])

    result = resolve_version("0.1.0", prompt=lambda _: next(inputs))

    assert result == "0.2.0"
