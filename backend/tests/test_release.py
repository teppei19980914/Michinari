"""マージ〜ビルド〜公開を一続きで実行するスクリプトのテスト（scripts/release.py参照）。

実際に実行すると`main`へマージしGitHubへ公開してしまうため、`subprocess.run`および
各工程の関数を差し替え、事前検証と工程の順序だけを検証する。
"""

import subprocess
from pathlib import Path

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
        release.verify_preconditions(version)


def test_verify_preconditions_rejects_dirty_worktree(monkeypatch, tmp_path: Path) -> None:
    """未コミットの変更があると、配布物と公開されるソースが食い違うため中止すること。"""
    _write_notes(tmp_path, "1.2.3")
    _prepare(monkeypatch, tmp_path, dirty=True)

    with pytest.raises(SystemExit):
        release.verify_preconditions("1.2.3")


def test_verify_preconditions_requires_release_notes(monkeypatch, tmp_path: Path) -> None:
    """Release本文の元になるノートが無ければ、マージ前に止めること。"""
    _prepare(monkeypatch, tmp_path)

    with pytest.raises(SystemExit):
        release.verify_preconditions("1.2.3")


def test_verify_preconditions_requires_summary_markers(monkeypatch, tmp_path: Path) -> None:
    """要約ブロックが無いノートは、公開直前ではなく事前に弾くこと。"""
    notes_dir = tmp_path / "docs" / "release-notes"
    notes_dir.mkdir(parents=True)
    (notes_dir / "v1.2.3.md").write_text("# v1.2.3\n要約ブロックなし\n", encoding="utf-8")
    _prepare(monkeypatch, tmp_path)

    with pytest.raises(SystemExit):
        release.verify_preconditions("1.2.3")


def test_verify_preconditions_rejects_already_published_version(
    monkeypatch, tmp_path: Path
) -> None:
    """公開済みバージョンを上書きしないこと（配布済みの内容を黙って変えない）。"""
    _write_notes(tmp_path, "1.2.3")
    _prepare(monkeypatch, tmp_path, remote_tag=f"{_STALE_COMMIT}{_TAB}refs/tags/ver1.2.3\n")

    with pytest.raises(SystemExit):
        release.verify_preconditions("1.2.3")


def test_verify_preconditions_accepts_a_ready_state(monkeypatch, tmp_path: Path) -> None:
    _write_notes(tmp_path, "1.2.3")
    _prepare(monkeypatch, tmp_path)

    release.verify_preconditions("1.2.3")


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


# --- 工程の順序 ---


def test_main_runs_merge_build_publish_verify_in_order(monkeypatch, tmp_path: Path) -> None:
    """検証→マージ→ビルド→公開→公開後検証の順で、いずれも省略されないこと。"""
    order: list[str] = []
    monkeypatch.setattr(release, "verify_preconditions", lambda v: order.append("verify"))
    monkeypatch.setattr(release, "merge_to_base", lambda v: (order.append("merge"), _COMMIT)[1])
    monkeypatch.setattr(release, "build", lambda v: (order.append("build"), tmp_path / "a.zip")[1])
    monkeypatch.setattr(release, "publish", lambda v, z: order.append("publish"))
    monkeypatch.setattr(release, "verify_published", lambda v, c: order.append("verified"))
    monkeypatch.setattr("sys.argv", ["release.py", "1.2.3"])

    assert release.main() == 0
    assert order == ["verify", "merge", "build", "publish", "verified"]


def test_main_can_skip_merge_but_still_verifies(monkeypatch, tmp_path: Path) -> None:
    """既にマージ済みの場合でも、公開後のタグ検証は必ず行うこと。"""
    order: list[str] = []
    monkeypatch.setattr(release, "verify_preconditions", lambda v: order.append("verify"))
    monkeypatch.setattr(release, "merge_to_base", lambda v: pytest.fail("マージしてはならない"))
    monkeypatch.setattr(
        release, "run_git", lambda *a, **k: subprocess.CompletedProcess(a, 0, _COMMIT, "")
    )
    monkeypatch.setattr(release, "build", lambda v: (order.append("build"), tmp_path / "a.zip")[1])
    monkeypatch.setattr(release, "publish", lambda v, z: order.append("publish"))
    monkeypatch.setattr(release, "verify_published", lambda v, c: order.append("verified"))
    monkeypatch.setattr("sys.argv", ["release.py", "1.2.3", "--skip-merge"])

    assert release.main() == 0
    assert order == ["verify", "build", "publish", "verified"]
