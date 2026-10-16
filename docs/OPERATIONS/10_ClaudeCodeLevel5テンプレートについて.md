## 10. Claude Code Level 5 テンプレートについて

本リポジトリは [ClaudeCodeTemplate](https://github.com/teppei19980914/GrowthEngine) から Claude Code の運用環境（Level 5）を導入している。`setup.sh` / `scripts/` は環境の再セットアップ・検証用に残しているツール類であり、ミチナリ本体の実装には含まれない。Agent / Skill の一覧・起動条件は [2.3 Agents 実行](#23-agents-実行) / [2.4 Skills 実行](#24-skills-実行) を参照。日次ブランチ自動化（Git 自動化）の詳細は [1. 運用フロー（時間軸）](#1-運用フロー時間軸) を参照。

### 10.1 テンプレートの内容

```
ClaudeCodeTemplate/
├── README.md              # 本ファイル（運用手順）
├── setup.sh               # 対話式セットアップスクリプト
├── CLAUDE.md               # プロジェクトルール（テンプレート）
├── docs/templates/        # ドキュメント雛形（DESIGN/REQUIREMENTS/OPERATIONS/CODING_RULES/SPECIFICATION）
├── .github/workflows/
│   └── security.yml.template  # CI セキュリティスキャン雛形
└── .claude/
    ├── settings.json      # 許可設定 + Hooks (SessionStart/PreToolUse/PostToolUse/Stop)
    ├── .git-automation-config    # Git自動化設定（オプトイン時に生成）
    ├── memory-seed/             # 新プロジェクトに展開するメモリ（ユーザー情報・横断フィードバック）
    ├── hooks/
    │   ├── session-start-git.sh         # SessionStart: 日次ブランチ自動化
    │   ├── session-start-tools-check.sh # SessionStart: セキュリティツール導入状況を可視化
    │   ├── block-dangerous-edit.sh      # PreToolUse: 危険API/機密ファイルをブロック
    │   ├── secret-scan.sh               # Stop: 機密情報スキャン
    │   ├── vuln-scan.sh                 # Stop: 依存関係の既知脆弱性をOSVでスコアリング（非ブロッキング）
    │   └── auto-commit.sh               # Stop: テスト成功時に自動コミット&プッシュ
    ├── skills/
    │   ├── fix-issue.md     # 問題修正 + 並列セキュリティレビュー（/fix-issue）
    │   ├── threat-model.md  # STRIDE 脅威モデリング（/threat-model）
    │   ├── release.md       # リリース作業（/release）
    │   ├── check-deploy.md  # デプロイ確認（/check-deploy）
    │   └── update-labels.md # ラベル更新（/update-labels）
    └── agents/
        ├── auth-reviewer.md       # 認証/認可/IDOR
        ├── injection-reviewer.md  # SQL/コマンド/SSRF/Path
        ├── xss-reviewer.md        # XSS/CSP/CSRF
        ├── secret-reviewer.md     # 機密情報/ログ漏洩
        ├── dependency-reviewer.md # 既知脆弱性/サプライチェーン
        ├── performance-reviewer.md # パフォーマンス
        ├── label-checker.md        # ハードコード文字列検出
        ├── dry-reviewer.md         # 重複コード/重複定数・ID（DRY原則）
        ├── style-reviewer.md       # 命名規則/コメント規約
        └── test-coverage-reviewer.md # テストカバレッジ
```

### 10.2 新規プロジェクトへのセットアップ手順

#### 方法1: スクリプトで自動セットアップ（推奨）

```bash
# 1. 新しいリポジトリに移動
cd /path/to/new-repo

# 2. セットアップスクリプトを実行
bash /path/to/ClaudeCodeTemplate/setup.sh
```

対話形式でプロジェクト情報を入力すると、テンプレートがコピーされプレースホルダが自動置換されます。

> **Windows (PowerShell) の注意点**: PowerShell 上で単に `bash setup.sh` と実行すると、
> `bash` コマンドが Git Bash ではなく WSL の中継スタブ (`C:\Windows\System32\bash.exe`) に解決され、
> `execvpe(/bin/bash) failed: No such file or directory` のようなエラーになることがあります
> （WSL に通常の Linux ディストリビューションが入っていない場合など）。
> その場合は Git Bash のフルパスを明示して実行してください。
>
> ```powershell
> & "C:\Program Files\Git\bin\bash.exe" /path/to/ClaudeCodeTemplate/setup.sh
> ```

```
=== Claude Code Level 5 セットアップ ===
プロジェクト名 (例: ユメログ): MyProject
技術スタック (例: Flutter / Dart): Python / FastAPI
テストコマンド (例: flutter test): pytest
静的解析コマンド (例: flutter analyze): ruff check .
ビルドコマンド (例: flutter build web): docker build .
フォーマットコマンド (例: dart format --fix): ruff format
プロジェクトの絶対パス: /path/to/MyProject
```

#### 方法2: 手動コピー

```bash
# 1. ファイルをコピー
cp -r /path/to/ClaudeCodeTemplate/.claude /path/to/new-repo/
cp /path/to/ClaudeCodeTemplate/CLAUDE.md /path/to/new-repo/

# 2. プレースホルダを手動で置換（全ファイル内の以下を書き換え）
```

#### プレースホルダ一覧

テンプレート内の `{{...}}` をプロジェクトに合わせて書き換える。

| プレースホルダ | 説明 | Flutter の例 | Python の例 |
|---|---|---|---|
| `{{PROJECT_NAME}}` | プロジェクト名 | ユメログ | MyAPI |
| `{{TECH_STACK}}` | 技術スタック | Flutter / Dart | Python / FastAPI |
| `{{TEST_COMMAND}}` | テスト実行 | `flutter test` | `pytest` |
| `{{ANALYZE_COMMAND}}` | 静的解析 | `flutter analyze` | `ruff check .` |
| `{{BUILD_COMMAND}}` | ビルド | `flutter build web` | `docker build .` |
| `{{FORMAT_COMMAND}}` | フォーマット | `dart format --fix` | `ruff format` |
| `{{PROJECT_DIR}}` | 絶対パス | `c:\Users\...\GrowthEngine` | `/home/user/myapi` |
| `{{LABEL_FILE_PATH}}` | ラベル/文言の定義ファイル | `lib/labels.dart` | `src/labels.py` |
| `{{CONSTANTS_FILE_PATH}}` | 画面ID・定数の定義ファイル | `lib/screens.dart` | `src/constants.py` |
| `{{UTILS_DIR}}` | 共通処理ディレクトリ | `lib/utils/` | `src/utils/` |
| `{{COMPONENTS_DIR}}` | 共通コンポーネントディレクトリ | `lib/widgets/` | `src/components/` |
| `{{NAMING_CONVENTION_SUMMARY}}` | 命名規則の要約 | `Widget:PascalCase / 変数:camelCase` | `関数/変数:snake_case / クラス:PascalCase` |

セットアップ後、新しいリポジトリには以下が作成される（テンプレート自体はコピーされない）。

```
new-repo/
├── CLAUDE.md              # プロジェクトルール（毎セッション自動読み込み）
├── CODING_RULES.md        # コーディングルール（DRY/ゼロハードコーディング等の詳細）
├── SPECIFICATION.md       # 機能仕様（コード内コメントから #N で参照）
├── DESIGN.md / REQUIREMENTS.md / OPERATIONS.md
└── .claude/
    ├── settings.json      # 許可設定 + Hooks
    ├── skills/            # スキル（5ファイル）
    └── agents/            # エージェント（10ファイル）
```

### 10.3 各レベルの機能

| Level | 構成 | 機能 | トークン効果 |
|---|---|---|---|
| **2** | CLAUDE.md | ルール自動読み込み | 基準 |
| **3** | + Skills | `/fix-issue` 等でオンデマンド手順注入 | -64% |
| **4** | + Hooks | 自動フォーマット + セッション終了時チェック | -67% |
| **5** | + Agents | セキュリティ/パフォーマンス並行レビュー | **-70%** |

### 10.4 Hooks の動作（多層セキュリティ）

Hook（正規表現による即時ブロック）と Agent（文脈を読む事後レビュー）は役割が異なるため、意図的に両方を残している。Hookは検知範囲が狭い代わりに編集の瞬間に無条件で止められ、Agentは検知範囲が広い代わりに実行コストがかかる。パターンを増やす場合は、まず `block-dangerous-edit.sh`（高確度な一部パターンのみ）に追加すべきか、`injection-reviewer` 等のAgent側の観点で十分かを先に判断する。

**PreToolUse（ファイル編集前）**

`block-dangerous-edit.sh` が以下をブロックする。

- 危険API: `eval` / `new Function` / `innerHTML` / `dangerouslySetInnerHTML` / `document.write` / 動的 `exec`
- 機密ファイル: `.env` / `*.pem` / `*.key` / `credentials.json` / `id_rsa`
- SQL 文字列連結

**PostToolUse（ファイル編集ごと）**

ファイル編集後に自動フォーマットを実行する。

**SessionStart（セッション開始時）**

- Git 自動化が有効な場合、`session-start-git.sh` が日次ブランチ運用を実行する（詳細は「1. 運用フロー（時間軸）」を参照）
- `session-start-tools-check.sh` が常時実行され、`gitleaks` / `osv-scanner` / CI(`security.yml`) の導入・有効化状況を毎回表示する（未導入でもブロックしない。`secret-scan.sh`/`vuln-scan.sh`はopt-inで無音スキップするため、導入し忘れに気づけるようにするための可視化用Hook）

**Stop（セッション終了時）**

以下が順番に自動実行される。

1. **機密情報スキャン** — `secret-scan.sh`（gitleaks 優先、フォールバックで grep）
2. **静的解析** — 静的解析コマンドを実行
3. **テスト** — テストコマンドを実行
4. **依存脆弱性スキャン** — `vuln-scan.sh`（osv-scanner導入時のみ。OSVデータベースとCVSSスコアを表示、非ブロッキング）
5. **自動コミット** — `auto-commit.sh`（Git 自動化有効時のみ、1-3 成功時のみ）
6. **AIチェック** — 横展開/コーディングルール/セキュリティ/パフォーマンス/テスト整合性/ドキュメント更新を確認

### 10.5 ドキュメント雛形

`docs/templates/` にセキュリティ要件・コーディングルールを含んだ雛形を同梱している。

- `DESIGN.template.md` — 信頼境界・STRIDE 脅威表・受容リスクのセクション付き
- `REQUIREMENTS.template.md` — 認証/認可/データ保護/コンプライアンス要件
- `OPERATIONS.template.md` — セキュリティ監視・インシデント対応・シークレットローテーション
- `CODING_RULES.template.md` — DRY/ゼロハードコーディング/置き場所ルール/命名規則/コメント規約/テストカバレッジ/保守性（複雑度）
- `SPECIFICATION.template.md` — 機能仕様の通し番号一覧。コード内コメントの「仕様書 #N」参照先

### 10.6 CI セキュリティスキャン

`.github/workflows/security.yml.template` を `.yml` にリネームすると以下が有効化される。

- **gitleaks** — 機密情報スキャン
- **npm audit / pip-audit** — 既知脆弱性スキャン
- **Semgrep** — SAST（静的解析）
- **CodeQL** — 高度な SAST

**ローカル（`vuln-scan.sh`）とCIの役割分担**: ローカルはセッション終了ごとに `osv-scanner` で軽量・高速に依存脆弱性のCVSSスコアを確認するための即時フィードバック用（非ブロッキング）。CIの `npm audit`/`pip-audit`/Semgrep/CodeQL はマージ前のより網羅的なゲートとして機能する。両方を維持することで「早く気づく」と「厳密に止める」を両立する。

### 10.7 カスタマイズ

**スキルの追加**: `.claude/skills/` に新しい `.md` ファイルを作成する。

```markdown
---
name: my-skill
description: スキルの説明
---

# スキル名

## 手順
1. ...
```

**エージェントの追加**: `.claude/agents/` に新しい `.md` ファイルを作成する。

```markdown
---
name: my-agent
description: エージェントの説明
tools:
  - Read
  - Grep
  - Bash
---

# エージェント名

## チェック項目
1. ...
```

**Hook の追加**: `.claude/settings.json` の `hooks` セクションに追記する。

### 10.8 テンプレートの更新

テンプレート自体を改善した場合は、[ClaudeCodeTemplate](https://github.com/teppei19980914/GrowthEngine) リポジトリを更新する。既存プロジェクト（本リポジトリ含む）への反映は各プロジェクト側で手動実施する。

`.claude/agents` / `.claude/skills` / `.claude/hooks` にファイルを追加・削除した場合は、コミット前に以下を実行し、README.md / setup.sh の件数表記が実ファイル数とずれていないか機械的に検証する（LLMのgrep確認だけに頼らないため）。

```bash
bash scripts/verify-template.sh
```

### 10.9 元プロジェクト

このテンプレートは [GrowthEngine（ユメログ）](https://github.com/teppei19980914/GrowthEngine) の開発運用から抽出された。

