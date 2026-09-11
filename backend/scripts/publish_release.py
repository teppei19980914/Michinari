"""配布パッケージをGitHub Releasesへ公開するスクリプト（OPERATIONS.md 7.4参照）。

`build_package.py`とは独立しており、ビルドスクリプトから自動的に呼び出されることはない。
公開はGitHub上で他者から見える操作であるため、開発者が公開したいタイミングで明示的に
実行する（CLAUDE.md「マージは開発者が手動実施」と同じ考え方で、公開も自動化の対象外とする）。

実行例（backendディレクトリから、事前に `uv run python scripts/build_package.py` でzipを
生成しておくこと）: `uv run python scripts/publish_release.py`
"""

import subprocess
import sys
from pathlib import Path

from build_package import APP_NAME, distribution_zip_filename

from app.services.system_info_service import read_app_version

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DIST_DIR = BACKEND_DIR / "dist"


def release_tag(version: str) -> str:
    """公開済みリリース（`ver1.0.0`/`ver1.1.0`）と同じタグ命名を返す。

    タグ名は公開済みリリースのURLに含まれ、READMEや外部からの参照先になるため、
    既存の命名へスクリプト側を合わせる（過去タグの付け替えは参照を壊すため行わない）。
    """
    return f"ver{version}"


def release_title(version: str) -> str:
    """公開済みリリース（`Michinari-v1.0.0`/`Michinari-v1.1.0`）と同じ表題を返す。"""
    return f"{APP_NAME}-v{version}"


def build_release_command(version: str, zip_path: Path) -> list[str]:
    return [
        "gh",
        "release",
        "create",
        release_tag(version),
        str(zip_path),
        "--title",
        release_title(version),
        "--generate-notes",
    ]


def build_upload_command(version: str, zip_path: Path) -> list[str]:
    return ["gh", "release", "upload", release_tag(version), str(zip_path), "--clobber"]


def publish(version: str, zip_path: Path) -> None:
    """`v{version}`タグでリリースを作成し、zipを添付する。

    タグが既存の場合（`gh release create`が失敗する場合）は、同名タグへの
    アップロードへ切り替える（`--clobber`で既存アセットを差し替え）。`gh`の
    エラーメッセージ文字列で「タグ既存」かどうかを判定する（CLI出力形式への
    依存はもろいため）のではなく、常にcreateを試みてから失敗時にuploadへ
    フォールバックする方式に統一する。
    """
    if not zip_path.is_file():
        print(f"エラー: {zip_path} が見つかりません。先に build_package.py を実行してください。")
        raise SystemExit(1)

    result = subprocess.run(build_release_command(version, zip_path), cwd=REPO_ROOT)
    if result.returncode != 0:
        print("既存リリースの可能性があるため、アップロードで差し替えます…")
        fallback = subprocess.run(build_upload_command(version, zip_path), cwd=REPO_ROOT)
        if fallback.returncode != 0:
            raise SystemExit(fallback.returncode)


def main() -> None:
    version = read_app_version(REPO_ROOT)
    zip_path = DIST_DIR / distribution_zip_filename(APP_NAME, version)
    publish(version, zip_path)


if __name__ == "__main__":
    sys.exit(main())
