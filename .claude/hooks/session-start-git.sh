#!/usr/bin/env bash
# SessionStart hook: 日次ブランチ運用の自動化
#
# 動作:
#   1. git automation が有効か確認 (.claude/.git-automation-config)
#   2. 排他: 同時に1つだけ動かす（.git 配下のロック。古いロックは10分で無効）
#   3. gh CLI の前提を確認（認証は24時間キャッシュ。以降は warn-only）
#   4. 前日以前の dev/YYYY-MM-DD ブランチを処理する（チェックアウトはしない）
#      - 起動時のブランチの未コミット変更だけを、そのブランチへコミットする
#      - push・PR 作成・削除は、ブランチ名を指定して行う（作業ツリーを変えない）
#      - マージ済みの判定: PR が MERGED、かつ内容が基準ブランチに含まれる
#        （HEAD が到達済み、または git cherry で基準にない変更が無い）
#   5. 当日ブランチの決定（CLAUDE.md「運用フロー」の分岐）
#      - 未マージの前日ブランチがあれば、それを「作業中」として上で作業を継続する
#        （起動時のブランチが未マージならそのまま。複数あれば起動時のブランチを優先）
#      - 前日ブランチが全てマージ済み（または無い）場合のみ、最新の base から当日ブランチを作る
#      - 当日ブランチが既にあればそれへ切り替える（同一日の複数セッション対応）
#
# 暴走防止（2026-10-07 の事象の再発防止）:
#   - 切り替えの禁止: 前日ブランチを順にチェックアウトしない。チェックアウトが起きると作業ツリーが
#     入れ替わり、それが次の起動の引き金になる循環が起きた。チェックアウトは最後の1回だけ。
#   - 排他: 同時の起動は片方だけが実行する（もう一方は何もせず終わる）。
#   - 時間上限: 同期処理全体を HOOK_BUDGET_SECONDS（既定30秒）で打ち切る。SessionStart は
#     CLI の初期化上限（60秒）の中で完了しなければならないため。打ち切り後の処理は安全側
#     （削除せず、未マージ扱い）に倒す。
#   - 認証確認のキャッシュ: `gh auth status` は24時間に1回だけ実行する。
#
# 安全の原則（これまでの事故の再発防止）:
#   - 未マージのまま当日ブランチを base から切ると、前日の成果が作業ツリーから消える（2026-09-10・11）。
#   - PR状態（MERGED）だけで削除すると、マージ後に積まれた追加コミットが失われる（2026-09-14・10-02）。
#     そのため削除前に内容が基準ブランチに含まれることを確認する。確認できなければ削除しない。
#   - 未追跡ファイルも含めて自動コミットする（取りこぼし防止、2026-09-17〜18）。

set -u

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$REPO_ROOT" ]; then
  echo "[git-automation] git リポジトリではないためスキップ"
  exit 0
fi
cd "$REPO_ROOT"

CONFIG_FILE=".claude/.git-automation-config"
SETUP_DONE_FILE=".claude/.git-automation-setup-done"

# ========================================
# Step 0: 有効化チェック (オプトイン)
# ========================================
if [ ! -f "$CONFIG_FILE" ]; then
  # 設定ファイルがない = 無効
  exit 0
fi

# shellcheck disable=SC1090
. "$CONFIG_FILE"

if [ "${enabled:-false}" != "true" ]; then
  exit 0
fi

BRANCH_PREFIX="${branch_prefix:-dev/}"
BASE_BRANCH="${base_branch:-main}"

# ========================================
# 排他（同時実行の防止）
# ========================================
# ロックは .git 配下に作る（作業ツリーに現れず、Git の追跡対象にもならない）。
GIT_DIR="$(git rev-parse --git-dir 2>/dev/null)"
LOCK_DIR="$GIT_DIR/git-automation.lock"
LOCK_STALE_MINUTES="${LOCK_STALE_MINUTES:-10}"

acquire_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    return 0
  fi
  # 前回の実行が途中で止まって残ったロックは、一定時間で無効とみなして取り直す
  if [ -n "$(find "$LOCK_DIR" -maxdepth 0 -mmin +"$LOCK_STALE_MINUTES" 2>/dev/null)" ]; then
    rmdir "$LOCK_DIR" 2>/dev/null && mkdir "$LOCK_DIR" 2>/dev/null && return 0
  fi
  return 1
}

if ! acquire_lock; then
  echo "[git-automation] 別の実行が進行中のためスキップ"
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

# ========================================
# 時間上限と通信
# ========================================
# 起動時間の上限対策（2026-10-05）: このフックは SessionStart で同期実行され、CLI の初期化
# 上限（60秒）の中で完了する必要がある。ネットワーク呼び出しは1回ずつ上限付きで行い、
# 全体の予算（HOOK_BUDGET_SECONDS）を超えたら以降の通信を省く。
NET_TIMEOUT="${NET_TIMEOUT:-10}"
HOOK_BUDGET_SECONDS="${HOOK_BUDGET_SECONDS:-30}"
HOOK_STARTED_AT="$(date +%s)"
BUDGET_EXHAUSTED=0
# gh の起動コマンド。テストで偽の gh を差し替えるための口（既定は gh）
GH_CMD="${GH_BIN:-gh}"

budget_left() {
  [ $(( $(date +%s) - HOOK_STARTED_AT )) -lt "$HOOK_BUDGET_SECONDS" ]
}

net() {
  if ! budget_left; then
    if [ "$BUDGET_EXHAUSTED" -eq 0 ]; then
      echo "  [!] 時間上限（${HOOK_BUDGET_SECONDS}秒）に達したため、以降の通信を省略します"
      BUDGET_EXHAUSTED=1
    fi
    return 1
  fi
  if command -v timeout >/dev/null 2>&1; then
    timeout "$NET_TIMEOUT" "$@"
  else
    "$@"
  fi
}

# base ブランチの取得は起動中に1回だけ行う
BASE_FETCHED=0
fetch_base() {
  if [ "$BASE_FETCHED" -eq 0 ]; then
    net git fetch origin "$BASE_BRANCH" >/dev/null 2>&1 || true
    BASE_FETCHED=1
  fi
}

echo ""
echo "=== Git Automation (SessionStart) ==="

# 終了メッセージ（複数の早期 return 経路から呼ぶため関数化する。CLAUDE.md DRYの原則）。
finish() {
  echo "=== Git Automation 完了 ==="
  echo ""
  exit 0
}

# ========================================
# Step 1: 前提CLIチェック (Hybrid モード)
# ========================================
AUTH_CACHE="$GIT_DIR/git-automation-auth-ok"

# 認証は24時間に1回だけ確認する（起動のたびに gh を呼ぶと、それだけで数秒かかるため）
gh_authed() {
  if [ -n "$(find "$AUTH_CACHE" -maxdepth 0 -mmin -1440 2>/dev/null)" ]; then
    return 0
  fi
  if net $GH_CMD auth status >/dev/null 2>&1; then
    touch "$AUTH_CACHE"
    return 0
  fi
  return 1
}

check_prereqs() {
  local missing=0

  if ! command -v git >/dev/null 2>&1; then
    echo "  [x] git が未インストール"
    missing=1
  fi

  if ! command -v "${GH_CMD%% *}" >/dev/null 2>&1; then
    echo "  [x] gh CLI が未インストール (https://cli.github.com/)"
    missing=1
  elif ! gh_authed; then
    echo "  [x] gh CLI が未認証 (実行: gh auth login)"
    missing=1
  fi

  local remote_url
  remote_url="$(git remote get-url origin 2>/dev/null || echo '')"
  if [ -z "$remote_url" ]; then
    echo "  [!] origin リモートが未設定"
    missing=1
  elif ! echo "$remote_url" | grep -q 'github\.com'; then
    echo "  [!] origin が GitHub ではありません ($remote_url) — gh CLI 連携不可"
    missing=1
  fi

  return $missing
}

if ! check_prereqs; then
  if [ ! -f "$SETUP_DONE_FILE" ]; then
    cat <<'EOF'

[git-automation] 初回セットアップが必要です:

  1. gh CLI をインストール:    https://cli.github.com/
  2. 認証:                     gh auth login
  3. リモート設定確認:         git remote -v

セットアップ完了後、以下を実行して有効化:
  touch .claude/.git-automation-setup-done

今回のセッションは手動コミット運用で継続します。
EOF
  else
    echo "[git-automation] 前提不備のため自動化をスキップ (warn-only mode)"
  fi
  echo "=== Git Automation 終了 ==="
  echo ""
  exit 0
fi

# ========================================
# Step 2: 前日以前のブランチの処理（チェックアウトしない）
# ========================================
TODAY="$(date +%Y-%m-%d)"
TODAY_BRANCH="${BRANCH_PREFIX}${TODAY}"

# 起動時のブランチ（detached HEAD なら空）。このブランチの作業ツリーだけが自動コミット
# の対象になり、処理の最後にここへ戻す。
ORIG_BRANCH="$(git symbolic-ref --short -q HEAD || echo '')"

# 未マージのまま残った前日ブランチ。複数あれば起動時のブランチを優先する。
UNMERGED_PREV_BRANCHES=""

current_branch_name() {
  git symbolic-ref --short -q HEAD || echo ''
}

# 起動時のブランチの未コミット変更だけをコミットする（未追跡ファイルも含める）。
# 他のブランチの作業ツリーには触れない（チェックアウトしないため、変更は起動時のブランチのもの）。
commit_wip_if_current() {
  local branch="$1"
  [ -n "$ORIG_BRANCH" ] && [ "$branch" = "$ORIG_BRANCH" ] || return 0
  if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
    echo "  未コミット変更をコミット中..."
    git add -A
    git commit -m "chore: auto-commit on session start ($(date +%Y-%m-%d\ %H:%M))" >/dev/null 2>&1 || true
  fi
}

# ブランチ名を指定して push する（チェックアウト不要）。上流が無ければ -u で設定する。
# 未送信コミットが無ければ通信しない（毎回の push は起動時間の大半を占めていたため）。
push_branch() {
  local branch="$1"
  if git rev-parse --verify --quiet "refs/remotes/origin/$branch" >/dev/null; then
    if [ -n "$(git rev-list "origin/$branch..$branch" 2>/dev/null)" ]; then
      net git push origin "$branch" >/dev/null 2>&1 || echo "  [!] push 失敗"
    fi
  else
    net git push -u origin "$branch" >/dev/null 2>&1 || echo "  [!] push 失敗"
  fi
}

pr_state_of() {
  net $GH_CMD pr view "$1" --json state -q .state 2>/dev/null || echo ''
}

create_pr() {
  local branch="$1" body
  body="$(git log "${BASE_BRANCH}..${branch}" --oneline 2>/dev/null | head -50)"
  [ -z "$body" ] && body="自動作成された日次 PR"
  if net $GH_CMD pr create --base "$BASE_BRANCH" --head "$branch" --title "${branch}: 日次変更" --body "$body" >/dev/null 2>&1; then
    echo "  [OK] PR 作成完了"
  else
    echo "  [!] PR 作成失敗 (既に存在する可能性)"
  fi
}

# 内容が基準ブランチに含まれるか（マージ済みの判定）。
#   - HEAD が基準ブランチに到達済み（通常のマージ）、または
#   - 基準ブランチにない変更（git cherry の '+'）が1つも無い（squash マージ等）
# 基準ブランチの取得に失敗していれば判定できないため「含まれない」（削除しない）側に倒す。
is_merged_into_base() {
  local branch="$1" head
  git rev-parse --verify --quiet "refs/remotes/origin/$BASE_BRANCH" >/dev/null || return 1
  head="$(git rev-parse "$branch")"
  if git merge-base --is-ancestor "$head" "origin/$BASE_BRANCH"; then
    return 0
  fi
  if git cherry "origin/$BASE_BRANCH" "$branch" 2>/dev/null | grep -q '^+'; then
    return 1
  fi
  return 0
}

# ローカルのブランチを削除し、リモートからも消す。起動時のブランチを消す場合だけ
# 基準ブランチへ移る（それ以外はチェックアウトしない）。
delete_branch() {
  local branch="$1"
  if [ "$branch" = "$ORIG_BRANCH" ]; then
    git checkout "$BASE_BRANCH" >/dev/null 2>&1 || return 1
  fi
  git branch -D "$branch" >/dev/null 2>&1 || return 1
  net git push origin --delete "$branch" >/dev/null 2>&1 || true
  return 0
}

# 1つの前日ブランチを処理する。未マージならグローバルの候補へ積む。
process_prev_branch() {
  local branch="$1" pr_state
  echo "[$branch] 処理中..."

  commit_wip_if_current "$branch"
  push_branch "$branch"

  pr_state="$(pr_state_of "$branch")"
  if [ -z "$pr_state" ]; then
    echo "  PR を作成中..."
    create_pr "$branch"
    pr_state="OPEN"
  else
    echo "  PR 状態: $pr_state"
  fi

  if [ "$pr_state" = "MERGED" ]; then
    fetch_base
    if is_merged_into_base "$branch"; then
      if delete_branch "$branch"; then
        echo "  マージ済み（内容が基準ブランチに含まれる） → ブランチ削除"
        echo "  [OK] 削除完了"
        return 0
      fi
      echo "  [!] 削除できなかったため残します"
    else
      echo "  [!] PRはMERGEDですが、基準ブランチに無い変更が残っています。削除せず作業継続として扱います"
    fi
  else
    echo "  [!] 未マージのため削除しません (開発者のマージを待機)"
  fi
  UNMERGED_PREV_BRANCHES="${UNMERGED_PREV_BRANCHES}${branch}"$'\n'
  return 0
}

PREV_BRANCHES="$(git branch --format='%(refname:short)' | grep -E "^${BRANCH_PREFIX}[0-9]{4}-[0-9]{2}-[0-9]{2}$" | grep -v "^${TODAY_BRANCH}$" || true)"

if [ -n "$PREV_BRANCHES" ]; then
  echo "前日以前のブランチを検出:"
  echo "$PREV_BRANCHES" | sed 's/^/  - /'
  echo ""

  while IFS= read -r prev_branch; do
    [ -z "$prev_branch" ] && continue
    process_prev_branch "$prev_branch"
  done <<< "$PREV_BRANCHES"

  # 起動時のブランチへ戻す（削除で基準ブランチへ移った場合は、そのまま）
  cur="$(current_branch_name)"
  if [ -n "$ORIG_BRANCH" ] && [ "$cur" != "$ORIG_BRANCH" ] \
    && git show-ref --verify --quiet "refs/heads/$ORIG_BRANCH"; then
    git checkout "$ORIG_BRANCH" >/dev/null 2>&1 || true
  fi
  echo ""
fi

# 作業を継続する未マージのブランチ（起動時のブランチを優先、無ければ最後に見つかったもの）
UNMERGED_PREV_BRANCH=""
if [ -n "$UNMERGED_PREV_BRANCHES" ]; then
  UNMERGED_PREV_BRANCH="$(printf '%s' "$UNMERGED_PREV_BRANCHES" | grep -Fx -- "$ORIG_BRANCH" || true)"
  if [ -z "$UNMERGED_PREV_BRANCH" ]; then
    UNMERGED_PREV_BRANCH="$(printf '%s' "$UNMERGED_PREV_BRANCHES" | grep -v '^$' | tail -n 1)"
  fi
fi

# ========================================
# Step 3: 作業ブランチの決定（チェックアウトは最後の1回だけ）
# ========================================
# 既に当日ブランチがある場合は、同一日の2回目以降のセッションなのでそれを使う。
if git show-ref --verify --quiet "refs/heads/$TODAY_BRANCH"; then
  echo "当日ブランチ $TODAY_BRANCH に切り替え"
  [ "$(current_branch_name)" = "$TODAY_BRANCH" ] || git checkout "$TODAY_BRANCH" >/dev/null 2>&1 || true
  finish
fi

# 未マージの前日ブランチが残っている場合は「作業中」と判断し、当日ブランチを作らずに
# その上で作業を継続する（CLAUDE.md「運用フロー」の例外規定）。
if [ -n "$UNMERGED_PREV_BRANCH" ]; then
  echo "前日ブランチ $UNMERGED_PREV_BRANCH が未マージのため、当日ブランチは作成しません"
  echo "  → 作業中と判断し $UNMERGED_PREV_BRANCH 上で作業を継続します"
  echo "  → 当日ブランチへ切り替えるには、先に PR をマージしてください"
  [ "$(current_branch_name)" = "$UNMERGED_PREV_BRANCH" ] || git checkout "$UNMERGED_PREV_BRANCH" >/dev/null 2>&1 || true
  finish
fi

# 前日ブランチが全てマージ済み（または存在しない）→ 最新の base から当日ブランチを切る。
# 「最新化されているか」は pull の終了コードではなく origin との差で判定する。
git checkout "$BASE_BRANCH" >/dev/null 2>&1 || true
fetch_base

if git rev-parse --verify --quiet "refs/remotes/origin/$BASE_BRANCH" >/dev/null; then
  # origin より遅れている分だけ fast-forward で取り込む
  if [ "$(git rev-list --count "$BASE_BRANCH..origin/$BASE_BRANCH")" != "0" ]; then
    git merge --ff-only "origin/$BASE_BRANCH" >/dev/null 2>&1 || true
  fi
  behind="$(git rev-list --count "$BASE_BRANCH..origin/$BASE_BRANCH")"
  if [ "$behind" != "0" ]; then
    echo "  [!] $BASE_BRANCH が origin より $behind コミット遅れており fast-forward できません"
    echo "      当日ブランチの作成を中止します（古い base から切ると差分が巻き戻るため）"
    echo "      手動で $BASE_BRANCH を最新化してから、セッションを開き直してください"
    finish
  fi
fi

echo "当日ブランチ $TODAY_BRANCH を作成（$BASE_BRANCH は最新化済み）"
git checkout -b "$TODAY_BRANCH" >/dev/null 2>&1 || true

finish
