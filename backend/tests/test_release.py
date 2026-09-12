"""マージ〜ビルド〜公開を一続きで実行するスクリプトのテスト（scripts/release.py参照）。

実際に実行すると`main`へマージしGitHubへ公開してしまうため、`subprocess.run`および
各工程の関数を差し替え、事前検証と工程の順序だけを検証する。
"""

import inspect
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


def _stub_git(monkeypatch, head: str, base: str, *, tree_matches: bool, ff_ok: bool = True):
    """`ensure_base_is_checked_out`が使うgit操作を差し替え、呼ばれた引数を記録する。"""
    calls: list[tuple] = []

    def fake_run_git(*args, check=True):
        calls.append(args)
        if args[:2] == ("rev-parse", "HEAD"):
            return subprocess.CompletedProcess(args, 0, head, "")
        if args[0] == "rev-parse":
            return subprocess.CompletedProcess(args, 0, base, "")
        if args[0] == "diff":
            return subprocess.CompletedProcess(args, 0 if tree_matches else 1, "", "")
        if args[0] == "merge":
            return subprocess.CompletedProcess(args, 0 if ff_ok else 1, "", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(release, "run_git", fake_run_git)
    return calls


def test_ensure_base_is_checked_out_does_nothing_when_already_synced(monkeypatch) -> None:
    calls = _stub_git(monkeypatch, _COMMIT, _COMMIT, tree_matches=True)

    assert release.ensure_base_is_checked_out() == _COMMIT
    assert not [c for c in calls if c[0] == "checkout"]


def test_ensure_base_is_checked_out_switches_to_main_when_work_is_merged(monkeypatch) -> None:
    """PRをマージした直後の状態から、mainへの切り替えと最新化まで行うこと。

    以前はここで中止し、`git checkout main && git pull`を人にやらせていた。
    """
    calls = _stub_git(monkeypatch, _STALE_COMMIT, _COMMIT, tree_matches=True)

    assert release.ensure_base_is_checked_out() == _COMMIT
    assert ("checkout", "main") in calls
    assert ("merge", "--ff-only", "origin/main") in calls


def test_ensure_base_is_checked_out_refuses_when_work_is_not_merged(monkeypatch) -> None:
    """マージし忘れた状態でmainへ切り替えないこと。

    無条件に切り替えると、変更を含まないパッケージを配布してしまう（CLAUDE.mdの
    「未マージのままmainから当日ブランチを切ると成果が消える」と同種の取りこぼし）。
    """
    calls = _stub_git(monkeypatch, _STALE_COMMIT, _COMMIT, tree_matches=False)

    with pytest.raises(SystemExit):
        release.ensure_base_is_checked_out()
    assert not [c for c in calls if c[0] == "checkout"]


def test_ensure_base_is_checked_out_reports_a_diverged_local_main(monkeypatch) -> None:
    """ローカルmainが分岐していてfast-forwardできない場合は中止すること。"""
    _stub_git(monkeypatch, _STALE_COMMIT, _COMMIT, tree_matches=True, ff_ok=False)

    with pytest.raises(SystemExit):
        release.ensure_base_is_checked_out()


def test_is_content_merged_into_base_uses_tree_comparison(monkeypatch) -> None:
    """squashマージでもマージ済みと判定できるよう、祖先関係ではなくツリーを比べること。"""
    calls = _stub_git(monkeypatch, _STALE_COMMIT, _COMMIT, tree_matches=True)

    assert release.is_content_merged_into_base() is True
    assert ("diff", "--quiet", "origin/main", "HEAD") in calls
    assert not [c for c in calls if c[0] == "merge-base"]


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
        release, "ensure_base_is_checked_out", lambda: (order.append("base"), _COMMIT)[1]
    )
    monkeypatch.setattr("sys.argv", ["release.py", "1.2.3", "--skip-merge"])

    assert release.main() == 0
    # mainとの一致確認は、時間のかかるテストより前に行う。
    assert order == ["workspace", "base", "verify", "build", "publish", "verified"]


def test_main_checks_the_base_branch_before_running_tests(monkeypatch, tmp_path: Path) -> None:
    """mainと一致しているかの確認を、テストとバージョン入力より前に行うこと。

    テストは数分かかる。その後で「mainと一致していません」と言われるのは手間の無駄で、
    かつバージョンを入力させた後に中止するのも同じ理由で避ける。
    """
    order: list[str] = []
    _stub_main_steps(monkeypatch, tmp_path, order)
    monkeypatch.setattr(
        release, "ensure_base_is_checked_out", lambda: (order.append("base"), _COMMIT)[1]
    )
    monkeypatch.setattr(build_package, "run_tests", lambda: order.append("tests"))
    monkeypatch.setattr(build_package, "read_current_version", lambda _p: "1.2.2")
    monkeypatch.setattr(release, "prompt_version", lambda cur: (order.append("prompt"), "1.2.3")[1])
    monkeypatch.setattr("sys.argv", ["release.py", "--skip-merge", "--draft"])

    assert release.main() == 0
    assert order.index("base") < order.index("tests") < order.index("prompt")


def test_main_does_not_check_the_base_branch_when_merging(monkeypatch, tmp_path: Path) -> None:
    """マージする実行では、事前の一致確認は行わない（これからマージして揃えるため）。"""
    order: list[str] = []
    _stub_main_steps(monkeypatch, tmp_path, order)
    monkeypatch.setattr(
        release, "ensure_base_is_checked_out", lambda: pytest.fail("確認してはならない")
    )
    monkeypatch.setattr("sys.argv", ["release.py", "1.2.3"])

    assert release.main() == 0
    assert "merge" in order


def test_main_prompts_for_the_version_only_after_tests_pass(monkeypatch, tmp_path: Path) -> None:
    """バージョンを省略した場合、テストを通してから入力を求めること（要件）。

    通らないビルドのためにバージョンを考えさせない。入力後はテストを再実行しない。
    """
    order: list[str] = []
    _stub_main_steps(monkeypatch, tmp_path, order)
    monkeypatch.setattr(release, "ensure_base_is_checked_out", lambda: _COMMIT)
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
    monkeypatch.setattr(release, "ensure_base_is_checked_out", lambda: _COMMIT)
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
    monkeypatch.setattr(release, "ensure_base_is_checked_out", lambda: _COMMIT)
    monkeypatch.setattr(release, "publish", lambda v, z, **k: captured.update(k))
    monkeypatch.setattr("sys.argv", ["release.py", "1.2.3", "--skip-merge", "--draft"])

    assert release.main() == 0
    assert captured["draft"] is True


def test_main_does_not_require_notes_when_drafting(monkeypatch, tmp_path: Path) -> None:
    """下書き公開では詳細ノートの存在を求めないこと（ノートは後から書く運用）。"""
    captured: dict = {}
    order: list[str] = []
    _stub_main_steps(monkeypatch, tmp_path, order)
    monkeypatch.setattr(release, "ensure_base_is_checked_out", lambda: _COMMIT)
    monkeypatch.setattr(release, "verify_preconditions", lambda v, **k: captured.update(k))
    monkeypatch.setattr("sys.argv", ["release.py", "1.2.3", "--skip-merge", "--draft"])

    assert release.main() == 0
    assert captured["require_notes"] is False


# --- 公開処理への引数の受け渡し ---


def _capture_publish_release(monkeypatch) -> dict:
    """`publish_release.publish`を、実シグネチャへ束縛してから記録するスタブへ差し替える。

    `lambda *args`で受けると引数の欠落や順序違いを取りこぼすため、本物の
    シグネチャで`bind`してから名前付きで記録する。5fb2a25で`notes_path`が
    抜け落ちたまま公開工程まで到達した事故は、この束縛があれば検知できた。
    """
    captured: dict = {}
    signature = inspect.signature(publish_release.publish)

    def fake_publish(*args, **kwargs) -> None:
        captured.update(signature.bind(*args, **kwargs).arguments)

    monkeypatch.setattr(publish_release, "publish", fake_publish)
    return captured


def test_publish_passes_the_notes_and_commit_paths_to_publish_release(
    monkeypatch, tmp_path: Path
) -> None:
    """詳細ノートとビルド元コミットの記録を、それぞれ正しい引数位置で渡すこと。

    5fb2a25の再発検知。`notes_path`が抜けると、ビルド元コミットの記録がノートとして
    読まれてしまう（Pythonが引数不足で止めるため実害は出ないが、止まるのは公開直前で、
    テスト・ビルドを全て終えた後になる）。
    """
    monkeypatch.setattr(release, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(build_package, "DIST_DIR", tmp_path / "dist")
    captured = _capture_publish_release(monkeypatch)
    zip_path = tmp_path / "dist" / "Michinari-v1.2.3.zip"

    release.publish("1.2.3", zip_path, draft=True)

    assert captured["version"] == "1.2.3"
    assert captured["zip_path"] == zip_path
    assert captured["notes_path"] == publish_release.release_notes_path(tmp_path, "1.2.3")
    assert captured["commit_path"] == publish_release.build_commit_path(tmp_path / "dist", "1.2.3")


@pytest.mark.parametrize("draft", [True, False])
def test_publish_forwards_the_draft_flag_to_publish_release(
    monkeypatch, tmp_path: Path, draft: bool
) -> None:
    """`--draft`が実際の公開処理まで伝わること（ひな形のまま一般公開しないため）。"""
    monkeypatch.setattr(release, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(build_package, "DIST_DIR", tmp_path / "dist")
    captured = _capture_publish_release(monkeypatch)

    release.publish("1.2.3", tmp_path / "dist" / "Michinari-v1.2.3.zip", draft=draft)

    assert captured["draft"] is draft
