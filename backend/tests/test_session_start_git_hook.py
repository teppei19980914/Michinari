"""SessionStart フック `.claude/hooks/session-start-git.sh` の振る舞いテスト。

一時ディレクトリに作業リポジトリ・bare の origin・偽の gh を作り、実フックを bash で実行して
ブランチ判定・push の有無・gh 呼び出し・通信の時間上限を検証する。
origin は `url.<bare>.insteadOf` で GitHub の URL を bare へ向けるため外部通信は発生しない。
偽の gh は `GH_BIN` 経由で差し替え、PR 状態は環境変数で切り替える。
"""

import datetime
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / ".claude" / "hooks" / "session-start-git.sh"


def _find_bash() -> str | None:
    """フックを実行する bash を返す。Windows では PATH 先頭の System32\\bash.exe（WSL の起動器）が
    見つかることがあり、ディストリビューション未導入だと起動できないため、Git for Windows の
    bash を git の場所から優先して探す（フックは Git Bash 前提で書かれている）。"""
    git = shutil.which("git")
    if git:
        candidate = Path(git).resolve().parents[1] / "bin" / "bash.exe"
        if candidate.exists():
            return str(candidate)
    return shutil.which("bash")


BASH = _find_bash()
PREV_BRANCH = "dev/2000-01-01"
TODAY = datetime.date.today().isoformat()

pytestmark = pytest.mark.skipif(BASH is None or not HOOK.exists(), reason="bash と実フックが必要")

FAKE_GH = """#!/usr/bin/env bash
echo "$*" >> "$FAKE_GH_LOG"
case "$1 $2" in
  "auth status") exit 0 ;;
  "pr view")
    if [ -n "${FAKE_GH_SLEEP:-}" ]; then exec sleep "$FAKE_GH_SLEEP"; fi
    printf '%s' "${FAKE_PR_STATE:-}" ;;
  "pr create") echo "https://example.invalid/pull/1" ;;
  *) exit 1 ;;
esac
"""


@dataclass
class Workspace:
    work: Path
    bare: Path
    gh: Path
    gh_log: Path
    push_log: Path


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, encoding="utf-8"
    )
    return result.stdout.strip()


def current_branch(repo: Path) -> str:
    return git(repo, "branch", "--show-current")


def branches(repo: Path) -> list[str]:
    return git(repo, "branch", "--format=%(refname:short)").split()


def commit_file(repo: Path, name: str) -> None:
    (repo / name).write_text("x\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", f"add {name}")


def make_branch(repo: Path, name: str, *, push: bool = False) -> None:
    git(repo, "branch", name)
    if push:
        git(repo, "push", "-q", "-u", "origin", name)


@pytest.fixture
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Workspace:
    monkeypatch.setenv("GIT_AUTHOR_NAME", "test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.invalid")

    # フックは origin の URL に github.com を含むことを要求するため、パスに含めて判定を通す
    bare = tmp_path / "github.com" / "origin.git"
    bare.parent.mkdir()
    work = tmp_path / "work"
    gh = tmp_path / "fakegh"
    gh.write_text(FAKE_GH, encoding="utf-8", newline="\n")
    gh.chmod(0o755)
    push_log = tmp_path / "push.log"

    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    # 受信時に記録する（push が実際に起きたかを確認するため）
    (bare / "hooks" / "pre-receive").write_text(
        f'#!/bin/sh\necho pushed >> "{push_log.as_posix()}"\n', encoding="utf-8", newline="\n"
    )

    work.mkdir()
    git(work, "init", "-q", "-b", "main")
    (work / ".claude").mkdir()
    (work / ".claude" / ".git-automation-config").write_text(
        "enabled=true\nbranch_prefix=dev/\nbase_branch=main\n", encoding="utf-8"
    )
    commit_file(work, "README.md")
    git(work, "remote", "add", "origin", f"file:///{bare.as_posix()}")
    git(work, "push", "-q", "-u", "origin", "main")

    return Workspace(work=work, bare=bare, gh=gh, gh_log=tmp_path / "gh.log", push_log=push_log)


def run_hook(ws: Workspace, **env: str) -> subprocess.CompletedProcess[str]:
    base_env = {
        **os.environ,
        "GH_BIN": str(ws.gh),
        "FAKE_GH_LOG": str(ws.gh_log),
        "FAKE_PR_STATE": "",
        "NET_TIMEOUT": "10",
    }
    return subprocess.run(
        [BASH, str(HOOK)],
        cwd=ws.work,
        env={**base_env, **env},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )


def test_disabled_config_does_nothing(ws: Workspace) -> None:
    (ws.work / ".claude" / ".git-automation-config").write_text("enabled=false\n", encoding="utf-8")

    result = run_hook(ws)

    assert result.returncode == 0
    assert "Git Automation" not in result.stdout
    assert current_branch(ws.work) == "main"
    assert not ws.gh_log.exists()


def test_creates_today_branch_when_no_previous_branch(ws: Workspace) -> None:
    result = run_hook(ws)

    assert result.returncode == 0
    assert current_branch(ws.work) == f"dev/{TODAY}"
    assert f"当日ブランチ dev/{TODAY} を作成" in result.stdout


def test_stays_on_unmerged_previous_branch(ws: Workspace) -> None:
    make_branch(ws.work, PREV_BRANCH)

    result = run_hook(ws, FAKE_PR_STATE="OPEN")

    assert current_branch(ws.work) == PREV_BRANCH
    assert f"dev/{TODAY}" not in branches(ws.work)
    assert "作業中と判断" in result.stdout
    assert "pr view" in ws.gh_log.read_text(encoding="utf-8")


def test_deletes_merged_previous_branch_when_head_reached_base(ws: Workspace) -> None:
    make_branch(ws.work, PREV_BRANCH, push=True)

    run_hook(ws, FAKE_PR_STATE="MERGED")

    assert PREV_BRANCH not in branches(ws.work)
    assert current_branch(ws.work) == f"dev/{TODAY}"


def test_keeps_merged_branch_that_has_commits_outside_base(ws: Workspace) -> None:
    make_branch(ws.work, PREV_BRANCH, push=True)
    git(ws.work, "checkout", "-q", PREV_BRANCH)
    commit_file(ws.work, "extra.txt")

    result = run_hook(ws, FAKE_PR_STATE="MERGED")

    assert PREV_BRANCH in branches(ws.work)
    assert current_branch(ws.work) == PREV_BRANCH
    assert "未到達" in result.stdout


def test_does_not_push_when_nothing_is_ahead(ws: Workspace) -> None:
    make_branch(ws.work, PREV_BRANCH, push=True)
    # セットアップ時の push で記録された分を消し、フック実行中の push だけを見る
    ws.push_log.unlink(missing_ok=True)

    run_hook(ws, FAKE_PR_STATE="OPEN")

    assert not ws.push_log.exists()


def test_pushes_when_previous_branch_is_ahead_of_upstream(ws: Workspace) -> None:
    make_branch(ws.work, PREV_BRANCH, push=True)
    git(ws.work, "checkout", "-q", PREV_BRANCH)
    commit_file(ws.work, "extra.txt")

    run_hook(ws, FAKE_PR_STATE="OPEN")

    assert ws.push_log.exists()


def test_network_calls_are_time_limited(ws: Workspace) -> None:
    make_branch(ws.work, PREV_BRANCH, push=True)

    start = time.monotonic()
    # 上限は gh の起動時間（約1秒）より長くし、sleep 中の pr view だけを打ち切る
    result = run_hook(ws, FAKE_GH_SLEEP="120", NET_TIMEOUT="5")
    elapsed = time.monotonic() - start

    # 上限が効かなければ gh pr view の sleep 120 秒を待つ。上限で打ち切られ PR 作成経路へ進む
    assert elapsed < 100
    assert "PR 作成" in result.stdout
