"""配布パッケージビルドスクリプトのアーカイブ処理・zip化・ビルド情報生成のテスト
（scripts/build_package.py参照）。

PyInstaller本体の実行はCI環境依存が大きいため対象外とし、既存パッケージの退避ロジック
（`archive_previous_package`）・配布用zip化ロジック（`create_distribution_zip`）・
ビルド情報生成ロジック（`generate_build_info`）のみを検証する。
"""

import datetime as dt
import json
import zipfile
from pathlib import Path

from build_package import archive_previous_package, create_distribution_zip, generate_build_info


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

    result = create_distribution_zip(output_dir, dist_dir, "Michinari")

    assert result == dist_dir / "Michinari.zip"
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

    create_distribution_zip(output_dir, dist_dir, "Michinari")

    assert (archived / "v1.txt").exists()
    with zipfile.ZipFile(dist_dir / "Michinari.zip") as zf:
        names = set(zf.namelist())
    assert not any(name.startswith("_archive") for name in names)


def test_create_distribution_zip_overwrites_previous_zip_content(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    output_dir = dist_dir / "Michinari"
    output_dir.mkdir(parents=True)
    (output_dir / "v1.txt").write_text("v1", encoding="utf-8")
    create_distribution_zip(output_dir, dist_dir, "Michinari")

    (output_dir / "v1.txt").unlink()
    (output_dir / "v2.txt").write_text("v2", encoding="utf-8")
    result = create_distribution_zip(output_dir, dist_dir, "Michinari")

    with zipfile.ZipFile(result) as zf:
        names = set(zf.namelist())
    assert "Michinari/v2.txt" in names
    assert "Michinari/v1.txt" not in names


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
