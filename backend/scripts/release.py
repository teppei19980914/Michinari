"""修正のマージから公開までを一続きで実行するリリーススクリプト（OPERATIONS.md 7.4参照）。

`main`へのマージ → パッケージビルド → GitHub Releasesへの公開を1コマンドで行う。
手順を人が順に叩く運用では、工程の飛ばしや順序違いが事故になっていた。

- ビルド前に`main`へマージしないと、詳細リリースノートへのリンクが404になる
- マージ後に`main`が進んでからビルドすると、配布物とタグが食い違う
- 公開前にローカルへ古い同名タグがあると、ghがそれを押し出して`--target`を無視する
  （2026-09-12のv1.2.1で実際に発生）

各工程の実体は既存スクリプト（`build_package.py` / `publish_release.py`）に置いたまま、
本スクリプトは順序と事前検証だけを担う（CLAUDE.md DRYの原則）。

実行例（backendディレクトリから）:

- `uv run python scripts/release.py 1.2.2`
  マージから公開まで通しで行う。詳細リリースノートを先に用意しておく必要がある。

- `uv run python scripts/release.py --skip-merge --draft`（`release.bat`が呼ぶ形）
  main へマージ済みの状態から実行する。mainへの切り替えと最新化を自前で行うため、
  ローカルがdevブランチのままでもよい。テストを通してからコンソールでバージョンを
  尋ね、パッケージ・タグ・zip添付まで済ませた**下書き**リリースを作る。リリースノートは
  作成後にGitHubの画面で書き換えて公開する。ノートを書く前に配布物とタグを確定でき、
  人の作業を「本文を書く」1点に絞れる。
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


def verify_workspace() -> None:
    """バージョンに依らない前提（作業ツリーの状態）を検証する。

    バージョン入力より前に確認する。入力させた後で「未コミットの変更があります」と
    言われるのは手間の無駄なため。
    """
    if has_uncommitted_changes():
        raise SystemExit(
            "エラー: 未コミットの変更があります。コミットまたは退避してから実行してください"
            "（配布物と公開されるソースを一致させるため）。"
        )


def is_content_merged_into_base() -> bool:
    """現在の作業内容が`origin/main`に取り込まれているかを、ツリーの一致で判定する。

    コミットの祖先関係では判定できない。PRをsquashマージすると、取り込み済みでも
    元ブランチのコミットは`origin/main`の祖先にならないため
    （`git merge-base --is-ancestor`は偽を返す）。一方、取り込まれていれば内容は同一に
    なるので、ツリー同士を比較する。

    この判定を省いて無条件に`main`へ切り替えると、マージし忘れた状態で実行したときに
    作業内容を含まないパッケージを配布してしまう（CLAUDE.md「未マージのままmainから
    当日ブランチを切ると前日の成果が作業ツリーから消える」と同種の取りこぼし）。
    """
    return run_git("diff", "--quiet", f"origin/{BASE_BRANCH}", "HEAD", check=False).returncode == 0


def ensure_base_is_checked_out() -> str:
    """`main`を最新の状態でチェックアウトし、そのコミットを返す。

    マージを行わない実行（`--skip-merge`）では、ビルドは作業ツリーの内容から作られる
    一方で「ビルド元コミット」は`origin/main`として扱われる。両者がずれていると、
    配布物と異なるコミットにタグが付く（v1.2.1と同種の事故）。

    以前は一致していなければ中止し、`git checkout main && git pull`を人にやらせていたが、
    GitHub上でPRをマージした直後は必ずこの状態になるため、毎回の手作業になっていた。
    作業内容が取り込み済みであることを確認したうえで、ここで切り替えまで行う。
    """
    run_git("fetch", "origin")
    base = run_git("rev-parse", f"origin/{BASE_BRANCH}").stdout.strip()
    head = run_git("rev-parse", "HEAD").stdout.strip()
    if head == base:
        return base

    if not is_content_merged_into_base():
        raise SystemExit(
            f"エラー: 作業内容が origin/{BASE_BRANCH}（{base[:8]}）に取り込まれていません。"
            f"先に {BASE_BRANCH} へマージしてから実行してください"
            "（この状態で進めると、変更を含まないパッケージを配布することになります）。"
        )

    print(f"  → {BASE_BRANCH} へ切り替えて最新化します（{head[:8]} → {base[:8]}）")
    run_git("checkout", BASE_BRANCH)
    result = run_git("merge", "--ff-only", f"origin/{BASE_BRANCH}", check=False)
    if result.returncode != 0:
        raise SystemExit(
            f"エラー: ローカルの {BASE_BRANCH} を origin/{BASE_BRANCH} へ"
            "fast-forward できませんでした（履歴が分岐しています）。"
            "手動で最新化してから実行してください。"
        )
    return base


def verify_preconditions(version: str, *, require_notes: bool) -> None:
    """指定バージョンで公開してよい状態かを、変更を加える前に検証する。

    途中まで進んでから失敗すると、マージ済みだがタグが無い等の中途半端な状態が残る。
    取り返しのつかない操作（マージ・公開）の前に、確認できるものは全て確認する。

    `require_notes=False`（下書き公開）では詳細ノートの存在を求めない。ノートは公開後に
    GitHubの画面で書く運用のため（`publish_release.build_placeholder_body`参照）。
    ただしノートが存在する場合は、要約ブロックが読めるかをここで確認する。
    """
    if not _SEMVER_PATTERN.fullmatch(version):
        raise SystemExit(f"エラー: バージョンは N.N.N 形式で指定してください（指定値: {version}）")

    notes_path = publish_release.release_notes_path(REPO_ROOT, version)
    if not notes_path.is_file():
        if require_notes:
            raise SystemExit(
                f"エラー: リリースノート {notes_path} がありません。"
                "先に作成してください（Release本文はこのファイルの要約ブロックから作られます）。"
            )
    else:
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


def prompt_version(current_version: str, *, prompt=input) -> str:
    """配布バージョンをコンソールから入力させる。

    テストが全て通った後にだけ呼ぶ（品質ゲートを通過していないビルドのために
    バージョンを考えさせない）。`build_package.resolve_version`と役割は似ているが、
    こちらはリリースタグに使うため`N.N.N`形式のみを許可する点が異なる。
    """
    while True:
        entered = prompt(f"配布バージョンを入力してください（現在: {current_version}）: ").strip()
        if not entered:
            print("  → バージョンが未入力です。")
            continue
        if not _SEMVER_PATTERN.fullmatch(entered):
            print("  → バージョンは N.N.N 形式で入力してください（例: 1.2.2）。")
            continue
        return entered


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


def build(version: str, *, skip_tests: bool = False) -> Path:
    """`build_package.py`の各工程を、バージョンを対話入力させずに実行する。

    `skip_tests=True`は、バージョン入力より前に既にテストを通してある場合に使う
    （同じテストを二度流さないため）。テスト自体を省く手段としては使わない。
    """
    print(f"[2/4] バージョン {version} でパッケージをビルドしています…")
    if not skip_tests:
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


def publish(version: str, zip_path: Path, *, draft: bool) -> None:
    label = "下書きとして作成" if draft else "公開"
    print(f"[3/4] GitHub Releases へ{label}しています…")
    publish_release.publish(
        version,
        zip_path,
        publish_release.build_commit_path(build_package.DIST_DIR, version),
        draft=draft,
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


def print_draft_next_steps(version: str) -> None:
    """下書き作成後に、人が何をすればよいかを示す。

    下書きは作成者にしか見えず、放置すると配布されないまま忘れられる。次の操作を
    その場に出しておく（OPERATIONS.md 7.4の手順と同じ内容）。
    """
    tag = publish_release.release_tag(version)
    print()
    print("下書きリリースを作成しました。配布するには、次の操作を行ってください。")
    print(f"  1. {publish_release.REPOSITORY_URL}/releases を開く")
    print(f"  2. 下書き（Draft）の {publish_release.release_title(version)} を編集する")
    print("  3. 本文のひな形をリリースノートへ書き換える")
    print("  4. 「Publish release」を押して公開する")
    print(f"     タグ {tag} と配布zipは作成済みのため、本文の編集だけで配布できます。")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="マージ・ビルド・公開を一続きで実行する（OPERATIONS.md 7.4）"
    )
    parser.add_argument(
        "version",
        nargs="?",
        help="公開するバージョン（例: 1.2.2）。省略するとテスト通過後にコンソールで尋ねる",
    )
    parser.add_argument(
        "--skip-merge",
        action="store_true",
        help="mainへのマージを行わない（既にマージ済みの場合）",
    )
    parser.add_argument(
        "--draft",
        action="store_true",
        help="下書きとして作成する（リリースノートは公開後にGitHubの画面で記入する）",
    )
    args = parser.parse_args()

    verify_workspace()

    # マージしない実行では、mainを最新の状態にしてから始める。テスト（数分かかる）と
    # バージョン入力の後で中止されるのは手間の無駄なため、確認・準備は全て前に出す。
    checked_out_commit = ensure_base_is_checked_out() if args.skip_merge else None

    # バージョンを省略した場合は、テストを通してから尋ねる（要件: 本番リリース判定が
    # OKだと判断できたらバージョン入力欄を表示する）。通らないビルドのためにバージョンを
    # 考えさせない。
    version = args.version
    tested = False
    if version is None:
        print("[0/4] テストスイートを実行しています（本番リリース判定）…")
        build_package.run_tests()
        print("  → すべて成功しました。リリース判定 OK")
        print()
        version = prompt_version(build_package.read_current_version(build_package.PYPROJECT_PATH))
        tested = True

    verify_preconditions(version, require_notes=not args.draft)

    if checked_out_commit is not None:
        build_commit = checked_out_commit
        print(f"[1/4] マージをスキップします（{BASE_BRANCH} は {build_commit[:8]}）")
    else:
        build_commit = merge_to_base(version)

    zip_path = build(version, skip_tests=tested)
    publish(version, zip_path, draft=args.draft)
    verify_published(version, build_commit)
    if args.draft:
        print_draft_next_steps(version)
    else:
        print("リリースが完了しました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
