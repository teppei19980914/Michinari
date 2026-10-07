#!/usr/bin/env bash
# SessionStart hook: 日次ブランチ運用の自動化
#
# 設計（2026-10-07 全面改訂）:
#   この環境では、外部コマンドを1回起動するだけで約2秒かかる（git・find・gh等、実測：
#   `git rev-parse` 10回で19秒）。そのため、起動のたびに行う作業を2つに分け、片方だけを
#   起動時に同期で終わらせ、もう片方は起動の完了を待たせずに裏で続ける。
#
#   A（同期・高速。ブランチを決めて切り替えるところまで。外部コマンドの呼び出しを最小にする）:
#     1. 今日のブランチが既にあれば、それへ切り替える
#     2. 前日以前のブランチ（dev/*）が残っていれば、マージ済みかどうかをネットワークで
#        確認せずに、そのまま作業を継続する（起動時のブランチがその1つならそのまま、
#        そうでなければ最後に見つかったものへ切り替える。切り替えは起動につき最大1回）
#     3. 前日以前のブランチが無い場合だけ、base を最新化してから当日ブランチを作る
#        （このときだけネットワークを使う。新しい1日の最初の起動でのみ発生する）
#     起動時のブランチに未コミット変更があれば、それだけはAの中でコミットする
#     （ネットワーク不要で軽いため。取りこぼし防止、2026-09-17〜18と同じ考え方）。
#
#   B（非同期・裏。Aが前日ブランチを残した場合だけ、切り離して起動する）:
#     各 dev/* ブランチについて、push・PRの確認/作成・（マージ済みと確認できれば）削除を行う。
#     チェックアウトはしない（ref を指定して操作する）。今チェックアウトされているブランチは
#     削除しない（削除自体が失敗するうえ、作業中の可能性があるため）。
#
#   この分離により、「マージ済みと確認できるまでは削除しない」という安全性
#   （＝前日ブランチの成果は必ずmainに取り込まれてから消える。取りこぼしは起きない）は
#   変えない。トレードオフは、「マージされた直後の起動1回分だけ、当日ブランチへの切り替えが
#   次回の起動に遅れる」こと（詳細は docs/OPERATIONS.md）。
#
#   排他: 複数のセッションが同時に起動しても、片方だけが実行する（ロックファイル、
#   外部コマンドを使わず bash の機能だけで判定する）。ロックは B が終わるまで保持し、
#   B 自身が解放する（Bが無い場合はAの終わりで解放する）。
#
# 安全の原則（これまでの事故の再発防止）:
#   - 未マージのまま当日ブランチを base から切ると、前日の成果が作業ツリーから消える（2026-09-10・11）。
#   - PR状態（MERGED）だけで削除すると、マージ後に積まれた追加コミットが失われる（2026-09-14・10-02）。
#     削除前に、内容が基準ブランチに含まれることを確認する（到達済み、またはパッチが同一）。
#   - 未追跡ファイルも含めて自動コミットする（取りこぼし防止、2026-09-17〜18）。
#   - 前日ブランチを順にチェックアウトして処理すると、作業ツリーが入れ替わり続ける暴走が
#     起きた（2026-10-07）。そのため、ブランチの切り替えは起動につき最大1回のみ行う。

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
  exit 0
fi

# shellcheck disable=SC1090
. "$CONFIG_FILE"

if [ "${enabled:-false}" != "true" ]; then
  exit 0
fi

BRANCH_PREFIX="${branch_prefix:-dev/}"
BASE_BRANCH="${base_branch:-main}"
NET_TIMEOUT="${NET_TIMEOUT:-10}"
# gh の起動コマンド。テストで偽の gh を差し替えるための口（既定は gh）
GH_CMD="${GH_BIN:-gh}"

GIT_DIR="$(git rev-parse --git-dir)"
LOCK_FILE="$GIT_DIR/git-automation.lock"
LOCK_STALE_SECONDS="${LOCK_STALE_SECONDS:-600}"
AUTH_CACHE_FILE="$GIT_DIR/git-automation-auth-ok"
AUTH_CACHE_SECONDS="${AUTH_CACHE_SECONDS:-86400}"
CLEANUP_LOG="$GIT_DIR/git-automation-cleanup.log"
# マージ済みと確認できたが、今チェックアウト中のため削除できなかったブランチの印。
# 無ければ永久に削除できない（次回もまた「作業中」として同じブランチに留まり続け、
# 常に「今チェックアウト中」になってしまうため）。次回の前景は、ここに印のある
# ブランチだけが残っている場合、そこに留まらず当日ブランチの作成へ進み、
# チェックアウトが外れた状態で片付けにもう一度処理させる（詳細は Step 3 を参照）。
MERGEABLE_DIR="$GIT_DIR/git-automation-mergeable"
mergeable_marker_path() {
  printf '%s/%s' "$MERGEABLE_DIR" "${1//\//_}"
}
mark_mergeable() {
  mkdir -p "$MERGEABLE_DIR" 2>/dev/null && : > "$(mergeable_marker_path "$1")" 2>/dev/null || true
}
clear_mergeable() {
  rm -f "$(mergeable_marker_path "$1")" 2>/dev/null || true
}
is_marked_mergeable() {
  [ -f "$(mergeable_marker_path "$1")" ]
}

net() {
  if command -v timeout >/dev/null 2>&1; then
    timeout "$NET_TIMEOUT" "$@"
  else
    "$@"
  fi
}

echo ""
echo "=== Git Automation (SessionStart) ==="

finish() {
  echo "=== Git Automation 完了 ==="
  echo ""
  exit 0
}

# ========================================
# 排他（外部コマンド不使用。noclobberでの専有ファイル作成のみで判定する）
# ========================================
release_lock() {
  rm -f "$LOCK_FILE" 2>/dev/null || true
}

acquire_lock() {
  local restore_noclobber=1
  case "$-" in *C*) restore_noclobber=0 ;; esac
  set -C
  if { printf '%s %s\n' "$$" "$EPOCHSECONDS" > "$LOCK_FILE"; } 2>/dev/null; then
    [ "$restore_noclobber" -eq 1 ] && set +C
    return 0
  fi
  local pid held_at
  pid=0; held_at=0
  read -r pid held_at < "$LOCK_FILE" 2>/dev/null || true
  held_at="${held_at%$'\r'}"  # 何らかの理由でCRLFになっていても数値として読めるようにする
  if [[ "${held_at:-}" =~ ^[0-9]+$ ]] && [ $(( EPOCHSECONDS - held_at )) -ge "$LOCK_STALE_SECONDS" ]; then
    rm -f "$LOCK_FILE" 2>/dev/null || true
    if { printf '%s %s\n' "$$" "$EPOCHSECONDS" > "$LOCK_FILE"; } 2>/dev/null; then
      [ "$restore_noclobber" -eq 1 ] && set +C
      return 0
    fi
  fi
  [ "$restore_noclobber" -eq 1 ] && set +C
  return 1
}

if ! acquire_lock; then
  echo "[git-automation] 別の実行が進行中のためスキップ"
  echo ""
  exit 0
fi
# ここから先の早期終了は、このtrapでロックを解放する。Bへ引き継ぐ直前にだけ無効化する
# （Bの完了時にB自身が解放するため、Aでの解放と二重にならないようにする）。
trap release_lock EXIT

# ========================================
# Step 1: 前提チェック（ローカルで分かることだけ。外部コマンドは最小限）
# ========================================
# git の有無・リモートの形は、ブランチの判断そのものに要るため前景で確認する。
# gh の有無・認証は、使うのが片付け（B）だけなので、そこで確認する（前景を待たせない）。
REMOTE_URL="$(git remote get-url origin 2>/dev/null || echo '')"
GH_USABLE=1
if ! command -v "${GH_CMD%% *}" >/dev/null 2>&1; then
  GH_USABLE=0
elif [ -z "$REMOTE_URL" ] || [[ "$REMOTE_URL" != *github.com* ]]; then
  GH_USABLE=0
fi

if [ "$GH_USABLE" -eq 0 ] && [ ! -f "$SETUP_DONE_FILE" ]; then
  cat <<'EOF'

[git-automation] 初回セットアップが必要な場合があります（gh 未導入 / origin が GitHub ではない）:

  1. gh CLI をインストール:    https://cli.github.com/
  2. 認証:                     gh auth login
  3. リモート設定確認:         git remote -v

セットアップ完了後、以下を実行して案内を止める:
  touch .claude/.git-automation-setup-done

ブランチの作成・切り替えは、この確認に関わらず行う（push・PRの管理だけが対象外になる）。
EOF
fi

# gh の認証は片付け（B）の中で確認する（1日1回だけ。外部コマンドを使わず判定する）。
gh_authed() {
  local checked_at
  checked_at=0
  if [ -f "$AUTH_CACHE_FILE" ]; then
    read -r checked_at < "$AUTH_CACHE_FILE" 2>/dev/null || checked_at=0
    checked_at="${checked_at%$'\r'}"  # 何らかの理由でCRLFになっていても数値として読めるようにする
  fi
  if [[ "$checked_at" =~ ^[0-9]+$ ]] && [ $(( EPOCHSECONDS - checked_at )) -lt "$AUTH_CACHE_SECONDS" ]; then
    return 0
  fi
  if net $GH_CMD auth status >/dev/null 2>&1; then
    printf '%s\n' "$EPOCHSECONDS" > "$AUTH_CACHE_FILE"
    return 0
  fi
  return 1
}

# ========================================
# B（裏で行う片付け）で使う関数。チェックアウトはしない
# ========================================
BASE_FETCHED=0
fetch_base() {
  if [ "$BASE_FETCHED" -eq 0 ]; then
    net git fetch origin "$BASE_BRANCH" >/dev/null 2>&1 || true
    BASE_FETCHED=1
  fi
}

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

delete_branch() {
  git branch -D "$1" >/dev/null 2>&1 || return 1
  net git push origin --delete "$1" >/dev/null 2>&1 || true
  return 0
}

# 1つの前日ブランチを処理する（push・PR確認/作成・削除判定）。チェックアウトはしない。
# 「マージ済みと確認できた」印は、この回の判定で常に最新化する（今回そうでなければ外す）。
process_prev_branch() {
  local branch="$1" pr_state
  echo "[$branch] 処理中..."
  clear_mergeable "$branch"

  push_branch "$branch"

  pr_state="$(pr_state_of "$branch")"
  if [ -z "$pr_state" ]; then
    echo "  PR を作成中..."
    create_pr "$branch"
    pr_state="OPEN"
  else
    echo "  PR 状態: $pr_state"
  fi

  if [ "$pr_state" != "MERGED" ]; then
    echo "  [!] 未マージのため削除しません (開発者のマージを待機)"
    return 0
  fi

  fetch_base
  if ! is_merged_into_base "$branch"; then
    echo "  [!] PRはMERGEDですが、基準ブランチに無い変更が残っています。削除せず次回に確認します"
    return 0
  fi

  local cur
  cur="$(git symbolic-ref --short -q HEAD || echo '')"
  if [ "$branch" = "$cur" ]; then
    echo "  [!] マージ済みですが、現在チェックアウト中のため削除を見送ります"
    echo "      （次回、このブランチから離れていれば削除します）"
    mark_mergeable "$branch"
    return 0
  fi

  if delete_branch "$branch"; then
    echo "  マージ済み（内容が基準ブランチに含まれる） → ブランチ削除"
    echo "  [OK] 削除完了"
  else
    echo "  [!] 削除できなかったため残します"
  fi
}

run_cleanup() {
  local branch
  if [ "$GH_USABLE" -eq 0 ]; then
    echo "[git-automation] gh が使えないため、push・PRの管理を見送ります (warn-only mode)"
    release_lock
    return 0
  fi
  if ! gh_authed; then
    echo "[git-automation] gh CLI が未認証のため、push・PRの管理を見送ります (実行: gh auth login)"
    release_lock
    return 0
  fi
  for branch in "$@"; do
    [ -z "$branch" ] && continue
    process_prev_branch "$branch"
  done
  release_lock
}

# 片付け（B）を起動する。通常は切り離して裏で動かし、起動の完了を待たせない。
# テスト（GIT_AUTOMATION_SYNC=1）では、結果を検証できるようその場で（同期で）実行する。
launch_cleanup() {
  trap - EXIT
  if [ -n "${GIT_AUTOMATION_SYNC:-}" ]; then
    run_cleanup "$@"
  else
    ( run_cleanup "$@" ) >>"$CLEANUP_LOG" 2>&1 < /dev/null &
    disown 2>/dev/null || true
  fi
}

# ========================================
# Step 2: 起動時のブランチの把握（外部コマンドは最小限）
# ========================================
TODAY="$(printf '%(%Y-%m-%d)T' -1)"
TODAY_BRANCH="${BRANCH_PREFIX}${TODAY}"

ORIG_BRANCH="$(git symbolic-ref --short -q HEAD || echo '')"

# ブランチ一覧は1回だけ取得し、以降は bash の文字列処理だけで判定する。
BRANCH_LIST="$(git branch --format='%(refname:short)')"

TODAY_BRANCH_EXISTS=0
PREV_BRANCHES=()
while IFS= read -r b; do
  [ -z "$b" ] && continue
  if [ "$b" = "$TODAY_BRANCH" ]; then
    TODAY_BRANCH_EXISTS=1
    continue
  fi
  if [[ "$b" =~ ^${BRANCH_PREFIX}[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    PREV_BRANCHES+=("$b")
  fi
done <<< "$BRANCH_LIST"

# 「マージ済みと確認できたが、今チェックアウト中で削除できなかった」印の付いたブランチを
# 除いた一覧。これが空なら、残っているのはチェックアウトさえ外せば削除できるものだけ
# ということなので、そこに留まらず当日ブランチの作成へ進む（デッドロック防止。後述）。
EFFECTIVE_PREV_BRANCHES=()
for b in "${PREV_BRANCHES[@]+"${PREV_BRANCHES[@]}"}"; do
  is_marked_mergeable "$b" || EFFECTIVE_PREV_BRANCHES+=("$b")
done

# 起動時のブランチが前日ブランチの1つであれば、その未コミット変更をコミットする
# （ネットワーク不要で軽いため、ここは同期で行う。取りこぼし防止）。
if [ -n "$ORIG_BRANCH" ]; then
  is_prev=0
  for b in "${PREV_BRANCHES[@]+"${PREV_BRANCHES[@]}"}"; do
    [ "$b" = "$ORIG_BRANCH" ] && is_prev=1
  done
  if [ "$is_prev" -eq 1 ]; then
    if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
      echo "未コミット変更をコミット中..."
      git add -A
      git commit -m "chore: auto-commit on session start ($(printf '%(%Y-%m-%d %H:%M)T' -1))" >/dev/null 2>&1 || true
    fi
  fi
fi

# ========================================
# Step 3: 作業ブランチの決定（切り替えは起動につき最大1回）
# ========================================
# 現在のブランチは ORIG_BRANCH から追跡する（checkout のたびに git へ問い合わせ直さない）。
CURRENT_BRANCH="$ORIG_BRANCH"
checkout_if_needed() {
  local target="$1"
  if [ "$CURRENT_BRANCH" != "$target" ]; then
    git checkout "$target" >/dev/null 2>&1 || true
    CURRENT_BRANCH="$target"
  fi
}

# 既に当日ブランチがある場合は、同一日の2回目以降のセッションなのでそれを使う。
if [ "$TODAY_BRANCH_EXISTS" -eq 1 ]; then
  echo "当日ブランチ $TODAY_BRANCH に切り替え"
  checkout_if_needed "$TODAY_BRANCH"
  if [ "${#PREV_BRANCHES[@]}" -gt 0 ]; then
    echo "前日以前のブランチが残っています（裏で確認します）:"
    printf '  - %s\n' "${PREV_BRANCHES[@]}"
    launch_cleanup "${PREV_BRANCHES[@]}"
  fi
  finish
fi

# 未マージの可能性がある前日ブランチ（まだマージ済みと確認できていないもの）が残っていれば、
# ネットワークで確認せずに作業を継続する（CLAUDE.md「運用フロー」の例外規定）。マージ済みの
# 確認・削除・当日ブランチの作成準備は、裏の処理が次回までに行う。
if [ "${#EFFECTIVE_PREV_BRANCHES[@]}" -gt 0 ]; then
  echo "前日以前のブランチを検出:"
  printf '  - %s\n' "${PREV_BRANCHES[@]}"
  echo ""

  target=""
  for b in "${EFFECTIVE_PREV_BRANCHES[@]}"; do
    [ "$b" = "$ORIG_BRANCH" ] && target="$ORIG_BRANCH"
  done
  if [ -z "$target" ]; then
    target="${EFFECTIVE_PREV_BRANCHES[${#EFFECTIVE_PREV_BRANCHES[@]}-1]}"
  fi

  echo "マージ済みかどうかはこの場では確認せず、当日ブランチは作成しません"
  echo "  → 作業中と判断し $target 上で作業を継続します（確認は裏で行います）"
  echo "  → 当日ブランチへの切り替えは、マージ済みと確認でき次第、次回の起動で行われます"
  checkout_if_needed "$target"
  launch_cleanup "${PREV_BRANCHES[@]}"
  finish
fi

# 前日ブランチが全く無い、または残っているのは「マージ済みと確認できたが前回は
# チェックアウト中で削除できなかった」ものだけ → 最新の base から当日ブランチを切る
# （このときだけネットワークを使う）。後者の場合、ここでチェックアウトを外れたことで
# 削除できるようになるため、片付けをもう一度走らせる。
checkout_if_needed "$BASE_BRANCH"
if [ "${#PREV_BRANCHES[@]}" -gt 0 ]; then
  echo "マージ済みと確認できていたブランチの削除を再試行します（裏で行います）:"
  printf '  - %s\n' "${PREV_BRANCHES[@]}"
  launch_cleanup "${PREV_BRANCHES[@]}"
fi
fetch_base

behind="$(git rev-list --count "$BASE_BRANCH..origin/$BASE_BRANCH" 2>/dev/null || echo 0)"
if [ "$behind" != "0" ]; then
  git merge --ff-only "origin/$BASE_BRANCH" >/dev/null 2>&1 || true
  # ff-only が失敗した場合（分岐している等）だけ、遅れが解消したかを数え直す
  behind="$(git rev-list --count "$BASE_BRANCH..origin/$BASE_BRANCH" 2>/dev/null || echo 0)"
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
