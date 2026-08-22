#!/usr/bin/env bash
# setup.sh の統合テスト（実害の再発防止）
#
# 実害事例:
#   1) Windows のバックスラッシュ付き絶対パス (例: C:\Users\...) を
#      「プロジェクトの絶対パス」に入力すると、区切りが消失し全 Hook が
#      動作不能になった。原因は複数重なっていた:
#        - read -p (-r なし) がバックスラッシュをエスケープ文字として
#          解釈し、入力の時点で消える
#        - sed の s/// も置換テキスト側でバックスラッシュを解釈する
#      さらに settings.json は JSON なので、値中の \ をそのまま
#      埋め込むと不正な JSON になる問題もあった。
#   2) 矢印キー入力がエスケープシーケンスとしてそのまま文字列に混入し、
#      生成ファイルが破損した。
#
# このテストは、Windows 風バックスラッシュパスを PROJECT_DIR に与えて
# setup.sh を非対話実行し、生成された .claude/settings.json が
#   - 妥当な JSON としてパースできる
#   - デコード後、元のパスが区切りを保ったまま含まれている
# ことを検証する。
#
# 使い方: bash scripts/test-setup-backslash-path.sh

set -u

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

# setup.sh はメモリシードを $HOME/.claude (または $APPDATA/claude) 配下に
# 書き込むため、実行環境の実際の HOME を汚染しないよう隔離する
TARGET_DIR="$WORK_DIR/target"
mkdir -p "$TARGET_DIR" "$WORK_DIR/home" "$WORK_DIR/appdata"

FAKE_PROJECT_DIR='C:\Users\teppe\OneDrive\PersonalFolder\GitHubRepository_teppei19980914\CreateMinutes'

FAIL=0

cd "$TARGET_DIR" || exit 1

# setup.sh の read_clean 呼び出し順に合わせて応答を流し込む
# (プロジェクト名 / 技術スタック / テスト / 解析 / ビルド / フォーマット /
#  絶対パス / ラベル / 定数 / utils / components / 命名規則 /
#  Git自動化(n) / 確認(y))
HOME="$WORK_DIR/home" APPDATA="$WORK_DIR/appdata" bash "$REPO_ROOT/setup.sh" <<INPUTS > "$WORK_DIR/setup.log" 2>&1
テストプロジェクト
Flutter / Dart
flutter test
flutter analyze
flutter build web
dart format --fix
$FAKE_PROJECT_DIR
src/labels.js
src/constants.js
src/utils/
src/components/
PascalCase / camelCase / kebab-case
n
y
INPUTS
SETUP_EXIT=$?

if [ "$SETUP_EXIT" -ne 0 ]; then
  echo "[NG] setup.sh が異常終了しました (exit=$SETUP_EXIT)"
  cat "$WORK_DIR/setup.log"
  exit 1
fi

SETTINGS_JSON="$TARGET_DIR/.claude/settings.json"
if [ ! -f "$SETTINGS_JSON" ]; then
  echo "[NG] settings.json が生成されていません"
  exit 1
fi

# 未置換プレースホルダーが残っていないか
if grep -rlE '\{\{[A-Z_]+\}\}' "$TARGET_DIR/.claude" "$TARGET_DIR/CLAUDE.md" >/dev/null 2>&1; then
  echo "[NG] 未置換のプレースホルダーが残っています"
  FAIL=1
else
  echo "[OK] プレースホルダーはすべて置換されています"
fi

# settings.json が妥当な JSON であり、デコード後に元のパスが
# 区切りを保ったまま含まれているかを検証する
if command -v python3 >/dev/null 2>&1; then
  if python3 - "$SETTINGS_JSON" "$FAKE_PROJECT_DIR" <<'PY'
import json, sys
path, target = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as f:
    data = json.load(f)

found = False
def walk(o):
    global found
    if isinstance(o, str):
        if target in o:
            found = True
    elif isinstance(o, dict):
        for v in o.values():
            walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)
walk(data)
sys.exit(0 if found else 1)
PY
  then
    echo "[OK] settings.json は妥当な JSON で、パスの区切りが保たれています"
  else
    echo "[NG] settings.json が不正、またはパスの区切りが失われています"
    FAIL=1
  fi
else
  echo "[!] python3 が見つからないため JSON 妥当性検証をスキップします"
  # python3 がなくても、区切り消失の典型的な失敗パターン（バックスラッシュが
  # 全て消えて連結された文字列）が含まれていないかだけは grep で確認する
  if grep -q 'UsersteppeOneDrive' "$SETTINGS_JSON"; then
    echo "[NG] パスの区切りが失われた痕跡(Usersteppe...の連結)を検出しました"
    FAIL=1
  else
    echo "[OK] パス区切り消失の痕跡は見つかりませんでした（簡易チェック）"
  fi
fi

if [ "$FAIL" -eq 1 ]; then
  echo "=== FAIL ==="
  echo "--- setup.log ---"
  cat "$WORK_DIR/setup.log"
  exit 1
fi

echo "=== PASS ==="
exit 0
