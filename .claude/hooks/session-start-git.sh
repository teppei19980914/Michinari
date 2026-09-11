#!/usr/bin/env bash
# SessionStart hook: 日次ブランチ運用の自動化
#
# 動作:
#   1. git automation が有効か確認 (.claude/.git-automation-config)
#   2. gh CLI の前提を確認 (Hybrid: 初回セットアップ案内、以降は warn-only)
#   3. 前日以前の dev/YYYY-MM-DD ブランチを検出
#   4. 未コミット変更があればコミット
#   5. PR 未作成なら作成
#   6. PR が MERGED なら旧ブランチを削除
#   7. 当日ブランチの決定（CLAUDE.md「運用フロー」の分岐）
#      - 未マージの前日ブランチが残っている場合: それを「作業中」と判断し、当日ブランチを
#        作らずその前日ブランチ上で作業を継続する
#      - 前日ブランチが全てマージ済み（または存在しない）場合のみ、最新の base から
#        当日の dev/YYYY-MM-DD を作成・チェックアウトする
#      - 当日ブランチが既にある場合はチェックアウトのみ（同一日複数セッション対応）
#
# 未マージのまま当日ブランチを base から切ると、前日の成果が作業ツリーから消えて
# 取りこぼしが起きる（2026-09-10・09-11 に実際に発生）。その再発防止のための分岐である。

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
check_prereqs() {
  local missing=0

  if ! command -v git >/dev/null 2>&1; then
    echo "  [x] git が未インストール"
    missing=1
  fi

  if ! command -v gh >/dev/null 2>&1; then
    echo "  [x] gh CLI が未インストール (https://cli.github.com/)"
    missing=1
  else
    if ! gh auth status >/dev/null 2>&1; then
      echo "  [x] gh CLI が未認証 (実行: gh auth login)"
      missing=1
    fi
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
# Step 2: 前日以前のブランチを検出
# ========================================
TODAY="$(date +%Y-%m-%d)"
TODAY_BRANCH="${BRANCH_PREFIX}${TODAY}"

# ローカルの dev/YYYY-MM-DD パターンのうち今日以外
PREV_BRANCHES="$(git branch --format='%(refname:short)' | grep -E "^${BRANCH_PREFIX}[0-9]{4}-[0-9]{2}-[0-9]{2}$" | grep -v "^${TODAY_BRANCH}$" || true)"

# 未マージのまま残った前日ブランチ（作業継続の候補）。最後の1件を採用する。
UNMERGED_PREV_BRANCH=""

if [ -n "$PREV_BRANCHES" ]; then
  echo "前日以前のブランチを検出:"
  echo "$PREV_BRANCHES" | sed 's/^/  - /'
  echo ""

  while IFS= read -r prev_branch; do
    [ -z "$prev_branch" ] && continue
    echo "[$prev_branch] 処理中..."

    # ブランチをチェックアウト
    if ! git checkout "$prev_branch" 2>/dev/null; then
      echo "  [!] チェックアウト失敗 — スキップ"
      continue
    fi

    # 未コミット変更をコミット
    if ! git diff --quiet || ! git diff --cached --quiet; then
      echo "  未コミット変更をコミット中..."
      git add -A
      git commit -m "chore: auto-commit on session start ($(date +%Y-%m-%d\ %H:%M))" >/dev/null 2>&1 || true
    fi

    # リモートにプッシュ (上流未設定なら -u)
    if git rev-parse --abbrev-ref --symbolic-full-name "@{u}" >/dev/null 2>&1; then
      git push 2>/dev/null || echo "  [!] push 失敗"
    else
      git push -u origin "$prev_branch" 2>/dev/null || echo "  [!] push 失敗"
    fi

    # PR の存在確認
    pr_state="$(gh pr view "$prev_branch" --json state -q .state 2>/dev/null || echo '')"

    if [ -z "$pr_state" ]; then
      # PR 未作成 → 作成
      echo "  PR を作成中..."
      pr_title="${prev_branch}: 日次変更"
      pr_body="$(git log "${BASE_BRANCH}..${prev_branch}" --oneline 2>/dev/null | head -50)"
      [ -z "$pr_body" ] && pr_body="自動作成された日次 PR"
      if gh pr create --base "$BASE_BRANCH" --head "$prev_branch" --title "$pr_title" --body "$pr_body" 2>/dev/null; then
        echo "  [OK] PR 作成完了"
      else
        echo "  [!] PR 作成失敗 (既に存在する可能性)"
      fi
      pr_state="OPEN"
    else
      echo "  PR 状態: $pr_state"
    fi

    # MERGED なら削除
    if [ "$pr_state" = "MERGED" ]; then
      echo "  マージ済み → ブランチ削除"
      git checkout "$BASE_BRANCH" 2>/dev/null || true
      git branch -D "$prev_branch" 2>/dev/null || true
      git push origin --delete "$prev_branch" 2>/dev/null || true
      echo "  [OK] 削除完了"
    else
      echo "  [!] 未マージのため削除しません (開発者のマージを待機)"
      UNMERGED_PREV_BRANCH="$prev_branch"
    fi
  done <<< "$PREV_BRANCHES"
  echo ""
fi

# ========================================
# Step 3: 作業ブランチの決定
# ========================================
# 既に当日ブランチがある場合は、同一日の2回目以降のセッションなのでそれを使う
# （前日ブランチの状態に関わらず、当日の作業を引き継ぐのが正しい）。
if git show-ref --verify --quiet "refs/heads/$TODAY_BRANCH"; then
  echo "当日ブランチ $TODAY_BRANCH に切り替え"
  git checkout "$TODAY_BRANCH"
  finish
fi

# 未マージの前日ブランチが残っている場合は「作業中」と判断し、当日ブランチを作らずに
# その上で作業を継続する（CLAUDE.md「運用フロー」の例外規定）。base から切ってしまうと
# 前日の成果が作業ツリーから消え、取りこぼしの原因になる。
if [ -n "$UNMERGED_PREV_BRANCH" ]; then
  echo "前日ブランチ $UNMERGED_PREV_BRANCH が未マージのため、当日ブランチは作成しません"
  echo "  → 作業中と判断し $UNMERGED_PREV_BRANCH 上で作業を継続します"
  echo "  → 当日ブランチへ切り替えるには、先に PR をマージしてください"
  git checkout "$UNMERGED_PREV_BRANCH" 2>/dev/null || true
  finish
fi

# 前日ブランチが全てマージ済み（または存在しない）→ 最新の base から当日ブランチを切る。
# 「最新化されているか」は pull の終了コードではなく origin との差で判定する
# （リモート未設定・オフラインでも pull は失敗しうるが、それ自体は巻き戻しの危険を意味しない）。
git checkout "$BASE_BRANCH" 2>/dev/null || true
git fetch origin "$BASE_BRANCH" >/dev/null 2>&1 || true

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
git checkout -b "$TODAY_BRANCH"

finish
