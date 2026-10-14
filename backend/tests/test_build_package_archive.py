"""配布パッケージビルドスクリプトのうち、既存配布物の退避（archive_previous_distributions）・
旧ビルド出力の削除（discard_previous_package）・不要な残骸フォルダの清掃
（cleanup_stale_previous_packages）・改名/削除の再試行ロジックのテスト
（scripts/build_package.py参照）。実装フェーズ分割計画書S02、test_build_package.pyからの
分割（決定事項S7）。
"""

import datetime as dt
from pathlib import Path

import build_package
import pytest
from build_package import (
    PREVIOUS_PACKAGE_PREFIX,
    _rename_with_retry,
    _rmtree_with_retry,
    archive_previous_distributions,
    cleanup_stale_previous_packages,
    discard_previous_package,
)


def test_archive_previous_distributions_returns_empty_when_dist_dir_is_absent(
    tmp_path: Path,
) -> None:
    dist_dir = tmp_path / "dist"
    archive_dir = dist_dir / "_archive"

    assert archive_previous_distributions(dist_dir, archive_dir) == []
    assert not archive_dir.exists()


def test_archive_previous_distributions_returns_empty_when_no_distribution_files(
    tmp_path: Path,
) -> None:
    """退避対象が無ければ`_archive/`を作らない（空フォルダを増やさない）。"""
    dist_dir = tmp_path / "dist"
    (dist_dir / "Michinari").mkdir(parents=True)
    (dist_dir / "Michinari" / "Michinari.exe").write_text("dummy", encoding="utf-8")

    assert archive_previous_distributions(dist_dir, dist_dir / "_archive") == []
    assert not (dist_dir / "_archive").exists()


def test_archive_previous_distributions_moves_zip_and_commit_record(tmp_path: Path) -> None:
    """zipとビルド元コミットの記録だけを退避し、ビルド出力フォルダには触れない。"""
    dist_dir = tmp_path / "dist"
    archive_dir = dist_dir / "_archive"
    dist_dir.mkdir(parents=True)
    (dist_dir / "Michinari-v1.2.2.zip").write_text("zip", encoding="utf-8")
    (dist_dir / "Michinari-v1.2.2.commit.json").write_text("{}", encoding="utf-8")
    output_dir = dist_dir / "Michinari"
    output_dir.mkdir()
    (output_dir / "Michinari.exe").write_text("exe", encoding="utf-8")

    moved = archive_previous_distributions(dist_dir, archive_dir)

    assert moved == [
        archive_dir / "Michinari-v1.2.2.commit.json",
        archive_dir / "Michinari-v1.2.2.zip",
    ]
    assert (archive_dir / "Michinari-v1.2.2.zip").read_text(encoding="utf-8") == "zip"
    assert not (dist_dir / "Michinari-v1.2.2.zip").exists()
    assert (output_dir / "Michinari.exe").read_text(encoding="utf-8") == "exe"


def test_archive_previous_distributions_keeps_earlier_versions(tmp_path: Path) -> None:
    """バージョンが異なる配布物は退避先で併存する（旧版のzipを失わない）。"""
    dist_dir = tmp_path / "dist"
    archive_dir = dist_dir / "_archive"
    dist_dir.mkdir(parents=True)
    (dist_dir / "Michinari-v1.2.1.zip").write_text("v1.2.1", encoding="utf-8")
    archive_previous_distributions(dist_dir, archive_dir)
    (dist_dir / "Michinari-v1.2.2.zip").write_text("v1.2.2", encoding="utf-8")

    archive_previous_distributions(dist_dir, archive_dir)

    assert (archive_dir / "Michinari-v1.2.1.zip").read_text(encoding="utf-8") == "v1.2.1"
    assert (archive_dir / "Michinari-v1.2.2.zip").read_text(encoding="utf-8") == "v1.2.2"


def test_archive_previous_distributions_overwrites_same_named_archive(tmp_path: Path) -> None:
    """同一バージョンで再ビルドした場合は退避先の同名ファイルを上書きする。"""
    dist_dir = tmp_path / "dist"
    archive_dir = dist_dir / "_archive"
    archive_dir.mkdir(parents=True)
    (archive_dir / "Michinari-v1.2.2.zip").write_text("old", encoding="utf-8")
    (dist_dir / "Michinari-v1.2.2.zip").write_text("new", encoding="utf-8")

    archive_previous_distributions(dist_dir, archive_dir)

    assert (archive_dir / "Michinari-v1.2.2.zip").read_text(encoding="utf-8") == "new"


def test_archive_previous_distributions_retries_rename_on_transient_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """改名（`os.rename`）が一時的に失敗しても再試行して退避を完了する

    （`discard_previous_package`と共通の`_rename_with_retry`を使うことの確認、
    CLAUDE.md DRYの原則）。"""
    dist_dir = tmp_path / "dist"
    archive_dir = dist_dir / "_archive"
    dist_dir.mkdir(parents=True)
    (dist_dir / "Michinari-v1.2.2.zip").write_text("zip", encoding="utf-8")

    real_rename = build_package.os.rename
    call_count = 0

    def flaky_rename(src: Path, dst: Path) -> None:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise PermissionError("プロセスはファイルにアクセスできません。")
        real_rename(src, dst)

    monkeypatch.setattr(build_package.os, "rename", flaky_rename)
    sleep_calls: list[float] = []
    monkeypatch.setattr(build_package.time, "sleep", sleep_calls.append)

    moved = archive_previous_distributions(dist_dir, archive_dir)

    assert moved == [archive_dir / "Michinari-v1.2.2.zip"]
    assert call_count == 3
    assert sleep_calls == [build_package.RMTREE_RETRY_DELAY_SECONDS] * 2
    assert not (dist_dir / "Michinari-v1.2.2.zip").exists()


def test_archive_previous_distributions_warns_and_continues_when_rename_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """1件の退避が再試行しても失敗した場合、その1件は`dist/`に残したまま他の対象の
    退避は継続し、ビルドは中断しない（`shutil.move`のコピー＋削除フォールバックのように
    中途半端な状態にはならないことも確認する）。
    """
    dist_dir = tmp_path / "dist"
    archive_dir = dist_dir / "_archive"
    dist_dir.mkdir(parents=True)
    (dist_dir / "Michinari-v1.2.1.zip").write_text("locked", encoding="utf-8")
    (dist_dir / "Michinari-v1.2.1.commit.json").write_text("{}", encoding="utf-8")

    real_rename = build_package.os.rename

    def rename_that_locks_only_the_zip(src: Path, dst: Path) -> None:
        if Path(src).suffix == ".zip":
            raise PermissionError("プロセスはファイルにアクセスできません。")
        real_rename(src, dst)

    monkeypatch.setattr(build_package.os, "rename", rename_that_locks_only_the_zip)
    sleep_calls: list[float] = []
    monkeypatch.setattr(build_package.time, "sleep", sleep_calls.append)

    moved = archive_previous_distributions(dist_dir, archive_dir)

    assert moved == [archive_dir / "Michinari-v1.2.1.commit.json"]
    assert (dist_dir / "Michinari-v1.2.1.zip").read_text(encoding="utf-8") == "locked"
    assert not (archive_dir / "Michinari-v1.2.1.zip").exists()
    assert "既存の配布物を退避できませんでした" in capsys.readouterr().out
    assert sleep_calls == [build_package.RMTREE_RETRY_DELAY_SECONDS] * (
        build_package.RMTREE_RETRY_ATTEMPTS - 1
    )


def test_discard_previous_package_returns_none_when_no_existing_output(tmp_path: Path) -> None:
    output_dir = tmp_path / "dist" / "Michinari"

    assert discard_previous_package(output_dir) is None
    assert not output_dir.exists()


def test_discard_previous_package_removes_existing_output(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    output_dir = dist_dir / "Michinari"
    output_dir.mkdir(parents=True)
    (output_dir / "Michinari.exe").write_text("dummy", encoding="utf-8")

    assert discard_previous_package(output_dir) is None
    assert not output_dir.exists()
    assert list(dist_dir.iterdir()) == []


def test_discard_previous_package_keeps_the_staging_folder_when_removal_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """再試行しても全て失敗した場合、出力先は空いたまま一時フォルダを残す

    （OneDriveでの`WinError 5`対策。`time.sleep`は潰してテストを遅延させない）。
    """
    dist_dir = tmp_path / "dist"
    output_dir = dist_dir / "Michinari"
    output_dir.mkdir(parents=True)
    (output_dir / "Michinari.exe").write_text("dummy", encoding="utf-8")

    call_count = 0

    def fail_rmtree(path: Path) -> None:
        nonlocal call_count
        call_count += 1
        raise PermissionError("アクセスが拒否されました")

    monkeypatch.setattr(build_package.shutil, "rmtree", fail_rmtree)
    sleep_calls: list[float] = []
    monkeypatch.setattr(build_package.time, "sleep", sleep_calls.append)
    fixed_now = dt.datetime(2026, 9, 13, 18, 0, 0)

    leftover = discard_previous_package(output_dir, now=fixed_now)

    assert leftover == dist_dir / f"{PREVIOUS_PACKAGE_PREFIX}Michinari_20260913_180000"
    assert (leftover / "Michinari.exe").read_text(encoding="utf-8") == "dummy"
    assert not output_dir.exists()
    assert "旧パッケージを削除できませんでした" in capsys.readouterr().out
    # 既定は5回試行・試行の間だけ待機するため、待機回数は試行回数-1回になる。
    assert call_count == build_package.RMTREE_RETRY_ATTEMPTS
    assert sleep_calls == [build_package.RMTREE_RETRY_DELAY_SECONDS] * (
        build_package.RMTREE_RETRY_ATTEMPTS - 1
    )


def test_discard_previous_package_succeeds_after_transient_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OneDriveロックのような一時的な失敗の後に削除が成功すれば残骸を残さない。"""
    dist_dir = tmp_path / "dist"
    output_dir = dist_dir / "Michinari"
    output_dir.mkdir(parents=True)
    (output_dir / "Michinari.exe").write_text("dummy", encoding="utf-8")

    real_rmtree = build_package.shutil.rmtree
    call_count = 0

    def flaky_rmtree(path: Path) -> None:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise PermissionError("アクセスが拒否されました")
        real_rmtree(path)

    monkeypatch.setattr(build_package.shutil, "rmtree", flaky_rmtree)
    sleep_calls: list[float] = []
    monkeypatch.setattr(build_package.time, "sleep", sleep_calls.append)

    leftover = discard_previous_package(output_dir)

    assert leftover is None
    assert call_count == 3
    assert sleep_calls == [build_package.RMTREE_RETRY_DELAY_SECONDS] * 2
    assert not any(dist_dir.iterdir())


def test_discard_previous_package_retries_rename_on_transient_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """改名（`os.rename`）が一時的に失敗しても再試行して退避を完了する

    （2026-09-26、`shutil.move`では改名失敗時のコピー＋削除フォールバックが
    `__pycache__`のロックで中途半端に失敗する事象が発生したため、改名のみを
    直接再試行する方式に変更した）。"""
    dist_dir = tmp_path / "dist"
    output_dir = dist_dir / "Michinari"
    output_dir.mkdir(parents=True)
    (output_dir / "Michinari.exe").write_text("dummy", encoding="utf-8")

    real_rename = build_package.os.rename
    call_count = 0

    def flaky_rename(src: Path, dst: Path) -> None:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise PermissionError("プロセスはファイルにアクセスできません。")
        real_rename(src, dst)

    monkeypatch.setattr(build_package.os, "rename", flaky_rename)
    sleep_calls: list[float] = []
    monkeypatch.setattr(build_package.time, "sleep", sleep_calls.append)

    leftover = discard_previous_package(output_dir)

    assert leftover is None
    assert call_count == 3
    assert sleep_calls == [build_package.RMTREE_RETRY_DELAY_SECONDS] * 2
    assert not output_dir.exists()
    assert not any(dist_dir.iterdir())


def test_discard_previous_package_keeps_output_untouched_when_rename_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """改名が再試行しても全て失敗した場合、出力フォルダには一切手を付けず警告のみで継続する

    （`shutil.move`のコピー＋削除フォールバックのように、コピー先に複製ができた状態で
    コピー元も残るという中途半端な状態にはならないことを保証する）。
    """
    dist_dir = tmp_path / "dist"
    output_dir = dist_dir / "Michinari"
    output_dir.mkdir(parents=True)
    (output_dir / "Michinari.exe").write_text("dummy", encoding="utf-8")

    def always_fail_rename(src: Path, dst: Path) -> None:
        raise PermissionError("プロセスはファイルにアクセスできません。")

    monkeypatch.setattr(build_package.os, "rename", always_fail_rename)
    sleep_calls: list[float] = []
    monkeypatch.setattr(build_package.time, "sleep", sleep_calls.append)
    fixed_now = dt.datetime(2026, 9, 26, 16, 46, 4)

    leftover = discard_previous_package(output_dir, now=fixed_now)

    assert leftover is None
    assert output_dir.exists()
    assert (output_dir / "Michinari.exe").read_text(encoding="utf-8") == "dummy"
    assert list(dist_dir.iterdir()) == [output_dir]
    assert "旧パッケージを退避できませんでした" in capsys.readouterr().out
    assert sleep_calls == [build_package.RMTREE_RETRY_DELAY_SECONDS] * (
        build_package.RMTREE_RETRY_ATTEMPTS - 1
    )


def test_rename_with_retry_returns_last_error_when_all_attempts_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`discard_previous_package`が使う改名の再試行ヘルパー自体の挙動を検証する

    （`_rmtree_with_retry`と対になる再試行ヘルパー、CLAUDE.md DRYの原則）。"""
    src = tmp_path / "src"
    src.mkdir()
    dst = tmp_path / "dst"

    def always_fail_rename(source: Path, destination: Path) -> None:
        raise PermissionError("アクセスが拒否されました")

    monkeypatch.setattr(build_package.os, "rename", always_fail_rename)
    sleep_calls: list[float] = []
    monkeypatch.setattr(build_package.time, "sleep", sleep_calls.append)

    error = _rename_with_retry(src, dst, retry_attempts=3, retry_delay_seconds=1.5)

    assert isinstance(error, PermissionError)
    assert sleep_calls == [1.5, 1.5]
    assert src.exists()
    assert not dst.exists()


def test_rmtree_with_retry_returns_last_error_when_all_attempts_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`discard_previous_package`・`cleanup_stale_previous_packages`が共通で使う
    再試行ヘルパー自体の挙動を検証する（CLAUDE.md DRYの原則で共通化した処理）。"""
    target = tmp_path / "locked"
    target.mkdir()

    def always_fail_rmtree(path: Path) -> None:
        raise PermissionError("アクセスが拒否されました")

    monkeypatch.setattr(build_package.shutil, "rmtree", always_fail_rmtree)
    sleep_calls: list[float] = []
    monkeypatch.setattr(build_package.time, "sleep", sleep_calls.append)

    error = _rmtree_with_retry(target, retry_attempts=3, retry_delay_seconds=1.5)

    assert isinstance(error, PermissionError)
    assert sleep_calls == [1.5, 1.5]
    assert target.exists()


def test_cleanup_stale_previous_packages_returns_empty_when_dist_dir_is_absent(
    tmp_path: Path,
) -> None:
    dist_dir = tmp_path / "dist"

    assert cleanup_stale_previous_packages(dist_dir) == []


def test_cleanup_stale_previous_packages_returns_empty_when_none_exist(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "Michinari").mkdir()
    (dist_dir / "_archive").mkdir()

    assert cleanup_stale_previous_packages(dist_dir) == []


def test_cleanup_stale_previous_packages_removes_only_prefixed_folders(
    tmp_path: Path,
) -> None:
    """`_previous_`接頭辞のフォルダのみ削除し、出力フォルダ・`_archive/`・zipには触れない。"""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    stale_a = dist_dir / f"{PREVIOUS_PACKAGE_PREFIX}Michinari_20260913_180000"
    stale_a.mkdir()
    (stale_a / "Michinari.exe").write_text("dummy", encoding="utf-8")
    stale_b = dist_dir / f"{PREVIOUS_PACKAGE_PREFIX}Michinari_20260912_090000"
    stale_b.mkdir()
    output_dir = dist_dir / "Michinari"
    output_dir.mkdir()
    archive_dir = dist_dir / "_archive"
    archive_dir.mkdir()
    zip_path = dist_dir / "Michinari-v0.1.0.zip"
    zip_path.write_text("zip", encoding="utf-8")

    removed = cleanup_stale_previous_packages(dist_dir)

    assert removed == [stale_b, stale_a]
    assert not stale_a.exists()
    assert not stale_b.exists()
    assert output_dir.exists()
    assert archive_dir.exists()
    assert zip_path.exists()


def test_cleanup_stale_previous_packages_warns_and_continues_when_removal_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """1件の削除に再試行しても失敗した場合、他の対象の削除は継続し、ビルドは中断しない。

    `discard_previous_package`と同じ回数だけ再試行すること自体もここで検証する
    （2026-09-19、再試行が無く1回失敗しただけで諦めていた不具合の修正）。
    """
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    locked = dist_dir / f"{PREVIOUS_PACKAGE_PREFIX}Michinari_20260912_090000"
    locked.mkdir()
    removable = dist_dir / f"{PREVIOUS_PACKAGE_PREFIX}Michinari_20260913_180000"
    removable.mkdir()

    real_rmtree = build_package.shutil.rmtree
    locked_call_count = 0

    def selective_fail_rmtree(path: Path) -> None:
        nonlocal locked_call_count
        if path == locked:
            locked_call_count += 1
            raise PermissionError("アクセスが拒否されました")
        real_rmtree(path)

    monkeypatch.setattr(build_package.shutil, "rmtree", selective_fail_rmtree)
    sleep_calls: list[float] = []
    monkeypatch.setattr(build_package.time, "sleep", sleep_calls.append)

    removed = cleanup_stale_previous_packages(dist_dir)

    assert removed == [removable]
    assert locked.exists()
    assert not removable.exists()
    assert "残存する旧パッケージを削除できませんでした" in capsys.readouterr().out
    assert locked_call_count == build_package.RMTREE_RETRY_ATTEMPTS
    assert sleep_calls == [build_package.RMTREE_RETRY_DELAY_SECONDS] * (
        build_package.RMTREE_RETRY_ATTEMPTS - 1
    )


def test_cleanup_stale_previous_packages_succeeds_after_transient_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OneDriveロックのような一時的な失敗の後に削除が成功すれば残骸を残さない。"""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    flaky = dist_dir / f"{PREVIOUS_PACKAGE_PREFIX}Michinari_20260913_180000"
    flaky.mkdir()

    real_rmtree = build_package.shutil.rmtree
    call_count = 0

    def flaky_rmtree(path: Path) -> None:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise PermissionError("アクセスが拒否されました")
        real_rmtree(path)

    monkeypatch.setattr(build_package.shutil, "rmtree", flaky_rmtree)
    sleep_calls: list[float] = []
    monkeypatch.setattr(build_package.time, "sleep", sleep_calls.append)

    removed = cleanup_stale_previous_packages(dist_dir)

    assert removed == [flaky]
    assert call_count == 3
    assert sleep_calls == [build_package.RMTREE_RETRY_DELAY_SECONDS] * 2
    assert not flaky.exists()
