## 10. Claude Code Level 5 テンプレートについて

本リポジトリの Claude Code 運用環境（Level 5: CLAUDE.md + Skills + Hooks + Agents）は、元は [ClaudeCodeTemplate](https://github.com/teppei19980914/GrowthEngine) から導入したものである。新規プロジェクトへの再配布用スクリプト（`setup.sh`）・雛形（`docs/templates/`）・検証スクリプト（`scripts/`）はミチナリでは使用しないため削除済みで、以降は `.claude/` 配下の構成のみをミチナリ本体として保守する。Agent / Skill の一覧・起動条件は [2.3 Agents 実行](#23-agents-実行) / [2.4 Skills 実行](#24-skills-実行) を参照。日次ブランチ自動化（Git 自動化）の詳細は [1. 運用フロー（時間軸）](#1-運用フロー時間軸) を参照。

### 10.1 構成

```
.claude/
├── settings.json      # 許可設定 + Hooks (SessionStart/PreToolUse/PostToolUse/Stop)
├── .git-automation-config    # Git自動化設定
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

### 10.2 各レベルの機能

| Level | 構成 | 機能 | トークン効果 |
|---|---|---|---|
| **2** | CLAUDE.md | ルール自動読み込み | 基準 |
| **3** | + Skills | `/fix-issue` 等でオンデマンド手順注入 | -64% |
| **4** | + Hooks | 自動フォーマット + セッション終了時チェック | -67% |
| **5** | + Agents | セキュリティ/パフォーマンス並行レビュー | **-70%** |

### 10.3 Hooks の動作（多層セキュリティ）

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

### 10.4 CI セキュリティスキャン

`.github/workflows/security.yml.template` を `.yml` にリネームすると以下が有効化される。

- **gitleaks** — 機密情報スキャン
- **npm audit / pip-audit** — 既知脆弱性スキャン
- **Semgrep** — SAST（静的解析）
- **CodeQL** — 高度な SAST

**ローカル（`vuln-scan.sh`）とCIの役割分担**: ローカルはセッション終了ごとに `osv-scanner` で軽量・高速に依存脆弱性のCVSSスコアを確認するための即時フィードバック用（非ブロッキング）。CIの `npm audit`/`pip-audit`/Semgrep/CodeQL はマージ前のより網羅的なゲートとして機能する。両方を維持することで「早く気づく」と「厳密に止める」を両立する。

### 10.5 カスタマイズ

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

### 10.6 元の構成の更新

テンプレート自体（[ClaudeCodeTemplate](https://github.com/teppei19980914/GrowthEngine)）を改善した場合でも、ミチナリへの反映は手動実施とし、自動連携は行わない。`.claude/agents` / `.claude/skills` / `.claude/hooks` にファイルを追加・削除した場合は、README.md のエージェント/スキルの件数表記が実ファイル数とずれていないか手動で確認する。

### 10.7 元プロジェクト

このテンプレートは [GrowthEngine（ユメログ）](https://github.com/teppei19980914/GrowthEngine) の開発運用から抽出された。

