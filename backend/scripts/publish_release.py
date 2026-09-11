"""配布パッケージをGitHub Releasesへ公開するスクリプト（OPERATIONS.md 7.4参照）。

`build_package.py`とは独立しており、ビルドスクリプトから自動的に呼び出されることはない。
公開はGitHub上で他者から見える操作であるため、開発者が公開したいタイミングで明示的に
実行する（CLAUDE.md「マージは開発者が手動実施」と同じ考え方で、公開も自動化の対象外とする）。

リリースノートは2層構成とする。Release本文には`docs/release-notes/v{version}.md`の
要約ブロックのみを載せ、全変更点は同ファイルへのリンクで示す。Releases一覧ページは各
リリースの本文を全文レンダリングするため、本文が長いと配布zip（Assets）が画面下へ埋もれ、
利用者が目的のバージョンを見つけられなくなることへの対処である。

実行例（backendディレクトリから、事前に `uv run python scripts/build_package.py` でzipを
生成しておくこと）: `uv run python scripts/publish_release.py`
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from build_package import APP_NAME, distribution_zip_filename

from app.services.system_info_service import read_app_version

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DIST_DIR = BACKEND_DIR / "dist"

REPOSITORY_URL = "https://github.com/teppei19980914/Michinari"
RELEASE_NOTES_DIR = "docs/release-notes"
SUMMARY_START = "<!-- summary:start -->"
SUMMARY_END = "<!-- summary:end -->"


def release_tag(version: str) -> str:
    """公開済みリリース（`ver1.0.0`〜`ver1.2.0`）と同じタグ命名を返す。

    タグ名は公開済みリリースのURLに含まれ、READMEや外部からの参照先になるため、
    既存の命名へスクリプト側を合わせる（過去タグの付け替えは参照を壊すため行わない）。
    """
    return f"ver{version}"


def release_title(version: str) -> str:
    """公開済みリリース（`Michinari-v1.0.0`〜`Michinari-v1.2.0`）と同じ表題を返す。"""
    return f"{APP_NAME}-v{version}"


def release_notes_relative_path(version: str) -> str:
    """詳細リリースノートのリポジトリ相対パス（ファイル実体とURLの単一の情報源）。"""
    return f"{RELEASE_NOTES_DIR}/v{version}.md"


def release_notes_path(repo_root: Path, version: str) -> Path:
    return repo_root / release_notes_relative_path(version)


def release_notes_url(version: str) -> str:
    """詳細リリースノートの参照先URL。

    タグではなく`main`を指す。過去バージョンのタグには当該ファイルが含まれないうえ、
    ノートの誤記を後から直した場合にRelease本文からのリンク先へも反映させたいため。
    """
    return f"{REPOSITORY_URL}/blob/main/{release_notes_relative_path(version)}"


def extract_summary(notes_markdown: str) -> str:
    """詳細リリースノートから要約ブロック（マーカーで囲まれた範囲）を取り出す。"""
    start = notes_markdown.find(SUMMARY_START)
    end = notes_markdown.find(SUMMARY_END)
    if start == -1 or end == -1 or end < start:
        raise ValueError(
            f"要約ブロックが見つかりません。{SUMMARY_START} と {SUMMARY_END} で囲んでください。"
        )
    return notes_markdown[start + len(SUMMARY_START) : end].strip()


def build_release_body(version: str, summary: str) -> str:
    """Release本文（ダウンロード導線 + 要約 + 詳細ノートへのリンク）を組み立てる。

    配布zipのファイル名は`build_package.distribution_zip_filename`に集約しているため、
    本文中でも同関数から導出して二重管理を避ける。
    """
    zip_filename = distribution_zip_filename(APP_NAME, version)
    return "\n".join(
        [
            f"**ダウンロード**: 下の Assets から `{zip_filename}` "
            f"→ [インストールと使いかた]({REPOSITORY_URL}/blob/main/README.md)",
            "",
            summary,
            "",
            "📄 [**詳細なリリースノート（全変更点・開発者向け補足）**]"
            f"({release_notes_url(version)})",
            "",
        ]
    )


def build_release_command(version: str, zip_path: Path, body_path: Path) -> list[str]:
    return [
        "gh",
        "release",
        "create",
        release_tag(version),
        str(zip_path),
        "--title",
        release_title(version),
        "--notes-file",
        str(body_path),
    ]


def build_edit_command(version: str, body_path: Path) -> list[str]:
    """既存リリースの本文を差し替えるコマンド（再公開時にノートを最新化するため）。"""
    return [
        "gh",
        "release",
        "edit",
        release_tag(version),
        "--title",
        release_title(version),
        "--notes-file",
        str(body_path),
    ]


def build_upload_command(version: str, zip_path: Path) -> list[str]:
    return ["gh", "release", "upload", release_tag(version), str(zip_path), "--clobber"]


def publish(version: str, zip_path: Path, notes_path: Path) -> None:
    """`ver{version}`タグでリリースを作成し、zipと要約版の本文を添付する。

    タグが既存の場合（`gh release create`が失敗する場合）は、本文の差し替え
    （`gh release edit`）とアセットの差し替え（`gh release upload --clobber`）へ
    切り替える。`gh`のエラーメッセージ文字列で「タグ既存」かどうかを判定する
    （CLI出力形式への依存はもろいため）のではなく、常にcreateを試みてから失敗時に
    フォールバックする方式に統一する。
    """
    if not zip_path.is_file():
        print(f"エラー: {zip_path} が見つかりません。先に build_package.py を実行してください。")
        raise SystemExit(1)
    if not notes_path.is_file():
        print(f"エラー: {notes_path} が見つかりません。詳細リリースノートを作成してください。")
        raise SystemExit(1)

    body = build_release_body(version, extract_summary(notes_path.read_text(encoding="utf-8")))
    with tempfile.TemporaryDirectory() as work_dir:
        body_path = Path(work_dir) / "release_body.md"
        body_path.write_text(body, encoding="utf-8")

        result = subprocess.run(build_release_command(version, zip_path, body_path), cwd=REPO_ROOT)
        if result.returncode == 0:
            return

        print("既存リリースの可能性があるため、本文とアセットを差し替えます…")
        edited = subprocess.run(build_edit_command(version, body_path), cwd=REPO_ROOT)
        if edited.returncode != 0:
            raise SystemExit(edited.returncode)
        uploaded = subprocess.run(build_upload_command(version, zip_path), cwd=REPO_ROOT)
        if uploaded.returncode != 0:
            raise SystemExit(uploaded.returncode)


def main() -> None:
    version = read_app_version(REPO_ROOT)
    zip_path = DIST_DIR / distribution_zip_filename(APP_NAME, version)
    publish(version, zip_path, release_notes_path(REPO_ROOT, version))


if __name__ == "__main__":
    sys.exit(main())
