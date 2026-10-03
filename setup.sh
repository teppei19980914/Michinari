#!/bin/bash
# Claude Code Level 5 テンプレート セットアップスクリプト
#
# 使い方:
#   新規プロジェクト:
#     cd /path/to/new-repo
#     bash /path/to/ClaudeCodeTemplate/setup.sh
#
#   既存プロジェクトへの後付け適用 (差分のみ追加):
#     cd /path/to/existing-repo
#     bash /path/to/ClaudeCodeTemplate/setup.sh --upgrade
#
# 対話形式でプロジェクト固有の設定を入力し、テンプレートを適用します。
#
# Windows (PowerShell) の注意点:
#   単に `bash setup.sh` と実行すると、`bash` が Git Bash ではなく WSL の中継スタブ
#   (C:\Windows\System32\bash.exe) に解決され、
#   execvpe(/bin/bash) failed: No such file or directory エラーになることがあります。
#   その場合は Git Bash のフルパスを明示してください:
#     & "C:\Program Files\Git\bin\bash.exe" setup.sh

set -e

UPGRADE_MODE=false
if [ "${1:-}" = "--upgrade" ]; then
  UPGRADE_MODE=true
fi

TEMPLATE_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$(pwd)"

echo "=== Claude Code Level 5 セットアップ ==="
if [ "$UPGRADE_MODE" = true ]; then
  echo "モード:       --upgrade (差分追加のみ・既存ファイルは保護)"
fi
echo "テンプレート: $TEMPLATE_DIR"
echo "適用先:       $TARGET_DIR"
echo ""

# 制御文字混入チェック用パターン（矢印キー等のエスケープシーケンス誤入力を検知）
# タブ(0x09)/改行(0x0A)/CR(0x0D)は許容し、ESC(0x1B)等の制御文字のみ検知する
CTRL_CHAR_PATTERN=$'[\x01-\x08\x0e-\x1f\x7f]'

# 入力受付ヘルパー
# -r: バックスラッシュをエスケープ文字として扱わない
#     (GNU Bash Reference Manual "Shell Builtin Commands" read: -r 無指定時は
#      バックスラッシュが直後の1文字をエスケープする特殊文字として解釈され、
#      "\" と直後の文字が消費されて消える。Windows の絶対パス
#      (例: C:\Users\...) を直接入力すると区切りが失われるため必須)
# -e: readline を有効化し、矢印キーでの行編集・履歴呼び出しを可能にする
#     (GNU Bash Reference Manual "Bash Builtins": 標準入力が端末の場合、
#      read -e は readline を使って行を取得する)
# 加えて、制御文字（矢印キーの誤入力等）が紛れ込んでいないかを検証し、
# 検出時は再入力を促す（見た目では気づきにくい入力破損を防ぐため）
read_clean() {
  local prompt="$1"
  local __varname="$2"
  local __input
  while true; do
    read -r -e -p "$prompt" __input
    if LC_ALL=C grep -q "$CTRL_CHAR_PATTERN" <<<"$__input"; then
      echo "  ⚠ 制御文字が入力に混入しています（矢印キー等の誤入力の可能性）。再入力してください。" >&2
      continue
    fi
    break
  done
  printf -v "$__varname" '%s' "$__input"
}

# 既存ファイルの確認 (新規モードのみ)
if [ "$UPGRADE_MODE" = false ]; then
  if [ -d "$TARGET_DIR/.claude" ] || [ -f "$TARGET_DIR/CLAUDE.md" ]; then
    read_clean "既存の .claude/ または CLAUDE.md が見つかりました。上書きしますか？ (y/n): " OVERWRITE
    if [ "$OVERWRITE" != "y" ]; then
      echo "キャンセルしました。--upgrade フラグでの差分追加も検討してください。"
      exit 0
    fi
  fi
fi

# プロジェクト情報の入力
read_clean "プロジェクト名 (例: ユメログ): " PROJECT_NAME
read_clean "技術スタック (例: Flutter / Dart): " TECH_STACK
read_clean "テストコマンド (例: flutter test): " TEST_COMMAND
read_clean "静的解析コマンド (例: flutter analyze): " ANALYZE_COMMAND
read_clean "ビルドコマンド (例: flutter build web): " BUILD_COMMAND
read_clean "フォーマットコマンド (例: dart format --fix): " FORMAT_COMMAND
read_clean "プロジェクトの絶対パス: " PROJECT_DIR

echo ""
echo "--- コーディングルール（CODING_RULES.md 用） ---"
read_clean "ラベル/文言の定義ファイル (例: src/labels.js): " LABEL_FILE_PATH
read_clean "画面ID・定数の定義ファイル (例: src/constants.js): " CONSTANTS_FILE_PATH
read_clean "共通処理ディレクトリ (例: src/utils/): " UTILS_DIR
read_clean "共通コンポーネントディレクトリ (例: src/components/): " COMPONENTS_DIR
read_clean "命名規則の要約 (例: コンポーネント:PascalCase / 変数・関数:camelCase / CSS:kebab-case): " NAMING_CONVENTION_SUMMARY

# Git 自動化のオプトイン
echo ""
echo "--- Git 自動化（日次ブランチ運用） ---"
echo "有効化すると以下が自動実行されます:"
echo "  - SessionStart: 前日ブランチの PR 作成・マージ済みなら削除・新ブランチ作成"
echo "  - Stop:          テスト成功時に自動 commit & push"
echo "  - 前提:          gh CLI の認証 (gh auth login) と GitHub リモート"
read_clean "Git 自動化を有効にしますか？ (y/n): " ENABLE_GIT_AUTO
ENABLE_GIT_AUTO="${ENABLE_GIT_AUTO:-n}"

BASE_BRANCH=""
if [ "$ENABLE_GIT_AUTO" = "y" ]; then
  read_clean "ベースブランチ (デフォルト: main): " BASE_BRANCH
  BASE_BRANCH="${BASE_BRANCH:-main}"
fi

echo ""
echo "--- 設定内容 ---"
echo "プロジェクト名:       $PROJECT_NAME"
echo "技術スタック:         $TECH_STACK"
echo "テストコマンド:       $TEST_COMMAND"
echo "静的解析コマンド:     $ANALYZE_COMMAND"
echo "ビルドコマンド:       $BUILD_COMMAND"
echo "フォーマットコマンド: $FORMAT_COMMAND"
echo "プロジェクトパス:     $PROJECT_DIR"
echo "ラベルファイル:       $LABEL_FILE_PATH"
echo "定数ファイル:         $CONSTANTS_FILE_PATH"
echo "共通処理ディレクトリ: $UTILS_DIR"
echo "共通部品ディレクトリ: $COMPONENTS_DIR"
echo "命名規則:             $NAMING_CONVENTION_SUMMARY"
echo "Git 自動化:           $ENABLE_GIT_AUTO ${BASE_BRANCH:+(base: $BASE_BRANCH)}"
echo ""
read_clean "この内容でセットアップしますか？ (y/n): " CONFIRM
if [ "$CONFIRM" != "y" ]; then
  echo "キャンセルしました。"
  exit 0
fi

# ========================================
# ファイルコピー (--upgrade では既存を保護)
# ========================================
copy_file() {
  local src="$1"
  local dst="$2"
  if [ "$UPGRADE_MODE" = true ] && [ -e "$dst" ]; then
    echo "  スキップ (既存): $dst"
    return 0
  fi
  cp "$src" "$dst"
  echo "  配置: $dst"
}

copy_dir_files() {
  local src_dir="$1"
  local dst_dir="$2"
  mkdir -p "$dst_dir"
  if [ ! -d "$src_dir" ]; then return 0; fi
  find "$src_dir" -mindepth 1 -maxdepth 1 -type f | while read -r f; do
    copy_file "$f" "$dst_dir/$(basename "$f")"
  done
}

echo ""
echo "テンプレートをコピー中..."
mkdir -p "$TARGET_DIR/.claude"
copy_file "$TEMPLATE_DIR/CLAUDE.md" "$TARGET_DIR/CLAUDE.md"
copy_file "$TEMPLATE_DIR/.claude/settings.json" "$TARGET_DIR/.claude/settings.json"
copy_dir_files "$TEMPLATE_DIR/.claude/hooks" "$TARGET_DIR/.claude/hooks"
copy_dir_files "$TEMPLATE_DIR/.claude/skills" "$TARGET_DIR/.claude/skills"
copy_dir_files "$TEMPLATE_DIR/.claude/agents" "$TARGET_DIR/.claude/agents"

# ドキュメント雛形のコピー（既存ファイルがあればスキップ）
echo "ドキュメント雛形を配置中..."
for tpl in DESIGN REQUIREMENTS OPERATIONS CODING_RULES SPECIFICATION; do
  src="$TEMPLATE_DIR/docs/templates/${tpl}.template.md"
  dst="$TARGET_DIR/${tpl}.md"
  if [ -f "$src" ] && [ ! -f "$dst" ]; then
    cp "$src" "$dst"
    echo "  配置: ${tpl}.md"
  elif [ -f "$dst" ]; then
    echo "  スキップ: ${tpl}.md（既存）"
  fi
done

# CI ワークフロー雛形のコピー（既存ファイルがあればスキップ）
echo "CI ワークフロー雛形を配置中..."
mkdir -p "$TARGET_DIR/.github/workflows"
if [ -f "$TEMPLATE_DIR/.github/workflows/security.yml.template" ] && [ ! -f "$TARGET_DIR/.github/workflows/security.yml" ] && [ ! -f "$TARGET_DIR/.github/workflows/security.yml.template" ]; then
  cp "$TEMPLATE_DIR/.github/workflows/security.yml.template" "$TARGET_DIR/.github/workflows/security.yml.template"
  echo "  配置: .github/workflows/security.yml.template"
  echo "    → 有効化するには .template を外してリネームしてください"
fi

# Git 自動化の設定ファイル生成
if [ "$ENABLE_GIT_AUTO" = "y" ]; then
  CONFIG_PATH="$TARGET_DIR/.claude/.git-automation-config"
  cat > "$CONFIG_PATH" <<EOF
# Git Automation Config
# このファイルが存在し enabled=true の場合のみ自動化が動作します
enabled=true
branch_prefix=dev/
base_branch=$BASE_BRANCH
EOF
  echo "Git 自動化を有効化: $CONFIG_PATH"
  echo "  → 初回は gh auth login を実行してください"
fi

# hooks スクリプトに実行権限を付与
chmod +x "$TARGET_DIR/.claude/hooks/"*.sh 2>/dev/null || true

# メモリ（ユーザー情報・横断的フィードバック）を Claude Code のメモリ領域にコピー
SEED_DIR="$TEMPLATE_DIR/.claude/memory-seed"
if [ -d "$SEED_DIR" ] && [ -n "$(ls "$SEED_DIR"/*.md 2>/dev/null)" ]; then
  echo "メモリシードを配置中..."
  # Claude Code のメモリパスを生成 (パスをハイフンに変換)
  NORMALIZED_PATH="$(echo "$PROJECT_DIR" | sed 's|[:\\]|-|g; s|/|-|g; s|^-||; s|-$||')"
  CLAUDE_HOME="${APPDATA:-$HOME/.config}/claude"
  if [ -d "$HOME/.claude" ]; then
    CLAUDE_HOME="$HOME/.claude"
  fi
  MEMORY_DIR="$CLAUDE_HOME/projects/$NORMALIZED_PATH/memory"
  mkdir -p "$MEMORY_DIR"
  for seed_file in "$SEED_DIR"/*.md; do
    dst="$MEMORY_DIR/$(basename "$seed_file")"
    if [ ! -f "$dst" ]; then
      cp "$seed_file" "$dst"
      echo "  配置: $(basename "$seed_file")"
    else
      echo "  スキップ: $(basename "$seed_file")（既存）"
    fi
  done
  echo "  メモリ配置先: $MEMORY_DIR"
fi

# プレースホルダを置換
#
# 注意: sed の s///（置換テキスト側）はバックスラッシュをエスケープ導入
# 文字として解釈するため、Windows の絶対パス (例: C:\Users\...) を
# そのまま渡すと区切りが消失する
# (参照: GNU sed manual "Escapes" — 置換テキスト中の \ をリテラルに
#  出力するには \\ が必要。1個の \ は \n 等の制御文字や \L/\U 等の
#  大小文字変換シーケンスとして解釈され得る)。
#
# bash の ${var/pattern/replacement} も同様の罠を持つため単純な代替に
# ならない (参照: GNU Bash Reference Manual "Shell Parameter Expansion" —
# replacement 側で \ は & をエスケープする特殊文字として扱われ、
# \\ でようやく1個のリテラル \ になる)。
#
# そのため置換は「パターン一致部分の削除 (${var#pattern} / ${var%pattern}、
# 置換フィールドを持たない) + 単純な文字列連結」のみで組み立て、
# 値を一切の特殊文字解釈にさらさない。
#
# .json ファイルは JSON 文字列としても妥当である必要があるため、
# 値中の \ と " を JSON エスケープしてから埋め込む。
declare -A PLACEHOLDER_VALUES=(
  ["{{PROJECT_NAME}}"]="$PROJECT_NAME"
  ["{{TECH_STACK}}"]="$TECH_STACK"
  ["{{TEST_COMMAND}}"]="$TEST_COMMAND"
  ["{{ANALYZE_COMMAND}}"]="$ANALYZE_COMMAND"
  ["{{BUILD_COMMAND}}"]="$BUILD_COMMAND"
  ["{{FORMAT_COMMAND}}"]="$FORMAT_COMMAND"
  ["{{PROJECT_DIR}}"]="$PROJECT_DIR"
  ["{{LABEL_FILE_PATH}}"]="$LABEL_FILE_PATH"
  ["{{CONSTANTS_FILE_PATH}}"]="$CONSTANTS_FILE_PATH"
  ["{{UTILS_DIR}}"]="$UTILS_DIR"
  ["{{COMPONENTS_DIR}}"]="$COMPONENTS_DIR"
  ["{{NAMING_CONVENTION_SUMMARY}}"]="$NAMING_CONVENTION_SUMMARY"
)

# "$1" 中に現れる全ての "$2" を "$3" へ、特殊文字解釈なしに置換する
literal_replace() {
  local content="$1" search="$2" replacement="$3"
  local result="" remainder="$content"
  while true; do
    case "$remainder" in
      *"$search"*)
        result="$result${remainder%%"$search"*}$replacement"
        remainder="${remainder#*"$search"}"
        ;;
      *)
        result="$result$remainder"
        break
        ;;
    esac
  done
  printf '%s' "$result"
}

json_escape() {
  local s="$1"
  s="$(literal_replace "$s" '\' '\\')"
  s="$(literal_replace "$s" '"' '\"')"
  printf '%s' "$s"
}

replace_placeholders_in_file() {
  local file="$1"
  local is_json=false
  case "$file" in
    *.json) is_json=true ;;
  esac

  local content
  content="$(cat "$file"; printf x)"
  content="${content%x}"

  local key val
  for key in "${!PLACEHOLDER_VALUES[@]}"; do
    val="${PLACEHOLDER_VALUES[$key]}"
    if [ "$is_json" = true ]; then
      val="$(json_escape "$val")"
    fi
    content="$(literal_replace "$content" "$key" "$val"; printf x)"
    content="${content%x}"
  done

  printf '%s' "$content" > "$file"
}

echo "プレースホルダを置換中..."
find "$TARGET_DIR/.claude" "$TARGET_DIR/CLAUDE.md" "$TARGET_DIR/CODING_RULES.md" -type f \( -name "*.md" -o -name "*.json" -o -name "*.sh" \) 2>/dev/null | while IFS= read -r file; do
  replace_placeholders_in_file "$file"
done

# 生成ファイルの検証: 未置換プレースホルダー・制御文字混入を検出する
echo "生成ファイルを検証中..."
VERIFY_TARGETS=("$TARGET_DIR/.claude" "$TARGET_DIR/CLAUDE.md" "$TARGET_DIR/CODING_RULES.md")
UNRESOLVED_FILES="$(grep -rlE '\{\{[A-Z_]+\}\}' "${VERIFY_TARGETS[@]}" 2>/dev/null || true)"
if [ -n "$UNRESOLVED_FILES" ]; then
  echo "⚠ 警告: 未置換のプレースホルダー ({{...}}) が残っているファイルがあります:"
  echo "$UNRESOLVED_FILES" | sed 's/^/    /'
fi

CONTROL_CHAR_FILES="$(LC_ALL=C grep -rl "$CTRL_CHAR_PATTERN" "${VERIFY_TARGETS[@]}" 2>/dev/null || true)"
if [ -n "$CONTROL_CHAR_FILES" ]; then
  echo "⚠ 警告: 制御文字（入力破損の可能性）が含まれるファイルがあります:"
  echo "$CONTROL_CHAR_FILES" | sed 's/^/    /'
fi

# .gitignore に機密ファイルパターンを追記（既存に追記）
GITIGNORE="$TARGET_DIR/.gitignore"
SECURITY_IGNORES=".env
.env.*
!.env.example
*.pem
*.key
*.p12
*.pfx
credentials.json
secrets.yaml
secrets.yml
id_rsa
id_rsa.pub
.claude/.git-automation-setup-done"

if [ -f "$GITIGNORE" ]; then
  if ! grep -q "# Security (added by ClaudeCodeTemplate)" "$GITIGNORE"; then
    echo "" >> "$GITIGNORE"
    echo "# Security (added by ClaudeCodeTemplate)" >> "$GITIGNORE"
    echo "$SECURITY_IGNORES" >> "$GITIGNORE"
    echo ".gitignore にセキュリティ関連パターンを追記しました"
  fi
else
  echo "# Security (added by ClaudeCodeTemplate)" > "$GITIGNORE"
  echo "$SECURITY_IGNORES" >> "$GITIGNORE"
  echo ".gitignore を新規作成しました"
fi

echo ""
echo "=== セットアップ完了 ==="
echo ""
echo "作成/更新されたファイル:"
echo "  $TARGET_DIR/CLAUDE.md"
echo "  $TARGET_DIR/.claude/settings.json"
echo "  $TARGET_DIR/.claude/hooks/ (6 hooks)"
echo "  $TARGET_DIR/.claude/skills/ (5 スキル)"
echo "  $TARGET_DIR/.claude/agents/ (10 エージェント)"
echo "  $TARGET_DIR/DESIGN.md / REQUIREMENTS.md / OPERATIONS.md / CODING_RULES.md / SPECIFICATION.md (雛形)"
echo "  $TARGET_DIR/.github/workflows/security.yml.template"
echo "  $TARGET_DIR/.gitignore (セキュリティパターン追記)"
if [ "$ENABLE_GIT_AUTO" = "y" ]; then
  echo "  $TARGET_DIR/.claude/.git-automation-config (Git 自動化有効)"
fi
echo ""
echo "次のステップ:"
echo "  1. CLAUDE.md をプロジェクトに合わせて調整"
echo "  2. DESIGN.md / REQUIREMENTS.md / OPERATIONS.md / CODING_RULES.md / SPECIFICATION.md を記入"
echo "  3. CI を有効化する場合は security.yml.template から .template を除去"
echo "  4. gitleaks をインストール推奨: https://github.com/gitleaks/gitleaks"
echo "     osv-scanner もインストール推奨（Stop hookで依存脆弱性をCVSSスコア付きで表示）: https://google.github.io/osv-scanner/installation/"
echo "  5. settings.json の許可設定は初期状態で Bash(*)（全許可）です。実際に使うコマンドが固まったら"
echo "     /fewer-permission-prompts で最小権限のホワイトリストに絞り込むことを推奨します"
if [ "$ENABLE_GIT_AUTO" = "y" ]; then
  echo "  6. gh CLI 認証: gh auth login"
  echo "  7. 認証完了後: touch $TARGET_DIR/.claude/.git-automation-setup-done"
  echo "  8. Claude Code でセッションを開始 (SessionStart Hook が動作確認)"
else
  echo "  6. Claude Code でセッションを開始"
fi
