"""配布パッケージビルドスクリプトのうち、配布用zip化（create_distribution_zip）・
ビルド情報生成（generate_build_info）・ユーザ手順書の同梱（copy_user_manual）・
起動用batのテンプレート内容（LAUNCHER_TEMPLATE_PATH）・uvのリンクモード設定のテスト
（scripts/build_package.py参照）。実装フェーズ分割計画書S02、test_build_package.pyからの
分割（決定事項S7）。
"""

import datetime as dt
import json
import tomllib
import zipfile
from pathlib import Path

from build_package import (
    LAUNCHER_TEMPLATE_PATH,
    PREVIOUS_PACKAGE_PREFIX,
    PYPROJECT_PATH,
    USER_MANUAL_PATH,
    copy_user_manual,
    create_distribution_zip,
    generate_build_info,
)

from app.desktop import runner as desktop_runner


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
    """zip化は`Michinari/`のみを対象とし、`_archive/`や削除し残した旧パッケージを含めない。"""
    dist_dir = tmp_path / "dist"
    output_dir = dist_dir / "Michinari"
    archive_dir = dist_dir / "_archive"
    output_dir.mkdir(parents=True)
    (output_dir / "Michinari.exe").write_text("dummy-exe", encoding="utf-8")
    archive_dir.mkdir(parents=True)
    (archive_dir / "Michinari-v0.1.0.zip").write_text("v1", encoding="utf-8")
    leftover = dist_dir / f"{PREVIOUS_PACKAGE_PREFIX}Michinari_20260913_180000"
    leftover.mkdir()
    (leftover / "v1.txt").write_text("v1", encoding="utf-8")

    create_distribution_zip(output_dir, dist_dir, "Michinari", "0.2.0")

    assert (archive_dir / "Michinari-v0.1.0.zip").exists()
    assert (leftover / "v1.txt").exists()
    with zipfile.ZipFile(dist_dir / "Michinari-v0.2.0.zip") as zf:
        names = set(zf.namelist())
    assert all(name.startswith("Michinari/") for name in names)


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

    この停止処理が無いとウィンドウが一瞬で閉じ、エラー内容が一切残らない
    （2026-09-08に発生した事象）。Phase37でコンソールを表示しない構成へ移行したため、
    利用者向けの起動失敗の通知はダイアログとログファイルが担うようになったが
    （`app/desktop/runner.py`の`show_error_dialog`）、このbatは開発者が`--console`付きで
    起動して原因を追うためのものなので、入力待ちは引き続き必要である。
    """
    text = _launcher_template_text()

    assert "if errorlevel 1 (" in text
    assert "pause" in text


def test_launcher_template_passes_the_console_option() -> None:
    """障害調査用batが`--console`付きでexeを起動すること（Phase37）。

    配布する実行ファイルはコンソールを表示しない構成でビルドする。このオプションが
    無いと、batから起動しても動作中のログが画面に出ず、batを同梱する意味が失われる。
    """
    assert f'"%~dp0Michinari.exe" {desktop_runner.CONSOLE_OPTION}' in _launcher_template_text()


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
