"""配布パッケージのビルドスクリプト（PyInstallerでの単一実行ファイル化、OPERATIONS.md参照）。

実行順序: フロントエンドの静的ビルド（`npm run build`）→ PyInstallerによる
バックエンドのパッケージ化（フロントエンドの静的ファイル・alembicマイグレーションを同梱）→
起動用batファイルの配置。

実行例（backendディレクトリから）: `uv run python scripts/build_package.py`

出力先: `backend/dist/Michinari/`（`Michinari.exe` と `Michinari.bat` を含む。この
フォルダごと他端末へコピーし、`Michinari.bat` をダブルクリックすれば起動できる）。
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
APP_NAME = "Michinari"
OUTPUT_DIR = BACKEND_DIR / "dist" / APP_NAME


def build_frontend() -> None:
    print("[1/3] フロントエンドをビルドしています…")
    subprocess.run(["npm", "run", "build"], cwd=FRONTEND_DIR, check=True, shell=True)


def build_backend() -> None:
    print("[2/3] PyInstallerでバックエンドをパッケージ化しています…")
    add_data = [
        f"{FRONTEND_DIST_DIR}{os.pathsep}frontend_dist",
        f"{BACKEND_DIR / 'alembic.ini'}{os.pathsep}.",
        f"{BACKEND_DIR / 'alembic'}{os.pathsep}alembic",
    ]
    args = [sys.executable, "-m", "PyInstaller", "--name", APP_NAME, "--noconfirm"]
    for entry in add_data:
        args += ["--add-data", entry]
    args.append(str(BACKEND_DIR / "app" / "main.py"))
    subprocess.run(args, cwd=BACKEND_DIR, check=True)


def assemble_launcher() -> None:
    print("[3/3] 起動用batファイルを配置しています…")
    launcher_src = BACKEND_DIR / "scripts" / "launcher_template.bat"
    launcher_dst = OUTPUT_DIR / f"{APP_NAME}.bat"
    shutil.copy(launcher_src, launcher_dst)
    print(f"完了: {OUTPUT_DIR}")


def main() -> None:
    build_frontend()
    build_backend()
    assemble_launcher()


if __name__ == "__main__":
    main()
