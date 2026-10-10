"""SessionStart フック `.claude/hooks/session-start-git.sh` の振る舞いテスト。

一時ディレクトリに作業リポジトリ・bare の origin・偽の gh を作り、実フックを bash で実行して
ブランチ判定・push の有無・gh 呼び出し・通信の時間上限を検証する。
origin は `url.<bare>.insteadOf` で GitHub の URL を bare へ向けるため外部通信は発生しない。
偽の gh は `GH_BIN` 経由で差し替え、PR 状態は環境変数で切り替える。

フックは2026-10-07に全面改訂した（暴走の再発防止、`.claude/hooks/session-start-git.sh` の
冒頭コメント参照）。ブランチを決めて切り替えるところまで（A）だけを起動時に同期で行い、
push・PRの確認/作成・削除（B）は起動の完了を待たせず裏で行う。このテストでは、Bの結果を
検証できるよう既定で `GIT_AUTOMATION_SYNC=1`（Bをその場で同期実行する）を渡す。Bが実際に
裏へ切り離されることを確かめるテストだけ、明示的にこれを外す。
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
PREV_BRANCH_2 = "dev/2000-01-02"
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


def git_dir(repo: Path) -> Path:
    return Path(git(repo, "rev-parse", "--git-dir"))


def lock_path(repo: Path) -> Path:
    d = git_dir(repo)
    return d if d.is_absolute() else repo / d


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
        # 既定ではBをその場で同期実行し、結果を検証できるようにする（下記docstring参照）。
        "GIT_AUTOMATION_SYNC": "1",
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


def wait_for(predicate, *, timeout_seconds: float = 20.0, interval_seconds: float = 0.5) -> bool:
    """条件が満たされるまで待つ（裏で動く処理の完了をポーリングで確認するため）。"""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval_seconds)
    return predicate()


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


def test_stays_on_the_branch_already_checked_out_among_several_unmerged(ws: Workspace) -> None:
    """前日ブランチが複数残っていても、起動時のブランチがその1つならチェックアウトしない
    （暴走の再発防止：切り替えは起動につき最大1回。2026-10-07の事象の回帰テスト）。
    他方のブランチには一切触れていないこと（先端が変わっていないこと）もあわせて確認する。
    """
    make_branch(ws.work, PREV_BRANCH)
    make_branch(ws.work, PREV_BRANCH_2)
    git(ws.work, "checkout", "-q", PREV_BRANCH_2)
    other_branch_tip_before = git(ws.work, "rev-parse", PREV_BRANCH)

    result = run_hook(ws, FAKE_PR_STATE="OPEN")

    assert current_branch(ws.work) == PREV_BRANCH_2
    assert git(ws.work, "rev-parse", PREV_BRANCH) == other_branch_tip_before
    assert "作業中と判断し dev/2000-01-02" in result.stdout


def test_commits_wip_only_on_the_branch_it_belongs_to(ws: Workspace) -> None:
    """未コミット変更は、起動時のブランチにだけコミットする。チェックアウトしていない
    他の前日ブランチには（作業ツリーを持たないため）コミットが起きないことを確認する。
    """
    make_branch(ws.work, PREV_BRANCH)
    make_branch(ws.work, PREV_BRANCH_2)
    git(ws.work, "checkout", "-q", PREV_BRANCH_2)
    (ws.work / "untracked.txt").write_text("x\n", encoding="utf-8")
    other_branch_tip_before = git(ws.work, "rev-parse", PREV_BRANCH)

    run_hook(ws, FAKE_PR_STATE="OPEN")

    assert "chore: auto-commit on session start" in git(ws.work, "log", "-1", "--format=%s")
    assert current_branch(ws.work) == PREV_BRANCH_2
    assert git(ws.work, "rev-parse", PREV_BRANCH) == other_branch_tip_before


def test_merge_and_today_branch_creation_take_one_more_session_each(ws: Workspace) -> None:
    """マージ済みと確認できても、今チェックアウト中のブランチはその場では削除しない
    （`test_does_not_delete_the_branch_currently_checked_out`）。削除・当日ブランチの作成は、
    次回の起動（このブランチから離れた回）まで1回遅れる（承認済みのトレードオフ。
    `.claude/hooks/session-start-git.sh` 冒頭コメント）。デッドロック（唯一残った前日ブランチが
    『マージ済みだが今チェックアウト中』を理由に、次回もまた同じブランチへ留まり続けて
    永久に削除できなくなること）が起きないことを、1回目・2回目の両方で確認する。
    """
    make_branch(ws.work, PREV_BRANCH, push=True)

    first = run_hook(ws, FAKE_PR_STATE="MERGED")
    assert current_branch(ws.work) == PREV_BRANCH
    assert PREV_BRANCH in branches(ws.work)  # 今チェックアウト中のため、1回目では削除しない
    assert "削除を見送ります" in first.stdout

    # 2回目：マージ済みの印が付いているため、このブランチへは留まらず当日ブランチを作る。
    # チェックアウトから外れたことで、片付けが同じ回のうちに削除まで終える（同期実行のため）。
    # FAKE_PR_STATE は偽のghが状態を覚えないためのテスト上の都合で、1回目と同じ値を渡す
    # （実際のGitHubでは、マージ済みのPRが未マージに戻ることはない）。
    second = run_hook(ws, FAKE_PR_STATE="MERGED")
    assert current_branch(ws.work) == f"dev/{TODAY}"
    assert f"当日ブランチ dev/{TODAY} を作成" in second.stdout
    assert PREV_BRANCH not in branches(ws.work)
    assert "ブランチ削除" in second.stdout


def test_keeps_merged_branch_that_has_commits_outside_base(ws: Workspace) -> None:
    make_branch(ws.work, PREV_BRANCH, push=True)
    git(ws.work, "checkout", "-q", PREV_BRANCH)
    commit_file(ws.work, "extra.txt")

    result = run_hook(ws, FAKE_PR_STATE="MERGED")

    assert PREV_BRANCH in branches(ws.work)
    assert current_branch(ws.work) == PREV_BRANCH
    assert "基準ブランチに無い変更が残っています" in result.stdout


def test_does_not_delete_the_branch_currently_checked_out(ws: Workspace) -> None:
    """マージ済みと確認できても、今チェックアウトしているブランチは削除しない
    （`git branch -D` が失敗するうえ、作業中の可能性があるため）。"""
    make_branch(ws.work, PREV_BRANCH, push=True)
    git(ws.work, "checkout", "-q", PREV_BRANCH)

    result = run_hook(ws, FAKE_PR_STATE="MERGED")

    assert PREV_BRANCH in branches(ws.work)
    assert current_branch(ws.work) == PREV_BRANCH
    assert "削除を見送ります" in result.stdout


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


def test_cleanup_runs_in_the_background_without_blocking_startup(ws: Workspace) -> None:
    """既定（GIT_AUTOMATION_SYNC を渡さない）では、片付け（B）は起動の完了を待たせない。
    gh の呼び出しが長時間かかっても、起動自体はすぐ終わり、結果は後から裏ログに記録される。
    """
    make_branch(ws.work, PREV_BRANCH, push=True)

    start = time.monotonic()
    result = run_hook(ws, FAKE_GH_SLEEP="40", NET_TIMEOUT="30", GIT_AUTOMATION_SYNC="")
    elapsed = time.monotonic() - start

    # 起動自体は、gh の sleep(40秒)やNET_TIMEOUT(30秒)を待たずに終わる。
    # このマシンでの外部コマンド起動オーバーヘッドは一定ではなく、他のテストと合わせて
    # 実行すると（プロセス数の蓄積等で）単体実行時より大きく振れる（実測で最大11秒程度）。
    # 上限はその振れに十分な余裕を持たせつつ、sleepより大きく小さく保つことで
    # 「待たずに終わる」ことの検出力を維持する（FAKE_GH_SLEEPを2/4/8/16秒と変えても
    # elapsedが追従しないことから、実際のブロッキングではなく起動オーバーヘッドだと確認済み）。
    assert elapsed < 20
    assert current_branch(ws.work) == PREV_BRANCH
    # この時点ではまだ裏の処理中のため、PR作成の結果は起動の出力には出ていない
    assert "PR 作成" not in result.stdout

    # 裏の sleep(40秒)が終わるまで待てるよう、wait_for の既定20秒より長めに取る
    cleanup_log = lock_path(ws.work) / "git-automation-cleanup.log"
    assert wait_for(
        lambda: cleanup_log.exists() and "PR 作成" in cleanup_log.read_text(encoding="utf-8"),
        timeout_seconds=60.0,
    )
    # 裏の処理が終わればロックは解放される
    assert wait_for(
        lambda: not (lock_path(ws.work) / "git-automation.lock").exists(),
        timeout_seconds=60.0,
    )


def test_concurrent_run_is_skipped_while_lock_is_held(ws: Workspace) -> None:
    lock = lock_path(ws.work) / "git-automation.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(f"999999 {int(time.time())}\n", encoding="utf-8", newline="")

    result = run_hook(ws)

    assert "別の実行が進行中のためスキップ" in result.stdout
    assert current_branch(ws.work) == "main"
    assert not ws.gh_log.exists()


def test_stale_lock_is_reclaimed(ws: Workspace) -> None:
    """古いロック（既定10分以上）は、前回の実行が異常終了した残骸とみなして取り直す。"""
    lock = lock_path(ws.work) / "git-automation.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("999999 0\n", encoding="utf-8", newline="")  # epoch 0 = 確実に期限切れ

    result = run_hook(ws)

    assert "別の実行が進行中のためスキップ" not in result.stdout
    assert current_branch(ws.work) == f"dev/{TODAY}"


def test_proceeds_with_local_branch_management_when_gh_is_unusable(ws: Workspace) -> None:
    """gh が使えなくても、ローカルだけで完結するブランチの作成・切り替えは行う
    （push・PRの管理だけが対象外になる。gh 未導入でも開発を止めない）。
    """
    make_branch(ws.work, PREV_BRANCH)

    result = run_hook(ws, GH_BIN="/no/such/gh-binary")

    assert "初回セットアップが必要な場合があります" in result.stdout
    assert "gh が使えないため" in result.stdout
    assert current_branch(ws.work) == PREV_BRANCH
    assert not ws.gh_log.exists()
