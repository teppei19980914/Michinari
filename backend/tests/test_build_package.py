"""配布パッケージビルドスクリプトのアーカイブ処理・zip化・バージョン確定・
ビルド情報生成のテスト（scripts/build_package.py参照）。

PyInstaller本体の実行はCI環境依存が大きいため対象外とし、既存パッケージの退避ロジック
（`archive_previous_package`）・配布用zip化ロジック（`create_distribution_zip`）・
配布バージョンの読み書き/確定ロジック（`read_current_version`/`write_version`/
`resolve_version`）・ビルド情報生成ロジック（`generate_build_info`）・ビルド元コミットの
記録ロジック（`read_git_commit`/`has_uncommitted_changes`/`generate_build_commit`）・
ユーザ手順書の
同梱ロジック（`copy_user_manual`）に加え、配布パッケージへ同梱する起動用batの
テンプレート内容（`LAUNCHER_TEMPLATE_PATH`）を検証する。
"""

import datetime as dt
import json
import subprocess
import tomllib
import zipfile
from pathlib import Path

import pytest
from build_package import (
    LAUNCHER_TEMPLATE_PATH,
    PYPROJECT_PATH,
    USER_MANUAL_PATH,
    archive_previous_package,
    build_commit_filename,
    copy_user_manual,
    create_distribution_zip,
    generate_build_commit,
    generate_build_info,
    has_uncommitted_changes,
    read_current_version,
    read_git_commit,
    resolve_version,
    write_version,
)


def test_archive_previous_package_returns_none_when_no_existing_output(tmp_path: Path) -> None:
    output_dir = tmp_path / "dist" / "Michinari"
    archive_dir = tmp_path / "dist" / "_archive"

    result = archive_previous_package(output_dir, archive_dir, "Michinari")

    assert result is None
    assert not archive_dir.exists()


def test_archive_previous_package_moves_existing_output_with_timestamp(tmp_path: Path) -> None:
    output_dir = tmp_path / "dist" / "Michinari"
    output_dir.mkdir(parents=True)
    marker_file = output_dir / "Michinari.exe"
    marker_file.write_text("dummy", encoding="utf-8")
    archive_dir = tmp_path / "dist" / "_archive"
    fixed_now = dt.datetime(2026, 8, 27, 14, 30, 0)

    result = archive_previous_package(output_dir, archive_dir, "Michinari", now=fixed_now)

    assert result == archive_dir / "Michinari_20260827_143000"
    assert not output_dir.exists()
    assert (result / "Michinari.exe").read_text(encoding="utf-8") == "dummy"


def test_archive_previous_package_keeps_prior_archives_on_repeated_builds(tmp_path: Path) -> None:
    output_dir = tmp_path / "dist" / "Michinari"
    archive_dir = tmp_path / "dist" / "_archive"

    output_dir.mkdir(parents=True)
    (output_dir / "v1.txt").write_text("v1", encoding="utf-8")
    first = archive_previous_package(
        output_dir, archive_dir, "Michinari", now=dt.datetime(2026, 8, 27, 9, 0, 0)
    )

    output_dir.mkdir(parents=True)
    (output_dir / "v2.txt").write_text("v2", encoding="utf-8")
    second = archive_previous_package(
        output_dir, archive_dir, "Michinari", now=dt.datetime(2026, 8, 27, 10, 0, 0)
    )

    assert first is not None and second is not None
    assert first != second
    assert (first / "v1.txt").exists()
    assert (second / "v2.txt").exists()


def test_create_distribution_zip_contains_top_level_app_folder(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    output_dir = dist_dir / "Michinari"
    output_dir.mkdir(parents=True)
    (output_dir / "Michinari.exe").write_text("dummy-exe", encoding="utf-8")
    (output_dir / "Michinari.bat").write_text("dummy-bat", encoding="utf-8")

    result = create_distribution_zip(output_dir, dist_dir, "Michinari", "0.2.0")

    assert result == dist_dir / "Michinari-v0.2.0.zip"
    with zipfile.ZipFile(result) as zf:
        names = set(zf.namelist())
    assert "Michinari/Michinari.exe" in names
    assert "Michinari/Michinari.bat" in names


def test_create_distribution_zip_does_not_touch_archive_dir(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    output_dir = dist_dir / "Michinari"
    archive_dir = dist_dir / "_archive"
    output_dir.mkdir(parents=True)
    (output_dir / "Michinari.exe").write_text("dummy-exe", encoding="utf-8")
    archived = archive_dir / "Michinari_20260827_090000"
    archived.mkdir(parents=True)
    (archived / "v1.txt").write_text("v1", encoding="utf-8")

    create_distribution_zip(output_dir, dist_dir, "Michinari", "0.2.0")

    assert (archived / "v1.txt").exists()
    with zipfile.ZipFile(dist_dir / "Michinari-v0.2.0.zip") as zf:
        names = set(zf.namelist())
    assert not any(name.startswith("_archive") for name in names)


def test_create_distribution_zip_overwrites_previous_zip_of_same_version(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    output_dir = dist_dir / "Michinari"
    output_dir.mkdir(parents=True)
    (output_dir / "v1.txt").write_text("v1", encoding="utf-8")
    create_distribution_zip(output_dir, dist_dir, "Michinari", "0.2.0")

    (output_dir / "v1.txt").unlink()
    (output_dir / "v2.txt").write_text("v2", encoding="utf-8")
    result = create_distribution_zip(output_dir, dist_dir, "Michinari", "0.2.0")

    with zipfile.ZipFile(result) as zf:
        names = set(zf.namelist())
    assert "Michinari/v2.txt" in names
    assert "Michinari/v1.txt" not in names


def test_create_distribution_zip_keeps_previous_version_zip_when_version_changes(
    tmp_path: Path,
) -> None:
    dist_dir = tmp_path / "dist"
    output_dir = dist_dir / "Michinari"
    output_dir.mkdir(parents=True)
    (output_dir / "app.txt").write_text("v1", encoding="utf-8")
    first = create_distribution_zip(output_dir, dist_dir, "Michinari", "0.1.0")

    (output_dir / "app.txt").write_text("v2", encoding="utf-8")
    second = create_distribution_zip(output_dir, dist_dir, "Michinari", "0.2.0")

    assert first != second
    assert first.exists()
    assert second.exists()


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


def _write_fixture_repo(repo_root: Path) -> None:
    backend_dir = repo_root / "backend"
    backend_dir.mkdir()
    (backend_dir / "pyproject.toml").write_text(
        """
[project]
name = "michinari-backend"
version = "1.2.3"
dependencies = ["fastapi>=0.115"]
""".strip(),
        encoding="utf-8",
    )
    frontend_dir = repo_root / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "package.json").write_text(
        json.dumps({"dependencies": {"react": "^19.2.8"}}), encoding="utf-8"
    )
    (frontend_dir / "package-lock.json").write_text(
        json.dumps(
            {"lockfileVersion": 3, "packages": {"node_modules/react": {"version": "19.2.8"}}}
        ),
        encoding="utf-8",
    )


def test_generate_build_info_writes_expected_json(tmp_path: Path) -> None:
    _write_fixture_repo(tmp_path)
    output_path = tmp_path / "backend" / "build_info.json"
    fixed_now = dt.datetime(2026, 8, 28, 0, 0, 0, tzinfo=dt.UTC)

    result = generate_build_info(tmp_path, output_path, now=fixed_now)

    assert result == output_path
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["app_version"] == "1.2.3"
    assert data["built_at"] == fixed_now.isoformat()
    assert data["backend_libraries"][0]["name"] == "fastapi"
    assert data["frontend_libraries"][0]["name"] == "react"


def test_generate_build_info_defaults_built_at_to_now(tmp_path: Path) -> None:
    _write_fixture_repo(tmp_path)
    output_path = tmp_path / "backend" / "build_info.json"

    generate_build_info(tmp_path, output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["built_at"] is not None
    # ISO8601形式であること（dt.datetime.fromisoformatで解釈できること）を確認する。
    dt.datetime.fromisoformat(data["built_at"])


def test_copy_user_manual_places_pdf_directly_under_the_package_folder(tmp_path: Path) -> None:
    """手順書は利用者がエクスプローラから開けるようパッケージ直下へ原本名のまま複製する。"""
    manual_path = tmp_path / "docs" / "ユーザ手順書.pdf"
    manual_path.parent.mkdir(parents=True)
    manual_path.write_bytes(b"%PDF-1.7 dummy")
    output_dir = tmp_path / "dist" / "Michinari"
    output_dir.mkdir(parents=True)

    result = copy_user_manual(manual_path, output_dir)

    assert result == output_dir / "ユーザ手順書.pdf"
    assert result.read_bytes() == b"%PDF-1.7 dummy"


def test_copy_user_manual_skips_without_failing_when_manual_is_missing(tmp_path: Path) -> None:
    """手順書が無くてもアプリの動作には影響しないため、ビルドを中止せず同梱のみ飛ばす。"""
    manual_path = tmp_path / "docs" / "ユーザ手順書.pdf"
    output_dir = tmp_path / "dist" / "Michinari"
    output_dir.mkdir(parents=True)

    result = copy_user_manual(manual_path, output_dir)

    assert result is None
    assert list(output_dir.iterdir()) == []


def test_copy_user_manual_overwrites_a_stale_manual_from_a_previous_build(tmp_path: Path) -> None:
    manual_path = tmp_path / "docs" / "ユーザ手順書.pdf"
    manual_path.parent.mkdir(parents=True)
    manual_path.write_bytes(b"new")
    output_dir = tmp_path / "dist" / "Michinari"
    output_dir.mkdir(parents=True)
    (output_dir / "ユーザ手順書.pdf").write_bytes(b"old")

    result = copy_user_manual(manual_path, output_dir)

    assert result.read_bytes() == b"new"


def test_create_distribution_zip_includes_the_bundled_user_manual(tmp_path: Path) -> None:
    """同梱した手順書が配布用zipにも含まれること（配布先はzipしか受け取らないため）。"""
    dist_dir = tmp_path / "dist"
    output_dir = dist_dir / "Michinari"
    output_dir.mkdir(parents=True)
    (output_dir / "Michinari.exe").write_text("dummy-exe", encoding="utf-8")
    (output_dir / "ユーザ手順書.pdf").write_bytes(b"%PDF-1.7 dummy")

    result = create_distribution_zip(output_dir, dist_dir, "Michinari", "0.2.0")

    with zipfile.ZipFile(result) as zf:
        names = set(zf.namelist())
    assert "Michinari/ユーザ手順書.pdf" in names


def test_user_manual_exists_at_the_path_the_build_bundles_from() -> None:
    """リポジトリ内の手順書原本が`USER_MANUAL_PATH`に実在すること。

    `copy_user_manual`は手順書が見つからない場合に警告のみでビルドを続行するため、
    原本の改名・移動が起きても配布パッケージから手順書が黙って欠落するだけで
    ビルドは成功してしまう。ここで実パスを検証し、その欠落をテストで検出する。
    """
    assert USER_MANUAL_PATH.is_file(), f"手順書の原本が見つかりません: {USER_MANUAL_PATH}"


def test_uv_link_mode_is_copy_so_sync_does_not_hardlink_cloud_files() -> None:
    """uvのリンク方式がコピーであること（OneDrive配下でのビルド失敗を防ぐ）。

    既定のハードリンクではキャッシュ配下がOneDriveのクラウドファイルの場合に
    `os error 396`で`uv sync`がビルド依存の導入に失敗し、ビルド自体が始まらない
    （OPERATIONS.md 7.4参照）。設定の消失を検出するため固定する。
    """
    with PYPROJECT_PATH.open("rb") as f:
        data = tomllib.load(f)

    assert data["tool"]["uv"]["link-mode"] == "copy"


def _launcher_template_text() -> str:
    return LAUNCHER_TEMPLATE_PATH.read_text(encoding="utf-8")


def test_launcher_template_starts_the_exe_from_its_own_folder() -> None:
    """ランチャがbat自身の場所へ移動し、exeをフルパスで起動すること。

    利用者はzipを展開した任意の場所からダブルクリックで起動するため、カレント
    ディレクトリはbatの場所と一致しない。`cd /d "%~dp0"`が失われるとアプリの
    作業ディレクトリがずれる。

    起動をファイル名だけ（`Michinari.exe`）にしないのは、環境変数
    `NoDefaultCurrentDirectoryInExePath`が設定された端末ではcmd.exeがカレント
    ディレクトリを探索せず、「is not recognized」で起動できないため。
    """
    text = _launcher_template_text()

    assert 'cd /d "%~dp0"' in text
    assert '"%~dp0Michinari.exe"' in text


def test_launcher_template_keeps_the_window_open_when_startup_fails() -> None:
    """exeが異常終了したとき、ランチャが入力待ちで止まりエラーを読めること。

    Michinari.exeは起動失敗（例: DBマイグレーションの解決失敗）をコンソールへ
    出力して終了コード1で終わる。この停止処理が無いとウィンドウが一瞬で閉じ、
    利用者にはエラー内容が一切残らない（2026-09-08に発生した事象）。
    """
    text = _launcher_template_text()

    assert "if errorlevel 1 (" in text
    assert "pause" in text


def test_launcher_template_does_not_pause_after_a_normal_shutdown() -> None:
    """正常終了時は入力待ちで止めないこと（`pause`が失敗時ブロック内のみにあること）。

    通常の終了までキー入力を求めると毎回の利用の妨げになるため、`pause`は
    `if errorlevel 1`のブロック内だけに置く。
    """
    lines = [line.strip() for line in _launcher_template_text().splitlines()]
    failure_block = lines[lines.index("if errorlevel 1 (") :]

    assert [line for line in lines if line == "pause"] == [
        line for line in failure_block if line == "pause"
    ]


def test_launcher_template_is_ascii_only_for_the_console_code_page() -> None:
    """ランチャがASCIIのみで構成されること。

    batはコンソールのOEMコードページ（日本語Windowsでは932）で解釈されるため、
    UTF-8で書いた日本語メッセージは文字化けする。表示文言・コメントとも
    ASCIIに固定する。
    """
    LAUNCHER_TEMPLATE_PATH.read_bytes().decode("ascii")


def test_launcher_template_uses_crlf_line_endings() -> None:
    """ランチャの改行がCRLFであること（cmd.exeが確実に解釈できる形に固定する）。"""
    data = LAUNCHER_TEMPLATE_PATH.read_bytes()

    assert data.count(b"\n") == data.count(b"\r\n")


class _FakeCompletedProcess:
    def __init__(self, returncode: int, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout


def test_build_commit_filename_pairs_with_the_distribution_zip() -> None:
    """記録ファイル名が配布zipと対になること（publish_release.pyが同じ名前で探す）。"""
    assert build_commit_filename("Michinari", "1.2.3") == "Michinari-v1.2.3.commit.json"


def test_read_git_commit_returns_head_sha(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, cwd=None, **kwargs: _FakeCompletedProcess(0, "abc1234\n"),
    )

    assert read_git_commit(tmp_path) == "abc1234"


def test_read_git_commit_returns_none_outside_a_git_repository(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda args, cwd=None, **kwargs: _FakeCompletedProcess(128)
    )

    assert read_git_commit(tmp_path) is None


def test_has_uncommitted_changes_detects_a_dirty_tree(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, cwd=None, **kwargs: _FakeCompletedProcess(0, " M backend/pyproject.toml\n"),
    )

    assert has_uncommitted_changes(tmp_path) is True


def test_has_uncommitted_changes_is_false_for_a_clean_tree(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda args, cwd=None, **kwargs: _FakeCompletedProcess(0, "")
    )

    assert has_uncommitted_changes(tmp_path) is False


def test_has_uncommitted_changes_returns_none_outside_a_git_repository(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda args, cwd=None, **kwargs: _FakeCompletedProcess(128)
    )

    assert has_uncommitted_changes(tmp_path) is None


def test_generate_build_commit_records_version_commit_and_dirty_flag(tmp_path: Path) -> None:
    output_path = tmp_path / "Michinari-v1.2.3.commit.json"

    generate_build_commit(output_path, "1.2.3", "abc1234", dirty=False)

    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "version": "1.2.3",
        "commit": "abc1234",
        "dirty": False,
    }


def test_generate_build_commit_keeps_dirty_builds_identifiable(tmp_path: Path) -> None:
    """未コミットの木からのビルドを記録に残し、publish_release.pyが公開を止められること。"""
    output_path = tmp_path / "Michinari-v1.2.3.commit.json"

    generate_build_commit(output_path, "1.2.3", "abc1234", dirty=True)

    assert json.loads(output_path.read_text(encoding="utf-8"))["dirty"] is True
