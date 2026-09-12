"""マージ〜ビルド〜公開を一続きで実行するスクリプトのテスト（scripts/release.py参照）。

実際に実行すると`main`へマージしGitHubへ公開してしまうため、`subprocess.run`および
各工程の関数を差し替え、事前検証と工程の順序だけを検証する。
"""

import subprocess
from pathlib import Path

import build_package
import publish_release
import pytest
import release

_COMMIT = "82c324748411a3763e964891abf869329243be6e"
_STALE_COMMIT = "da9e566d4eca76d6ae139d59404b73039634db01"
_TAB = "\t"


def _write_notes(repo_root: Path, version: str) -> Path:
    notes_dir = repo_root / "docs" / "release-notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    path = notes_dir / f"v{version}.md"
    path.write_text(
        f"# v{version}\n{publish_release.SUMMARY_START}\n要約\n{publish_release.SUMMARY_END}\n",
        encoding="utf-8",
    )
    return path


def _prepare(monkeypatch, tmp_path: Path, *, dirty: bool = False, remote_tag: str = "") -> None:
    """`verify_preconditions`が参照する外部状態をまとめて差し替える。"""
    monkeypatch.setattr(release, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(release, "has_uncommitted_changes", lambda: dirty)

    def fake_run(args, cwd=None, **kwargs):
        if args[:2] == ["git", "ls-remote"]:
            return subprocess.CompletedProcess(args, 0, stdout=remote_tag, stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)


# --- 事前検証 ---


@pytest.mark.parametrize("version", ["1.2", "v1.2.3", "1.2.3-rc1", "", "1.2.3.4"])
def test_verify_preconditions_rejects_non_semver(monkeypatch, tmp_path: Path, version) -> None:
    """タグ名の揺れを防ぐため、N.N.N以外は受け付けないこと。"""
    _prepare(monkeypatch, tmp_path)

    with pytest.raises(SystemExit):
        release.verify_preconditions(version, require_notes=True)


def test_verify_workspace_rejects_dirty_worktree(monkeypatch, tmp_path: Path) -> None:
    """未コミットの変更があると、配布物と公開されるソースが食い違うため中止すること。

    バージョン入力より前に確認する（入力させた後で止めるのは手間の無駄なため）。
    """
    _prepare(monkeypatch, tmp_path, dirty=True)

    with pytest.raises(SystemExit):
        release.verify_workspace()


def test_verify_workspace_accepts_a_clean_worktree(monkeypatch, tmp_path: Path) -> None:
    _prepare(monkeypatch, tmp_path)

    release.verify_workspace()


def test_verify_preconditions_requires_release_notes(monkeypatch, tmp_path: Path) -> None:
    """Release本文の元になるノートが無ければ、マージ前に止めること。"""
    _prepare(monkeypatch, tmp_path)

    with pytest.raises(SystemExit):
        release.verify_preconditions("1.2.3", require_notes=True)


def test_verify_preconditions_requires_summary_markers(monkeypatch, tmp_path: Path) -> None:
    """要約ブロックが無いノートは、公開直前ではなく事前に弾くこと。"""
    notes_dir = tmp_path / "docs" / "release-notes"
    notes_dir.mkdir(parents=True)
    (notes_dir / "v1.2.3.md").write_text("# v1.2.3\n要約ブロックなし\n", encoding="utf-8")
    _prepare(monkeypatch, tmp_path)

    with pytest.raises(SystemExit):
        release.verify_preconditions("1.2.3", require_notes=True)


def test_verify_preconditions_rejects_already_published_version(
    monkeypatch, tmp_path: Path
) -> None:
    """公開済みバージョンを上書きしないこと（配布済みの内容を黙って変えない）。"""
    _write_notes(tmp_path, "1.2.3")
    _prepare(monkeypatch, tmp_path, remote_tag=f"{_STALE_COMMIT}{_TAB}refs/tags/ver1.2.3\n")

    with pytest.raises(SystemExit):
        release.verify_preconditions("1.2.3", require_notes=True)


def test_verify_preconditions_accepts_a_ready_state(monkeypatch, tmp_path: Path) -> None:
    _write_notes(tmp_path, "1.2.3")
    _prepare(monkeypatch, tmp_path)

    release.verify_preconditions("1.2.3", require_notes=True)


# --- 公開後の検証 ---


def test_verify_published_accepts_a_matching_tag(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(release, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(publish_release, "read_remote_tag_commit", lambda *_: _COMMIT)

    release.verify_published("1.2.3", _COMMIT)


def test_verify_published_detects_a_tag_on_the_wrong_commit(monkeypatch, tmp_path: Path) -> None:
    """2026-09-12のv1.2.1の再発検知。

    Releaseの`target_commitish`には指定値が入るため、Releaseの情報だけを見ても
    食い違いに気付けない。リモートのタグ実体と突き合わせる。
    """
    monkeypatch.setattr(release, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(publish_release, "read_remote_tag_commit", lambda *_: _STALE_COMMIT)

    with pytest.raises(SystemExit):
        release.verify_published("1.2.3", _COMMIT)


# --- マージ済みかの検証 ---


def _stub_rev_parse(monkeypatch, head: str, base: str) -> None:
    """`git rev-parse HEAD` と `origin/main` の戻り値だけを差し替える。"""

    def fake_run_git(*args, check=True):
        if args[:2] == ("rev-parse", "HEAD"):
            return subprocess.CompletedProcess(args, 0, head, "")
        if args[0] == "rev-parse":
            return subprocess.CompletedProcess(args, 0, base, "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(release, "run_git", fake_run_git)


def test_verify_base_is_checked_out_accepts_a_synced_worktree(monkeypatch) -> None:
    _stub_rev_parse(monkeypatch, _COMMIT, _COMMIT)

    assert release.verify_base_is_checked_out() == _COMMIT


def test_verify_base_is_checked_out_rejects_a_worktree_behind_main(monkeypatch) -> None:
    """作業ツリーとorigin/mainがずれたまま公開しないこと。

    ビルドは作業ツリーの内容から作られる一方、ビルド元コミットはorigin/mainとして
    扱われるため、ずれていると配布物と異なるコミットにタグが付く（v1.2.1と同種の事故）。
    """
    _stub_rev_parse(monkeypatch, _STALE_COMMIT, _COMMIT)

    with pytest.raises(SystemExit):
        release.verify_base_is_checked_out()


# --- バージョン入力 ---


def test_prompt_version_accepts_a_semver_value() -> None:
    assert release.prompt_version("1.2.2", prompt=lambda _m: "1.2.3") == "1.2.3"


def test_prompt_version_strips_surrounding_spaces() -> None:
    assert release.prompt_version("1.2.2", prompt=lambda _m: "  1.2.3  ") == "1.2.3"


def test_prompt_version_reasks_until_the_format_is_valid() -> None:
    """タグ名の揺れを防ぐため、N.N.N以外は受け付けず再入力を求めること。"""
    answers = iter(["", "v1.2.3", "1.2", "1.2.3"])

    assert release.prompt_version("1.2.2", prompt=lambda _m: next(answers)) == "1.2.3"


def test_prompt_version_shows_the_current_version_in_the_message() -> None:
    """既定値として自動採用はしないが、参考として現在値を表示すること。"""
    messages: list[str] = []

    release.prompt_version("1.2.2", prompt=lambda m: (messages.append(m), "1.2.3")[1])

    assert "1.2.2" in messages[0]


# --- 工程の順序 ---


def _stub_main_steps(monkeypatch, tmp_path: Path, order: list[str]) -> None:
    """`main`の各工程を記録用のスタブへ差し替える（順序と省略の検証用）。"""
    monkeypatch.setattr(release, "verify_workspace", lambda: order.append("workspace"))
    monkeypatch.setattr(release, "verify_preconditions", lambda v, **k: order.append("verify"))
    monkeypatch.setattr(release, "merge_to_base", lambda v: (order.append("merge"), _COMMIT)[1])
    monkeypatch.setattr(
        release, "build", lambda v, **k: (order.append("build"), tmp_path / "a.zip")[1]
    )
    monkeypatch.setattr(release, "publish", lambda v, z, **k: order.append("publish"))
    monkeypatch.setattr(release, "verify_published", lambda v, c: order.append("verified"))


def test_main_runs_merge_build_publish_verify_in_order(monkeypatch, tmp_path: Path) -> None:
    """検証→マージ→ビルド→公開→公開後検証の順で、いずれも省略されないこと。"""
    order: list[str] = []
    _stub_main_steps(monkeypatch, tmp_path, order)
    monkeypatch.setattr("sys.argv", ["release.py", "1.2.3"])

    assert release.main() == 0
    assert order == ["workspace", "verify", "merge", "build", "publish", "verified"]


def test_main_can_skip_merge_but_still_verifies(monkeypatch, tmp_path: Path) -> None:
    """既にマージ済みの場合でも、公開後のタグ検証は必ず行うこと。"""
    order: list[str] = []
    _stub_main_steps(monkeypatch, tmp_path, order)
    monkeypatch.setattr(release, "merge_to_base", lambda v: pytest.fail("マージしてはならない"))
    monkeypatch.setattr(
        release, "verify_base_is_checked_out", lambda: (order.append("base"), _COMMIT)[1]
    )
    monkeypatch.setattr("sys.argv", ["release.py", "1.2.3", "--skip-merge"])

    assert release.main() == 0
    assert order == ["workspace", "verify", "base", "build", "publish", "verified"]


def test_main_prompts_for_the_version_only_after_tests_pass(monkeypatch, tmp_path: Path) -> None:
    """バージョンを省略した場合、テストを通してから入力を求めること（要件）。

    通らないビルドのためにバージョンを考えさせない。入力後はテストを再実行しない。
    """
    order: list[str] = []
    _stub_main_steps(monkeypatch, tmp_path, order)
    monkeypatch.setattr(release, "verify_base_is_checked_out", lambda: _COMMIT)
    monkeypatch.setattr(build_package, "run_tests", lambda: order.append("tests"))
    monkeypatch.setattr(build_package, "read_current_version", lambda _p: "1.2.2")
    monkeypatch.setattr(release, "prompt_version", lambda cur: (order.append("prompt"), "1.2.3")[1])
    monkeypatch.setattr("sys.argv", ["release.py", "--skip-merge", "--draft"])

    assert release.main() == 0
    assert order.index("tests") < order.index("prompt")


def test_main_does_not_run_the_tests_twice(monkeypatch, tmp_path: Path) -> None:
    """バージョン入力前にテスト済みなら、ビルド側で再実行しないこと。"""
    captured: dict = {}
    monkeypatch.setattr(release, "verify_workspace", lambda: None)
    monkeypatch.setattr(release, "verify_preconditions", lambda v, **k: None)
    monkeypatch.setattr(release, "verify_base_is_checked_out", lambda: _COMMIT)
    monkeypatch.setattr(build_package, "run_tests", lambda: None)
    monkeypatch.setattr(build_package, "read_current_version", lambda _p: "1.2.2")
    monkeypatch.setattr(release, "prompt_version", lambda cur: "1.2.3")
    monkeypatch.setattr(
        release,
        "build",
        lambda v, **k: (captured.update(k), tmp_path / "a.zip")[1],
    )
    monkeypatch.setattr(release, "publish", lambda v, z, **k: None)
    monkeypatch.setattr(release, "verify_published", lambda v, c: None)
    monkeypatch.setattr("sys.argv", ["release.py", "--skip-merge", "--draft"])

    assert release.main() == 0
    assert captured["skip_tests"] is True


def test_main_passes_the_draft_flag_through_to_publish(monkeypatch, tmp_path: Path) -> None:
    """`--draft`が公開処理まで伝わること（ひな形のまま一般公開しないため）。"""
    captured: dict = {}
    order: list[str] = []
    _stub_main_steps(monkeypatch, tmp_path, order)
    monkeypatch.setattr(release, "verify_base_is_checked_out", lambda: _COMMIT)
    monkeypatch.setattr(release, "publish", lambda v, z, **k: captured.update(k))
    monkeypatch.setattr("sys.argv", ["release.py", "1.2.3", "--skip-merge", "--draft"])

    assert release.main() == 0
    assert captured["draft"] is True


def test_main_does_not_require_notes_when_drafting(monkeypatch, tmp_path: Path) -> None:
    """下書き公開では詳細ノートの存在を求めないこと（ノートは後から書く運用）。"""
    captured: dict = {}
    order: list[str] = []
    _stub_main_steps(monkeypatch, tmp_path, order)
    monkeypatch.setattr(release, "verify_base_is_checked_out", lambda: _COMMIT)
    monkeypatch.setattr(release, "verify_preconditions", lambda v, **k: captured.update(k))
    monkeypatch.setattr("sys.argv", ["release.py", "1.2.3", "--skip-merge", "--draft"])

    assert release.main() == 0
    assert captured["require_notes"] is False
