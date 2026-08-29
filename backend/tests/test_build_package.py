"""配布パッケージビルドスクリプトのアーカイブ処理・zip化・バージョン確定のテスト
（scripts/build_package.py参照）。

PyInstaller本体の実行はCI環境依存が大きいため対象外とし、既存パッケージの退避ロジック
（`archive_previous_package`）・配布用zip化ロジック（`create_distribution_zip`）・
配布バージョンの読み書き/確定ロジック（`read_current_version`/`write_version`/
`resolve_version`）のみを検証する。
"""

import datetime as dt
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from build_package import (  # noqa: E402
    archive_previous_package,
    create_distribution_zip,
    read_current_version,
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
        '[project]\nname = "michinari-backend"\nversion = "0.1.0"\n'
        'description = "バックエンド"\n',
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
