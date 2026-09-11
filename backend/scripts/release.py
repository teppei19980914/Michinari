"""修正のマージから公開までを一続きで実行するリリーススクリプト（OPERATIONS.md 7.4参照）。

`main`へのマージ → パッケージビルド → GitHub Releasesへの公開を1コマンドで行う。
手順を人が順に叩く運用では、工程の飛ばしや順序違いが事故になっていた。

- ビルド前に`main`へマージしないと、詳細リリースノートへのリンクが404になる
- マージ後に`main`が進んでからビルドすると、配布物とタグが食い違う
- 公開前にローカルへ古い同名タグがあると、ghがそれを押し出して`--target`を無視する
  （2026-09-12のv1.2.1で実際に発生）

各工程の実体は既存スクリプト（`build_package.py` / `publish_release.py`）に置いたまま、
本スクリプトは順序と事前検証だけを担う（CLAUDE.md DRYの原則）。

実行例（backendディレクトリから）: `uv run python scripts/release.py 1.2.2`
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

import build_package
import publish_release

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
#: 公開対象の基準ブランチ。ここへマージ済みであることを公開の前提とする。
BASE_BRANCH = "main"
#: バージョン文字列の形式。`build_package._VALID_VERSION_PATTERN`より厳しく、
#: リリースタグとして使う`N.N.N`形式のみを許可する（タグ名の揺れを防ぐ）。
_SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=check
    )


def current_branch() -> str:
    return run_git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def has_uncommitted_changes() -> bool:
    return bool(run_git("status", "--porcelain").stdout.strip())


def verify_preconditions(version: str) -> None:
    """公開してよい状態かを、変更を加える前にまとめて検証する。

    途中まで進んでから失敗すると、マージ済みだがタグが無い等の中途半端な状態が残る。
    取り返しのつかない操作（マージ・公開）の前に、確認できるものは全て確認する。
    """
    if not _SEMVER_PATTERN.fullmatch(version):
        raise SystemExit(f"エラー: バージョンは N.N.N 形式で指定してください（指定値: {version}）")

    if has_uncommitted_changes():
        raise SystemExit(
            "エラー: 未コミットの変更があります。コミットまたは退避してから実行してください"
            "（配布物と公開されるソースを一致させるため）。"
        )

    notes_path = publish_release.release_notes_path(REPO_ROOT, version)
    if not notes_path.is_file():
        raise SystemExit(
            f"エラー: リリースノート {notes_path} がありません。"
            "先に作成してください（Release本文はこのファイルの要約ブロックから作られます）。"
        )
    try:
        publish_release.extract_summary(notes_path.read_text(encoding="utf-8"))
    except ValueError as error:
        # 公開直前ではなくここで止める（マージ済みだがタグが無い中途半端な状態を作らない）。
        raise SystemExit(f"エラー: {notes_path} の要約ブロックが読めません: {error}") from error

    tag = publish_release.release_tag(version)
    remote_tag_commit = publish_release.read_remote_tag_commit(REPO_ROOT, tag)
    if remote_tag_commit is not None:
        raise SystemExit(
            f"エラー: タグ {tag} は既にリモートに存在します（{remote_tag_commit[:8]}）。"
            "公開済みのバージョンは上書きしません。別のバージョンで実行してください。"
        )


def merge_to_base(version: str) -> str:
    """現在のブランチを`main`へマージし、マージ後の`main`のコミットSHAを返す。

    既に`main`にいる場合はマージ操作を行わない（`main`で直接作業する運用も許す）。
    戻り値をビルド元コミットとして扱うため、マージ後に必ず`main`をpullし直す。
    """
    branch = current_branch()
    if branch != BASE_BRANCH:
        print(f"[1/4] {branch} を {BASE_BRANCH} へマージしています…")
        run_git("push", "--set-upstream", "origin", branch, check=False)
        title = f"v{version}"
        body = (
            f"v{version} のリリース。変更点は docs/release-notes/v{version}.md を参照。\n\n"
            "🤖 Generated with [Claude Code](https://claude.com/claude-code)"
        )
        create = subprocess.run(
            [
                "gh",
                "pr",
                "create",
                "--base",
                BASE_BRANCH,
                "--head",
                branch,
                "--title",
                title,
                "--body",
                body,
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        # PRが既にある場合もmergeへ進める（createの失敗理由はmerge側で明らかになる）。
        if create.returncode == 0:
            print(f"  → PR を作成しました: {create.stdout.strip()}")
        merged = subprocess.run(["gh", "pr", "merge", branch, "--squash"], cwd=REPO_ROOT)
        if merged.returncode != 0:
            raise SystemExit(
                "エラー: PR のマージに失敗しました。GitHub 上の状態を確認してください。"
            )
    else:
        print(f"[1/4] 既に {BASE_BRANCH} にいるためマージをスキップします")

    run_git("fetch", "origin")
    run_git("checkout", BASE_BRANCH)
    run_git("merge", "--ff-only", f"origin/{BASE_BRANCH}")
    commit = run_git("rev-parse", "HEAD").stdout.strip()
    print(f"  → {BASE_BRANCH} は {commit[:8]} です")
    return commit


def build(version: str) -> Path:
    """`build_package.py`の各工程を、バージョンを対話入力させずに実行する。"""
    print(f"[2/4] バージョン {version} でパッケージをビルドしています…")
    build_package.run_tests()
    dirty = build_package.has_uncommitted_changes(REPO_ROOT)
    commit = build_package.read_git_commit(REPO_ROOT)
    if build_package.read_current_version(build_package.PYPROJECT_PATH) != version:
        build_package.write_version(build_package.PYPROJECT_PATH, version)
        print(f"  → pyproject.toml のバージョンを {version} へ更新しました")
    build_package.archive_previous_package(
        build_package.OUTPUT_DIR, build_package.ARCHIVE_DIR, build_package.APP_NAME
    )
    build_package.generate_build_info(REPO_ROOT, build_package.BUILD_INFO_PATH)
    build_package.build_frontend()
    build_package.build_backend()
    build_package.assemble_launcher()
    zip_path = build_package.create_distribution_zip(
        build_package.OUTPUT_DIR, build_package.DIST_DIR, build_package.APP_NAME, version
    )
    build_package.generate_build_commit(
        build_package.DIST_DIR
        / build_package.build_commit_filename(build_package.APP_NAME, version),
        version,
        commit,
        dirty=dirty,
    )
    print(f"  → {zip_path}")
    return zip_path


def publish(version: str, zip_path: Path) -> None:
    print("[3/4] GitHub Releases へ公開しています…")
    publish_release.publish(
        version,
        zip_path,
        publish_release.release_notes_path(REPO_ROOT, version),
        publish_release.build_commit_path(build_package.DIST_DIR, version),
    )


def verify_published(version: str, build_commit: str) -> None:
    """公開後に、タグが本当にビルド元コミットを指しているかを検証する。

    v1.2.1では`--target`が無視されてタグが別コミットへ付いたが、Release情報の
    `target_commitish`には指定値が入るため、Releaseだけを見ても気付けなかった。
    リモートのタグ実体を見て突き合わせる。
    """
    print("[4/4] 公開結果を検証しています…")
    tag = publish_release.release_tag(version)
    tag_commit = publish_release.read_remote_tag_commit(REPO_ROOT, tag)
    if tag_commit != build_commit:
        raise SystemExit(
            f"エラー: タグ {tag} が {tag_commit} を指しています"
            f"（ビルド元は {build_commit}）。手動で付け替えてください。"
        )
    print(f"  → タグ {tag} はビルド元 {build_commit[:8]} を指しています")
    print(f"  → {publish_release.REPOSITORY_URL}/releases/tag/{tag}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="マージ・ビルド・公開を一続きで実行する（OPERATIONS.md 7.4）"
    )
    parser.add_argument("version", help="公開するバージョン（例: 1.2.2）")
    parser.add_argument(
        "--skip-merge",
        action="store_true",
        help="mainへのマージを行わない（既にマージ済みの場合）",
    )
    args = parser.parse_args()

    verify_preconditions(args.version)
    if args.skip_merge:
        run_git("fetch", "origin")
        build_commit = run_git("rev-parse", f"origin/{BASE_BRANCH}").stdout.strip()
        print(f"[1/4] マージをスキップします（{BASE_BRANCH} は {build_commit[:8]}）")
    else:
        build_commit = merge_to_base(args.version)

    zip_path = build(args.version)
    publish(args.version, zip_path)
    verify_published(args.version, build_commit)
    print("リリースが完了しました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
