## 2. Claude Code 運用

### 2.1 セッション運用

#### 開始時
- SessionStart Hook (`session-start-git.sh`) が自動実行される
- 作業ブランチの決定（同期）→ push・PR 作成・マージ済みなら削除（既定では裏で非同期、2026-10-07改訂）
- **前日ブランチがまだマージ済みと確認できていない場合は当日ブランチを作らず、前日ブランチ上で作業を継続する**（[3.1 日次ブランチフロー](#31-日次ブランチフロー)）
- 初回のみ `gh auth login` と `touch .claude/.git-automation-setup-done` が必要

#### 中間
- 要件を自然言語で指示
- 新機能・認証系・外部入力を扱う場合は `/threat-model` を先に実行
- 問題修正は `/fix-issue` を使用（6 agents が自動並列レビュー）

#### 終了時
- Stop Hook が以下を順次実行:
  1. `secret-scan.sh` — 機密情報スキャン
  2. 静的解析 + テスト
  3. `auto-commit.sh` — テスト成功時のみ自動 commit & push
  4. AI 最終チェック（5 観点）

### 2.2 自動化 Hook の動作確認

定期的に Hook が機能しているか確認する:

```bash
# ログを確認（直近セッションの Hook 出力）
# Claude Code のセッションログに "[git-automation]" や "Auto Commit" が出ているか

# 設定ファイル確認
cat .claude/.git-automation-config
cat .claude/settings.json | grep -A 2 '"type"'

# Hook スクリプトに実行権限があるか
ls -la .claude/hooks/
```

### 2.3 Agents 実行

| 状況 | 起動する Agent | 起動方法 |
|---|---|---|
| 認証機能追加時 | auth-reviewer | `/fix-issue` で自動 or 直接起動 |
| DB/外部API 操作追加時 | injection-reviewer | `/fix-issue` で自動 |
| フロント変更時 | xss-reviewer | `/fix-issue` で自動 |
| 環境変数追加時 | secret-reviewer | `/fix-issue` で自動 |
| 新規依存追加時 | dependency-reviewer | `/fix-issue` で自動 or `週次運用` で定期 |
| パフォーマンス懸念時 | performance-reviewer | `/fix-issue` で自動 |
| 文言変更時 | label-checker | `/fix-issue` で自動 or 明示起動 |
| ロジック変更・共通化の要否判断時 | dry-reviewer | `/fix-issue` で自動 |
| 命名/コメント規約の確認時 | style-reviewer | `/fix-issue` で自動 |
| ロジック追加・変更時 | test-coverage-reviewer | `/fix-issue` で自動 |

### 2.4 Skills 実行

| コマンド | 用途 | 頻度 |
|---|---|---|
| `/fix-issue` | バグ修正・機能追加 | 日常的 |
| `/threat-model` | 新機能の脅威分析 | 機能着手前 |
| `/release` | リリース作業 | リリース時 |
| `/check-deploy` | デプロイ失敗調査 | CI 失敗時 |
| `/update-labels` | 文言変更の横展開 | 必要時 |

---

