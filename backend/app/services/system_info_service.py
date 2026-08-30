"""システム情報（アプリバージョン・使用ライブラリ）の取得（仕様書6.14 SC-15）。

`build_info.json`は`scripts/build_package.py`がビルド時に生成し配布パッケージへ
同梱する静的アセットであり、`alembic.ini`やフロントエンド静的ファイルと同列の
ビルド時同梱物である（アプリ実行時に生成・更新される状態ではない）。そのため
CLAUDE.md「日次ノルマ・残量・現在周回の保存禁止（都度算出する）」が禁じる
"実行時状態のDB永続化"には該当しない。frozen（PyInstaller配布exe）実行時は
importlib.metadataがパッケージのdist-info情報を保持しない場合があるため、
本ファイルを読むだけにとどめ、非frozen（ソースから起動する開発環境）時のみ
その場でライブ計算する。
"""

from __future__ import annotations

import json
import platform
import re
import sys
import tomllib
from dataclasses import asdict, dataclass
from importlib import metadata
from pathlib import Path

#: pyproject.tomlの依存文字列（例: "uvicorn[standard]>=0.32"）からパッケージ名のみを
#: 取り出す。対象は自プロジェクトの固定された依存文字列のみのため、PEP 508の完全な
#: パーサ（`packaging`ライブラリ）は使わない（`packaging`はPyInstaller経由の推移的
#: 依存にすぎず、開発環境でのライブ計算がそれへ暗黙依存するのを避けるため）。
_DEPENDENCY_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+")

#: パッケージの実バージョンが引けなかった場合（未インストール・lockファイル未掲載等）の
#: 想定外エラー用フォールバック表示。
_UNKNOWN_VERSION = "unknown"


@dataclass(frozen=True)
class LibraryInfo:
    name: str
    version: str


@dataclass(frozen=True)
class BuildInfo:
    app_version: str
    python_version: str
    built_at: str | None
    backend_libraries: list[LibraryInfo]
    frontend_libraries: list[LibraryInfo]


def _dependency_name(spec: str) -> str:
    match = _DEPENDENCY_NAME_PATTERN.match(spec)
    return match.group(0) if match else spec


def read_app_version(repo_root: Path) -> str:
    """`backend/pyproject.toml`の`[project].version`を読む（アプリバージョンの単一の情報源）。"""
    pyproject = repo_root / "backend" / "pyproject.toml"
    with pyproject.open("rb") as f:
        pyproject_data = tomllib.load(f)
    return pyproject_data["project"]["version"]


def _backend_libraries(repo_root: Path) -> list[LibraryInfo]:
    pyproject = repo_root / "backend" / "pyproject.toml"
    with pyproject.open("rb") as f:
        pyproject_data = tomllib.load(f)
    libraries = []
    for spec in pyproject_data["project"]["dependencies"]:
        name = _dependency_name(spec)
        try:
            version = metadata.version(name)
        except metadata.PackageNotFoundError:  # pragma: no cover
            # uv syncが正しく行われていれば発生しない異常系（依存が未インストールの場合のみ）。
            version = _UNKNOWN_VERSION
        libraries.append(LibraryInfo(name=name, version=version))
    return libraries


def _frontend_libraries(repo_root: Path) -> list[LibraryInfo]:
    """`package.json`の依存名に対し、`package-lock.json`（lockfileVersion 3）で実際に
    解決されたバージョンを引く。バックエンドの`importlib.metadata.version()`と同じく、
    宣言された範囲（例: "^19.2.8"）ではなくインストール済みの実バージョンを表示するため。
    """
    package_json = repo_root / "frontend" / "package.json"
    package_json_data = json.loads(package_json.read_text(encoding="utf-8"))
    package_lock = repo_root / "frontend" / "package-lock.json"
    lock_packages = json.loads(package_lock.read_text(encoding="utf-8")).get("packages", {})

    libraries = []
    for name in package_json_data.get("dependencies", {}):
        lock_entry = lock_packages.get(f"node_modules/{name}")
        version = lock_entry["version"] if lock_entry else _UNKNOWN_VERSION
        libraries.append(LibraryInfo(name=name, version=version))
    return libraries


def collect_build_info(repo_root: Path, *, built_at: str | None = None) -> BuildInfo:
    """アプリバージョン・Pythonバージョン・主要ライブラリ構成をその場で計算する。

    `scripts/build_package.py`がビルド時に呼び出して`build_info.json`へ書き出す用途と、
    ソースから起動する開発環境で`get_system_info`がライブ計算する用途の両方で使う
    （CLAUDE.md DRYの原則、ロジックの重複を避けるため1関数に集約）。
    """
    return BuildInfo(
        app_version=read_app_version(repo_root),
        python_version=platform.python_version(),
        built_at=built_at,
        backend_libraries=_backend_libraries(repo_root),
        frontend_libraries=_frontend_libraries(repo_root),
    )


def _bundled_build_info_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return base / "build_info.json"


def get_system_info(repo_root: Path) -> BuildInfo:
    """システム情報画面（SC-15）向けのビルド情報を取得する。

    frozen（PyInstaller配布exe）実行時はビルド時に同梱された`build_info.json`を
    読むだけにする（`app/config.py`の`_default_data_dir`・`app/main.py`の
    `resolve_frontend_dist_dir`と同じ`sys.frozen`分岐の考え方）。非frozen時は
    ソースツリーから`collect_build_info`でその場計算する（built_atはビルド時刻を
    持たないため`None`＝開発環境である旨をAPI層・画面側で表示する）。
    """
    if getattr(sys, "frozen", False):
        bundled_build_info = json.loads(_bundled_build_info_path().read_text(encoding="utf-8"))
        return BuildInfo(
            app_version=bundled_build_info["app_version"],
            python_version=bundled_build_info["python_version"],
            built_at=bundled_build_info["built_at"],
            backend_libraries=[
                LibraryInfo(**lib) for lib in bundled_build_info["backend_libraries"]
            ],
            frontend_libraries=[
                LibraryInfo(**lib) for lib in bundled_build_info["frontend_libraries"]
            ],
        )
    return collect_build_info(repo_root)


def build_info_to_json(build_info: BuildInfo) -> str:
    """`build_info.json`書き出し用のJSON文字列化（`scripts/build_package.py`から利用）。"""
    return json.dumps(asdict(build_info), ensure_ascii=False, indent=2)
