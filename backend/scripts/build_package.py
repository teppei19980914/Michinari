"""配布パッケージのビルドスクリプト（PyInstallerでの単一実行ファイル化、OPERATIONS.md参照）。

実行順序: 既存パッケージのアーカイブ退避 → ビルド情報（バージョン・使用ライブラリ）の生成 →
フロントエンドの静的ビルド（`npm run build`）→ PyInstallerによるバックエンドのパッケージ化
（フロントエンドの静的ファイル・alembicマイグレーション・ビルド情報を同梱）→
起動用batファイルの配置 → 配布用zipの作成。

実行例（backendディレクトリから）: `uv run python scripts/build_package.py`
（`backend/build.bat` をダブルクリックしても同じ処理を実行できる）。

出力先: `backend/dist/Michinari/`（`Michinari.exe` と `Michinari.bat` を含む。この
フォルダごと他端末へコピーし、`Michinari.bat` をダブルクリックすれば起動できる）に加え、
同フォルダをzip化した `backend/dist/Michinari.zip` も生成する（配布時はzipを渡すだけでよい）。
zipは毎回のビルドで上書きされ、退避対象（アーカイブ処理）には含まれない。

GitHub Releasesへの公開は本スクリプトでは行わない（`scripts/publish_release.py`参照。
ビルドと公開を分離し、公開は開発者が明示的に実行する）。
"""

import datetime as dt
import os
import shutil
import subprocess
import sys
from pathlib import Path

from app.services.system_info_service import build_info_to_json, collect_build_info

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
APP_NAME = "Michinari"
DIST_DIR = BACKEND_DIR / "dist"
OUTPUT_DIR = DIST_DIR / APP_NAME
ARCHIVE_DIR = DIST_DIR / "_archive"
BUILD_INFO_PATH = BACKEND_DIR / "build_info.json"


def archive_previous_package(
    output_dir: Path, archive_dir: Path, app_name: str, *, now: dt.datetime | None = None
) -> Path | None:
    """既存の配布パッケージをタイムスタンプ付きフォルダへ退避する（削除せず残す）。

    以前のパッケージと最新パッケージを比較調査できるようにするため、PyInstallerに
    既存出力先の削除を任せず、本スクリプト側で先にリネーム（`shutil.move`）で
    退避しておく。リネームはディレクトリエントリの付け替えのみで再帰的なファイル削除を
    伴わないため、OneDriveファイルオンデマンド配下でリパースポイント化された
    ディレクトリを`shutil.rmtree`で削除しようとして`WinError 5`になる問題
    （OPERATIONS.md参照）も併せて回避できる。

    戻り値: 退避先のパス。既存パッケージが無ければ何もせず`None`を返す。
    """
    if not output_dir.exists():
        return None
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = (now or dt.datetime.now()).strftime("%Y%m%d_%H%M%S")
    destination = archive_dir / f"{app_name}_{timestamp}"
    shutil.move(str(output_dir), str(destination))
    return destination


def generate_build_info(
    repo_root: Path, output_path: Path, *, now: dt.datetime | None = None
) -> Path:
    """アプリバージョン・使用ライブラリのスナップショットを`build_info.json`へ書き出す。

    ここで生成したファイルはPyInstallerの`--add-data`で配布パッケージへ同梱し、
    配布exe（frozen実行時）はこのファイルを読むだけにする
    （`app/services/system_info_service.py`のモジュールdocstring参照。frozen環境では
    `importlib.metadata`がdist-info情報を保持しない場合があるため、ビルド時＝
    依存関係が正しくインストールされたこの環境でのみライブ計算する）。
    """
    built_at = (now or dt.datetime.now(dt.UTC)).isoformat()
    build_info = collect_build_info(repo_root, built_at=built_at)
    output_path.write_text(build_info_to_json(build_info), encoding="utf-8")
    return output_path


def build_frontend() -> None:
    print("[3/6] フロントエンドをビルドしています…")
    subprocess.run(["npm", "run", "build"], cwd=FRONTEND_DIR, check=True, shell=True)


def build_backend() -> None:
    print("[4/6] PyInstallerでバックエンドをパッケージ化しています…")
    add_data = [
        f"{FRONTEND_DIST_DIR}{os.pathsep}frontend_dist",
        f"{BACKEND_DIR / 'alembic.ini'}{os.pathsep}.",
        f"{BACKEND_DIR / 'alembic'}{os.pathsep}alembic",
        f"{BUILD_INFO_PATH}{os.pathsep}.",
    ]
    args = [sys.executable, "-m", "PyInstaller", "--name", APP_NAME, "--noconfirm"]
    for entry in add_data:
        args += ["--add-data", entry]
    args.append(str(BACKEND_DIR / "app" / "main.py"))
    subprocess.run(args, cwd=BACKEND_DIR, check=True)


def assemble_launcher() -> None:
    print("[5/6] 起動用batファイルを配置しています…")
    launcher_src = BACKEND_DIR / "scripts" / "launcher_template.bat"
    launcher_dst = OUTPUT_DIR / f"{APP_NAME}.bat"
    shutil.copy(launcher_src, launcher_dst)
    print(f"完了: {OUTPUT_DIR}")


def create_distribution_zip(output_dir: Path, dist_dir: Path, app_name: str) -> Path:
    """ビルド済みパッケージフォルダをzip化し、配布時のコピー手間を省く。

    既存パッケージのアーカイブ退避（`archive_previous_package`）はビルド前に
    `output_dir`（例: `backend/dist/Michinari/`）をリネーム退避する処理であり、
    本関数はビルド後に生成された最新の`output_dir`のみをzip化するため、退避処理
    とは対象・実行順序の両面で独立している。zip出力先（`dist_dir`直下）は退避先
    （`dist_dir/_archive/`）と重ならないため、退避処理が誤って新しいzipを巻き込む
    ことも、zip化が退避済みの旧パッケージを巻き込むこともない。

    戻り値: 生成したzipファイルのパス。zipは毎回のビルドで上書きされる（旧版の
    zipを履歴として残す必要があれば、`_archive/`配下の該当フォルダを手動でzip化する）。
    """
    archive_path = shutil.make_archive(
        base_name=str(dist_dir / app_name),
        format="zip",
        root_dir=str(dist_dir),
        base_dir=app_name,
    )
    return Path(archive_path)


def main() -> None:
    print("[1/6] 既存パッケージを確認しています…")
    archived_to = archive_previous_package(OUTPUT_DIR, ARCHIVE_DIR, APP_NAME)
    if archived_to:
        print(f"  → 既存パッケージを退避しました: {archived_to}")
    else:
        print("  → 既存パッケージはありません")

    print("[2/6] ビルド情報（バージョン・使用ライブラリ）を生成しています…")
    generate_build_info(REPO_ROOT, BUILD_INFO_PATH)

    build_frontend()
    build_backend()
    assemble_launcher()

    print("[6/6] 配布用zipを作成しています…")
    zip_path = create_distribution_zip(OUTPUT_DIR, DIST_DIR, APP_NAME)
    print(f"完了: {zip_path}")


if __name__ == "__main__":
    main()
