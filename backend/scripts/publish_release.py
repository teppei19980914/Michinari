"""配布パッケージをGitHub Releasesへ公開するスクリプト（OPERATIONS.md 7.4参照）。

`build_package.py`とは独立しており、ビルドスクリプトから自動的に呼び出されることはない。
公開の起点は常に人の操作とし、ビルドの副作用では公開しない（公開はGitHub上で他者から
見える操作のため）。通常は`release.py`（`release.bat`）が工程の一つとして本モジュールの
`publish`を呼ぶが、その`release.py`自体を人が実行する点は変わらない。

リリースノートは2層構成とする。Release本文には`docs/release-notes/v{version}.md`の
要約ブロックのみを載せ、全変更点は同ファイルへのリンクで示す。Releases一覧ページは各
リリースの本文を全文レンダリングするため、本文が長いと配布zip（Assets）が画面下へ埋もれ、
利用者が目的のバージョンを見つけられなくなることへの対処である。

詳細ノートを用意せずに公開することもできる。その場合は記入用のひな形を本文に載せ、
ノートは公開後にGitHubの画面で書く（`resolve_release_body`・`build_placeholder_body`）。
未記載のまま一般公開されないよう、その経路は下書き作成（`draft=True`）と組み合わせる。

実行例（backendディレクトリから、事前に `uv run python scripts/build_package.py` でzipを
生成しておくこと）: `uv run python scripts/publish_release.py`
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from build_package import APP_NAME, build_commit_filename, distribution_zip_filename

from app.services.system_info_service import read_app_version

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DIST_DIR = BACKEND_DIR / "dist"

REPOSITORY_URL = "https://github.com/teppei19980914/Michinari"
RELEASE_NOTES_DIR = "docs/release-notes"
SUMMARY_START = "<!-- summary:start -->"
SUMMARY_END = "<!-- summary:end -->"
#: タグを付ける対象を検証する基準ブランチ。配布物のコミットがここへマージ済みで
#: あることを公開の前提とする（未マージのまま公開すると、GitHubがタグを作れないか、
#: 詳細リリースノートへのリンクが404になる）。
BASE_BRANCH_REF = "origin/main"


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


def build_download_line(version: str) -> str:
    """Release本文の先頭に置くダウンロード導線。

    配布zipのファイル名は`build_package.distribution_zip_filename`に集約しているため、
    本文中でも同関数から導出して二重管理を避ける（CLAUDE.md DRYの原則）。
    """
    zip_filename = distribution_zip_filename(APP_NAME, version)
    return (
        f"**ダウンロード**: 下の Assets から `{zip_filename}` "
        f"→ [インストールと使いかた]({REPOSITORY_URL}/blob/main/README.md)"
    )


def build_release_body(version: str, summary: str) -> str:
    """Release本文（ダウンロード導線 + 要約 + 詳細ノートへのリンク）を組み立てる。"""
    return "\n".join(
        [
            build_download_line(version),
            "",
            summary,
            "",
            "📄 [**詳細なリリースノート（全変更点・開発者向け補足）**]"
            f"({release_notes_url(version)})",
            "",
        ]
    )


def build_placeholder_body(version: str) -> str:
    """詳細ノートが未作成のときのRelease本文（利用者が書き換えるひな形）。

    リリース作業を「先にノートを書く」前提から外し、パッケージとタグを先に用意して
    ノートは後からGitHubの画面で上書きする運用を可能にするためのもの。ひな形のまま
    一般公開されることを防ぐため、下書き（draft）での作成と組み合わせて使う
    （`release.py`の`--draft`）。

    詳細ノートへのリンクは載せない。ファイルが無い状態でリンクすると404になるため、
    2層構成を使う場合は`docs/release-notes/v{version}.md`を作ってから実行する
    （`resolve_release_body`がファイルの有無で自動的に切り替える）。
    """
    return "\n".join(
        [
            build_download_line(version),
            "",
            "> [!IMPORTANT]",
            "> **リリースノート未記載です。** 以下のひな形を書き換えてから公開してください",
            "> （この引用ブロックごと削除してください）。",
            "",
            "## このバージョンの変更",
            "",
            "- （変更点1）",
            "- （変更点2）",
            "",
            "## アップデート時のご注意",
            "",
            "- （特になければ「特にありません。"
            "これまでに入力した内容はそのまま引き継がれます。」）",
            "",
        ]
    )


def resolve_release_body(notes_path: Path, version: str) -> str:
    """詳細ノートの有無でRelease本文を切り替える。

    ノートがあり要約ブロックも読めるならそれを使い、無ければ記入用のひな形を返す。
    ノートはあるが要約ブロックが壊れている場合は、黙ってひな形へ落とすと書いた内容が
    失われたように見えるため、`extract_summary`が送出する例外をそのまま伝える。
    """
    if not notes_path.is_file():
        return build_placeholder_body(version)
    return build_release_body(version, extract_summary(notes_path.read_text(encoding="utf-8")))


def build_release_command(
    version: str, zip_path: Path, body_path: Path, *, draft: bool = False
) -> list[str]:
    """`--verify-tag`で「事前に作った正しいタグ」以外では公開しない。

    タグ作成をghの自動生成（`--target`）に任せない理由:
    `gh release create`は、同名のローカルタグが存在するとそれをリモートへpushし、
    `--target`の指定を無視する。2026-09-12のv1.2.1公開で、公開前に作られていた
    ローカルタグ（当時のmain先端）がそのまま押し出され、タグが配布物と異なるコミットを
    指す事故が起きた。Release側の`target_commitish`には`--target`の値が入るため、
    Releaseの情報だけを見ても食い違いに気付けない。

    そこで`ensure_release_tag`でビルド元コミットへタグを確定させてからここを呼び、
    `--verify-tag`（タグがリモートに無ければ中止）で取り違えを防ぐ。

    `draft=True`ではリリースノート未記載のまま一般公開しないよう下書きで作成する
    （`build_placeholder_body`参照）。ghの下書きは自身ではタグを作らないが、本関数を
    呼ぶ前に`ensure_release_tag`がgit側でタグを作成・pushするため、下書きの時点でも
    タグは付いた状態になる。
    """
    command = [
        "gh",
        "release",
        "create",
        release_tag(version),
        str(zip_path),
        "--title",
        release_title(version),
        "--verify-tag",
        "--notes-file",
        str(body_path),
    ]
    if draft:
        command.append("--draft")
    return command


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


def build_commit_path(dist_dir: Path, version: str) -> Path:
    """`build_package.py`が書き出した、ビルド元コミットの記録ファイルのパス。"""
    return dist_dir / build_commit_filename(APP_NAME, version)


def read_build_commit(commit_path: Path, version: str) -> str:
    """ビルド元コミットを読み、配布物と対応していることを検証して返す。

    記録が無い・gitが使えなかった・未コミットの変更があった・バージョンが食い違う
    場合は、タグを正しい位置へ付けられないため公開を中止する。
    """
    if not commit_path.is_file():
        raise SystemExit(
            f"エラー: {commit_path} が見つかりません。"
            "ビルド元コミットが不明なため公開できません。build_package.py を実行してください。"
        )
    record = json.loads(commit_path.read_text(encoding="utf-8"))
    if record.get("version") != version:
        raise SystemExit(
            f"エラー: ビルド元コミットの記録が別バージョン（{record.get('version')}）のものです。"
            "対象バージョンで build_package.py を実行し直してください。"
        )
    if record.get("dirty"):
        raise SystemExit(
            "エラー: 未コミットの変更がある状態でビルドされています。"
            "この配布物に対応するコミットが存在しないため公開できません。"
            "変更をコミットして main へマージしてから再ビルドしてください。"
        )
    commit = record.get("commit")
    if not commit:
        raise SystemExit(
            "エラー: ビルド元コミットが記録されていません"
            "（ビルド時にgitを参照できなかった可能性があります）。"
            "gitリポジトリ上で build_package.py を実行し直してください。"
        )
    return commit


def read_ref_commit(repo_root: Path, ref: str) -> str | None:
    """`ref`が指すコミットSHAを返す（存在しなければNone）。ローカル・リモート双方に使う。"""
    result = subprocess.run(
        ["git", "rev-list", "-n", "1", ref],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def read_remote_tag_commit(repo_root: Path, tag: str) -> str | None:
    """リモートの`tag`が指すコミットSHAを返す（存在しなければNone）。

    `git ls-remote`はローカルの状態に依存せずリモートの実体を見るため、ローカルに
    古いタグが残っていても正しく判定できる。注釈付きタグは`<tag>^{}`の行が実体の
    コミットを指すので、そちらを優先して読む。
    """
    result = subprocess.run(
        ["git", "ls-remote", "--tags", "origin", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    peeled: str | None = None
    plain: str | None = None
    for line in result.stdout.splitlines():
        sha, _, ref = line.partition("	")
        if ref.endswith("^{}"):
            peeled = sha.strip()
        elif ref.endswith(f"refs/tags/{tag}"):
            plain = sha.strip()
    return peeled or plain


def ensure_release_tag(repo_root: Path, tag: str, commit: str) -> None:
    """`tag`がビルド元`commit`を指す状態にしてリモートへ反映する。

    ghの自動タグ生成に任せず、ここで確定させる理由は`build_release_command`のdocstring
    を参照。既にリモートへ別のコミットで公開済みのタグがある場合は、配布済みの内容を
    黙って書き換えることになるため中止する（付け替えるかどうかは人が判断する）。
    """
    remote_commit = read_remote_tag_commit(repo_root, tag)
    if remote_commit == commit:
        return
    if remote_commit is not None:
        raise SystemExit(
            f"エラー: タグ {tag} は既にリモートに存在し、{remote_commit[:8]} を指しています"
            f"（ビルド元は {commit[:8]}）。配布済みのタグを黙って動かさないため中止します。"
            "意図した付け替えであれば、タグを削除するか別バージョンで公開してください。"
        )

    local_commit = read_ref_commit(repo_root, f"refs/tags/{tag}")
    if local_commit is not None and local_commit != commit:
        # ローカルの古いタグを残したままにすると、gh が push して --verify-tag を
        # すり抜けるため、ここで正しい位置へ付け替える。
        print(
            f"  → ローカルタグ {tag} が {local_commit[:8]} を指しているため "
            f"{commit[:8]} へ付け替えます"
        )
    subprocess.run(["git", "tag", "-f", tag, commit], cwd=repo_root, check=True)
    subprocess.run(["git", "push", "origin", "-f", f"refs/tags/{tag}"], cwd=repo_root, check=True)
    print(f"  → タグ {tag} を {commit[:8]} へ作成しました")


def is_merged_into_base(repo_root: Path, commit: str) -> bool:
    """ビルド元コミットが`origin/main`の履歴に含まれるかを判定する。

    未マージのまま公開すると、GitHubがタグを作れないか、Release本文から詳細
    リリースノート（`main`を指す）へのリンクが404になる（`release_notes_url`参照）。
    ローカルの`origin/main`参照を見るため、事前に`git fetch`しておくこと。

    ここは祖先関係（`merge-base --is-ancestor`）で判定するのが正しい。タグはこの
    コミットそのものを指すため、`main`の履歴に無いコミットへタグを付けてはならない。
    `release.is_content_merged_into_base`はツリーの一致で判定するが、あちらは
    「作業内容が取り込み済みか（＝mainへ切り替えても成果を失わないか）」という別の問いで
    あり、判定方法を互いに合わせてはならない。
    """
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, BASE_BRANCH_REF],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def publish(
    version: str, zip_path: Path, notes_path: Path, commit_path: Path, *, draft: bool = False
) -> None:
    """`ver{version}`タグでリリースを作成し、zipと本文を添付する。

    タグは`ensure_release_tag`でビルド元コミットへ確定させてから`--verify-tag`付きで
    公開する（ghの自動タグ生成に任せない理由は`build_release_command`参照）。公開の
    前提として、そのコミットが`origin/main`へマージ済みであることを検証する。

    本文は`resolve_release_body`が決める。詳細ノートがあればその要約を、無ければ記入用の
    ひな形を載せる。ひな形のまま一般公開されないよう、ノートが無い場合は`draft=True`での
    呼び出しを前提とする（判断は呼び出し側の`release.py`が行う）。

    タグが既存の場合（`gh release create`が失敗する場合）は、本文の差し替え
    （`gh release edit`）とアセットの差し替え（`gh release upload --clobber`）へ
    切り替える。`gh`のエラーメッセージ文字列で「タグ既存」かどうかを判定する
    （CLI出力形式への依存はもろいため）のではなく、常にcreateを試みてから失敗時に
    フォールバックする方式に統一する。
    """
    if not zip_path.is_file():
        print(f"エラー: {zip_path} が見つかりません。先に build_package.py を実行してください。")
        raise SystemExit(1)

    commit = read_build_commit(commit_path, version)
    if not is_merged_into_base(REPO_ROOT, commit):
        raise SystemExit(
            f"エラー: ビルド元コミット {commit[:8]} が {BASE_BRANCH_REF} へマージされていません。"
            "マージしてから公開してください（未マージのまま公開すると、タグが配布物と"
            "異なるコミットを指すか、詳細リリースノートへのリンクが404になります）。"
        )

    body = resolve_release_body(notes_path, version)
    with tempfile.TemporaryDirectory() as work_dir:
        body_path = Path(work_dir) / "release_body.md"
        body_path.write_text(body, encoding="utf-8")

        ensure_release_tag(REPO_ROOT, release_tag(version), commit)
        result = subprocess.run(
            build_release_command(version, zip_path, body_path, draft=draft), cwd=REPO_ROOT
        )
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
    publish(
        version,
        zip_path,
        release_notes_path(REPO_ROOT, version),
        build_commit_path(DIST_DIR, version),
    )


if __name__ == "__main__":
    sys.exit(main())
