"""app.services.system_info_service のテスト（仕様書6.14 SC-15）。"""

import json
import sys
from pathlib import Path

from app.services import system_info_service
from app.services.system_info_service import (
    BuildInfo,
    LibraryInfo,
    _dependency_name,
    build_info_to_json,
    collect_build_info,
    get_system_info,
    read_app_version,
)


def _write_fixture_repo(tmp_path: Path) -> Path:
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / "pyproject.toml").write_text(
        """
[project]
name = "michinari-backend"
version = "1.2.3"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "newtonx-adk",
]
""".strip(),
        encoding="utf-8",
    )
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "package.json").write_text(
        json.dumps({"dependencies": {"react": "^19.2.8", "recharts": "^3.10.1"}}),
        encoding="utf-8",
    )
    (frontend_dir / "package-lock.json").write_text(
        json.dumps(
            {
                "lockfileVersion": 3,
                "packages": {
                    "node_modules/react": {"version": "19.2.8"},
                    # recharts はロックファイル未掲載を想定し、フォールバック分岐を検証する
                },
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_dependency_name_extracts_bare_name() -> None:
    assert _dependency_name("fastapi>=0.115") == "fastapi"


def test_dependency_name_extracts_name_with_extras() -> None:
    assert _dependency_name("uvicorn[standard]>=0.32") == "uvicorn"


def test_dependency_name_extracts_name_without_version_specifier() -> None:
    assert _dependency_name("newtonx-adk") == "newtonx-adk"


def test_read_app_version_reads_pyproject_toml(tmp_path: Path) -> None:
    repo_root = _write_fixture_repo(tmp_path)

    assert read_app_version(repo_root) == "1.2.3"


def test_collect_build_info_returns_expected_libraries(tmp_path: Path) -> None:
    repo_root = _write_fixture_repo(tmp_path)

    build_info = collect_build_info(repo_root, built_at="2026-08-28T00:00:00+00:00")

    assert build_info.app_version == "1.2.3"
    assert build_info.built_at == "2026-08-28T00:00:00+00:00"
    backend_names = {lib.name for lib in build_info.backend_libraries}
    assert backend_names == {"fastapi", "uvicorn", "newtonx-adk"}
    assert LibraryInfo(name="react", version="19.2.8") in build_info.frontend_libraries
    assert LibraryInfo(name="recharts", version="unknown") in build_info.frontend_libraries


def test_collect_build_info_built_at_defaults_to_none(tmp_path: Path) -> None:
    repo_root = _write_fixture_repo(tmp_path)

    build_info = collect_build_info(repo_root)

    assert build_info.built_at is None


def test_build_info_to_json_round_trips(tmp_path: Path) -> None:
    repo_root = _write_fixture_repo(tmp_path)
    build_info = collect_build_info(repo_root, built_at="2026-08-28T00:00:00+00:00")

    data = json.loads(build_info_to_json(build_info))

    assert data["app_version"] == "1.2.3"
    assert data["backend_libraries"][0]["name"] == "fastapi"


def test_get_system_info_computes_live_when_not_frozen(monkeypatch, tmp_path: Path) -> None:
    repo_root = _write_fixture_repo(tmp_path)
    monkeypatch.setattr(sys, "frozen", False, raising=False)

    result = get_system_info(repo_root)

    assert isinstance(result, BuildInfo)
    assert result.app_version == "1.2.3"
    assert result.built_at is None


def test_get_system_info_reads_bundled_file_when_frozen(monkeypatch, tmp_path: Path) -> None:
    bundled = BuildInfo(
        app_version="9.9.9",
        python_version="3.12.0",
        built_at="2026-08-28T00:00:00+00:00",
        backend_libraries=[LibraryInfo(name="fastapi", version="0.115.0")],
        frontend_libraries=[LibraryInfo(name="react", version="19.2.8")],
    )
    (tmp_path / "build_info.json").write_text(build_info_to_json(bundled), encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    result = get_system_info(tmp_path)

    assert result == bundled


def test_bundled_build_info_path_falls_back_to_executable_dir_without_meipass(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "Michinari.exe"), raising=False)

    result = system_info_service._bundled_build_info_path()

    assert result == tmp_path / "build_info.json"
