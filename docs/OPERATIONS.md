# OPERATIONS.md — 運用手順書

本ドキュメントは運用に関わる全領域を **MECE（漏れなく・ダブりなく）** で整理したものです。
各セクションは独立しており、該当する状況のセクションのみを参照すれば対応できます。

---

## 目次

| # | セクション | 対応する状況 |
|---|---|---|
| 1 | [運用フロー（時間軸）](#1-運用フロー時間軸) | 日常の定期作業 |
| 2 | [Claude Code 運用](#2-claude-code-運用) | AI 駆動開発の運用 |
| 3 | [Git / ブランチ運用](#3-git--ブランチ運用) | コード管理・PR・マージ |
| 4 | [監視](#4-監視) | 常時監視・アラート |
| 5 | [セキュリティインシデント対応](#5-セキュリティインシデント対応) | セキュリティ事故発生時 |
| 6 | [バックアップ・リストア](#6-バックアップリストア) | データ保護・復旧 |
| 7 | [デプロイ](#7-デプロイ) | 本番反映 |
| 8 | [トラブルシューティング](#8-トラブルシューティング) | 自動化やツール不具合時 |
| 9 | [連絡先・エスカレーション](#9-連絡先エスカレーション) | 通報・エスカレーション |
| 10 | [Claude Code Level 5 テンプレートについて](#10-claude-code-level-5-テンプレートについて) | テンプレートの導入・カスタマイズ |

---

## 1. 運用フロー（時間軸）

### 1.1 日次運用

| 時間帯 | 担当 | 作業 |
|---|---|---|
| 朝 | 開発者 | Claude Code セッションを起動（SessionStart Hook が自動実行） |
| 朝 | 開発者 | 前日 PR を GitHub でレビュー＆マージ |
| 日中 | Claude Code | 要件取り込み・テスト追加・自動コミット |
| 夕 | Claude Code | Stop Hook で secret-scan → 静的解析 → テスト → auto-commit & push |
| 夜 | 監視システム | エラー率・レスポンスタイム・セキュリティイベントの自動確認 |

**開発者が意識すべき日次作業は 2 つのみ:**
1. 朝の Claude Code 起動
2. PR のレビュー＆マージ

### 1.2 週次運用

- [ ] 依存パッケージの更新確認（`npm outdated` / `pip list --outdated`）
- [ ] `dependency-reviewer` agent による脆弱性チェック（`vuln-scan.sh` の日次スキャン結果を一次情報として活用）
- [ ] `vuln-scan.sh` でCRITICAL/HIGHが継続検出されていないか週次でまとめて確認（日次は非ブロッキングのため見逃しやすい）
- [ ] CI の週間サマリー確認（失敗率、カバレッジ推移）
- [ ] `OPERATIONS.md` の監視アラートログ確認
- [ ] 未マージのまま残っている古い PR の棚卸し

### 1.3 月次運用

- [ ] セキュリティログのアーカイブ
- [ ] 使用していないブランチの清掃（自動化対象外の古いブランチ）
- [ ] パフォーマンスメトリクスのレビュー（SLA 達成状況）
- [ ] バックアップからのリストア訓練（小規模）
- [ ] `REQUIREMENTS.md` / `DESIGN.md` の陳腐化チェック

### 1.4 四半期運用

- [ ] セキュリティ設計レビュー（全 `/threat-model` 結果の棚卸し）
- [ ] ペネトレーションテスト実施（必要に応じて外部委託）
- [ ] インシデント対応訓練（シークレットローテーション訓練）
- [ ] バックアップからの完全リストア訓練
- [ ] CLAUDE.md / Skills / Agents / Hooks の見直し
- [ ] 受容したセキュリティリスクの再評価（`DESIGN.md`）

---

## 2. Claude Code 運用

### 2.1 セッション運用

#### 開始時
- SessionStart Hook (`session-start-git.sh`) が自動実行される
- 前日ブランチの処理 → PR 作成 → マージ済みなら削除 → 作業ブランチの決定
- **前日ブランチが未マージの場合は当日ブランチを作らず、前日ブランチ上で作業を継続する**（[3.1 日次ブランチフロー](#31-日次ブランチフロー)）
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

## 3. Git / ブランチ運用

### 3.1 日次ブランチフロー

```
main
 │
 ├─ dev/2026-04-09 (前日)  ──► PR #123 ──► マージ後削除
 ├─ dev/2026-04-10 (当日)  ──► Stop Hook で auto-commit
 └─ dev/2026-04-11 (翌日)  ──► SessionStart で自動作成（前日がマージ済みの場合のみ）
```

**ルール**:
- 1日1ブランチが原則。ブランチ名は `dev/YYYY-MM-DD` 固定
- **例外: 前日ブランチが `main` へ未マージなら「作業中」と判断し、当日ブランチを作らず前日ブランチで作業を継続する**
- 同一日に複数回セッションを開始しても既存ブランチを継続使用
- `main` / `master` / `develop` / `release/*` / `hotfix/*` への直接コミットは auto-commit が拒否

**作業ブランチの決定順序**（`session-start-git.sh` Step 3）:

| 順 | 条件 | 動作 |
|---|---|---|
| 1 | 当日ブランチが既に存在 | チェックアウトのみ |
| 2 | 未マージの前日ブランチがある | 当日ブランチを作らず、その前日ブランチをチェックアウト |
| 3 | 前日ブランチが全てマージ済み（または無い） | `main` を `origin/main` へ fast-forward してから当日ブランチを作成 |
| 4 | `main` が `origin/main` へ fast-forward 不可（分岐） | 当日ブランチの作成を中止し、手動での最新化を促す |

順2・順4は、未マージのまま `main` から当日ブランチを切って前日の成果が作業ツリーから消える事故（2026-09-10・09-11に発生）の再発防止。順4で中止された場合は、手動で `main` を最新化してからセッションを開き直す。

**日付ごとにブランチを分けたい場合**は、その日のうちに PR をマージする。マージしないまま日付が変わると順2が適用され、前日ブランチでの作業が続く。

### 3.2 PR 運用

| アクション | 実行者 | タイミング |
|---|---|---|
| PR 作成 | Claude Code（自動） | 翌朝の SessionStart 時 |
| PR タイトル | 自動生成（`dev/YYYY-MM-DD: 日次変更`） | 作成時 |
| PR 本文 | 自動生成（`git log main..HEAD --oneline`） | 作成時 |
| PR レビュー | 開発者 | 作成後すみやかに |
| PR マージ | 開発者（手動）または Claude Code（依頼時に `gh pr merge`） | レビュー完了後 |
| ブランチ削除 | Claude Code（自動） | マージ後の翌朝 |

PRのマージはClaude Codeに依頼してもよい（`gh pr merge`）。ただしHookによる無人自動
マージは行わない（レビュー完了の判断は開発者が行い、その指示を受けてClaude Codeが
実行する、という分担にする）。`main`等の保護ブランチへの**直接コミット**の禁止
（`auto-commit.sh`）はこれとは別の防御であり、引き続き有効である。

### 3.3 マージ戦略

- **通常マージ**: squash and merge 推奨（日次1PRを1コミットに圧縮）
- **リリース**: GitFlow 等を採用する場合は `release/*` ブランチで運用（自動化対象外）

### 3.4 緊急対応

#### 当日分を急ぎマージしたい
1. セッション終了（Stop Hook で自動コミット＆プッシュ）
2. 手動で `gh pr create` を実行（SessionStart を待たない）
3. `gh pr merge` でマージする（開発者が実行してもClaude Codeに依頼してもよい）

#### 保護ブランチ（main等）に誤コミットしてしまった
1. `git log` で誤コミットを特定
2. `git revert <commit>` で取り消し（`reset --hard` は禁止）
3. 原因調査: なぜ auto-commit.sh の保護が効かなかったか

#### 未マージブランチを手動削除したい
```bash
# PR を先にクローズ
gh pr close <PR番号>
# ローカル削除
git branch -D dev/YYYY-MM-DD
# リモート削除
git push origin --delete dev/YYYY-MM-DD
```

---

## 4. 監視

### 4.1 アプリケーション監視

| 項目 | しきい値（例） | 監視ツール |
|---|---|---|
| 稼働状況 | ダウン時即時 | <!-- 例: Datadog --> |
| エラー率 | 1% 超で警告 / 5% 超でクリティカル | |
| レスポンスタイム（p95） | 1秒 超で警告 | |
| CPU 使用率 | 80% 超で警告 | |
| メモリ使用率 | 85% 超で警告 | |
| ディスク使用率 | 80% 超で警告 | |

### 4.2 セキュリティ監視

| 項目 | しきい値（例） | 検知手段 |
|---|---|---|
| 認証失敗の急増 | 10分で100件 超 | アプリログ + SIEM |
| 権限エラーの急増 | 10分で50件 超 | アプリログ |
| 異常なデータアクセス | 通常の10倍 超 | DB 監査ログ |
| 不審 IP からのアクセス | Threat Intel ヒット | WAF |
| WAF/IDS アラート | High 以上 | WAF |
| 新規 CVE 該当依存 | 即時 | Dependabot + dependency-reviewer |

### 4.3 CI/CD 監視

| 項目 | 確認頻度 |
|---|---|
| Security Scan ワークフロー結果 | 毎実行 |
| gitleaks 検出 | 即時通知 |
| npm audit / pip-audit 結果 | 毎実行 |
| Semgrep / CodeQL 結果 | 毎実行 |
| ビルド成功率 | 週次サマリー |

### 4.4 アラート通知先

| 重大度 | 通知先 | 応答時間 |
|---|---|---|
| CRITICAL | オンコール呼び出し | 15分以内 |
| HIGH | <!-- Slack #alerts-high --> | 1時間以内 |
| MEDIUM | <!-- Slack #alerts-medium --> | 翌営業日 |
| LOW | ダッシュボード | 週次レビュー |

---

## 5. セキュリティインシデント対応

### 5.1 初動フロー

```
検知 → トリアージ → 封じ込め → 根絶 → 復旧 → 事後分析
```

### 5.2 重大度分類

| レベル | 定義 | 対応時間 |
|---|---|---|
| **SEV-1** | 機密情報漏洩、全ユーザー影響 | 即時エスカレーション、24時間対応 |
| **SEV-2** | 一部ユーザー影響、攻撃進行中 | 4時間以内着手 |
| **SEV-3** | 潜在的脆弱性、未悪用 | 翌営業日 |

### 5.3 シークレットローテーション手順

#### AWS アクセスキー
```bash
aws iam create-access-key --user-name <user>
# 新キーをデプロイ後
aws iam update-access-key --access-key-id <OLD> --status Inactive
# 動作確認後
aws iam delete-access-key --access-key-id <OLD>
```

#### JWT 署名鍵
1. 新しい鍵ペアを生成
2. 新旧両方で検証を受け付ける grace period を設定
3. 全トークンの有効期限経過後、旧鍵を削除

#### データベースパスワード
1. 新パスワードを Secrets Manager に登録
2. アプリケーションを順次再起動
3. DB 側で旧パスワードを無効化

#### API トークン（GitHub / Slack 等）
1. 該当サービスで新トークンを発行
2. 環境変数 / Secrets を更新
3. 旧トークンを失効

### 5.4 漏洩発覚時のチェックリスト

- [ ] 漏洩したシークレットの範囲を特定
- [ ] git 履歴から完全削除（`git filter-repo` / BFG Repo Cleaner）
- [ ] 漏洩期間中のアクセスログを調査
- [ ] 影響を受けたユーザー / データを特定
- [ ] 関係者への報告（法務・経営）
- [ ] 監督当局への報告要否判断（GDPR: 72時間以内）
- [ ] 影響ユーザーへの通知
- [ ] 事後分析レポート作成（ポストモーテム）

### 5.5 事後分析（ポストモーテム）

インシデント終息後、以下を含むレポートを作成:
- 時系列
- 根本原因（5 Whys）
- 影響範囲（ユーザー数・データ量）
- 対応内容
- 再発防止策（Hook / Agent / Skill の追加・改善）
- 検知ラグ短縮策

---

## 6. バックアップ・リストア

### 6.1 バックアップ対象

| データ種別 | 頻度 | 保管場所 | 保持期間 |
|---|---|---|---|
| データベース | <!-- 例: 日次 --> | <!-- 例: S3 --> | <!-- 例: 30日 --> |
| ユーザーアップロード | | | |
| 設定ファイル | | | |
| シークレット | | Vault / KMS | 無期限 |
| ログ | <!-- 例: 日次 --> | | <!-- 例: 1年 --> |

### 6.2 リストア手順

```bash
# 1. バックアップの整合性確認
# 2. ステージング環境でリストアテスト
# 3. 本番データベース停止（必要に応じて）
# 4. 本番リストア
# 5. 動作確認
# 6. 通常運用再開
```

### 6.3 訓練

- 月次: 小規模リストア訓練（1テーブル単位）
- 四半期: 完全リストア訓練
- 訓練記録を残し、所要時間を測定

---

## 7. デプロイ

### 7.1 通常デプロイ

1. PR が main にマージされる
2. CI がテスト + セキュリティスキャンを実行
3. 成功時、自動で本番デプロイ（または手動承認後）
4. デプロイ後のスモークテスト
5. 監視アラートが静まっていることを確認

### 7.2 ロールバック

```bash
# 直前のバージョンに戻す
# 例: Vercel
vercel rollback
# 例: AWS ECS
aws ecs update-service --service <svc> --task-definition <prev>
# 例: Kubernetes
kubectl rollout undo deployment/<name>
```

### 7.3 緊急デプロイ（ホットフィックス）

1. `hotfix/<issue>` ブランチを main から作成
2. 修正＋テスト追加
3. `/fix-issue` で全レビュー実行
4. PR 作成＋緊急承認
5. マージ＆デプロイ
6. 事後に `dev/YYYY-MM-DD` にも取り込む

### 7.4 配布パッケージのビルド（他端末への配布用）

本アプリは個人端末で完結するローカルアプリであるため、7.1〜7.3のサーバーデプロイとは別に、
Windows端末へ配布するための単一実行ファイル化（PyInstaller）を用意している。マージ〜ビルド〜
パッケージ化〜zip化〜GitHub Releasesへの公開までを`scripts/release.py`が一続きで実行する
（後述「配布物の公開方法」）。ビルド時にはバックエンド・フロントエンド双方のテストが
必ず実行され、1件でも失敗すればビルドを中止する。

#### ビルド前の準備（変更内容により手順が異なる）

`build.bat`はテストの実行とパッケージ化のみを行い、マイグレーションファイル自体は
生成しない。**DBスキーマの変更（列の追加/削除・テーブル新規作成等）を伴う修正では、
`build.bat`を実行する前にマイグレーションファイルを作成しておく必要がある。**
配布後の利用者操作（旧パッケージ削除→新パッケージ配置→起動）はどちらのケースでも
同一だが（7.5参照）、開発者がビルド前に行う作業は以下のように異なる。

**ケースA: ソースコードのみの修正（DBスキーマ変更なし）**

1. 通常どおりコード修正・テストを追加する
2. 下記「実行方法」に従い `backend/build.bat` を実行する

**ケースB: DB構造の変更を伴う修正**

1. `backend/app/models/*.py` を変更する
2. マイグレーションファイルを生成する（`backend/alembic/versions/` に追加される）

   ```bash
   cd backend
   uv run alembic revision --autogenerate -m "<変更内容の説明>"
   ```
3. 生成された内容をレビューする。列の追加/削除は autogenerate で検出されるが、
   既存データの値コピー・変換ロジック（例: `9a1c3e7d5b2f_daily_goal_diary.py`）は
   自動生成されないため手動で追記する。`downgrade()` も実装する
4. 既存テーブルへの `add_column` / `alter_column` 等を含む場合、CODING_RULES.md
   「DBマイグレーションのテスト」に従い、既存データに対する安全性検証テストを
   `backend/tests/test_migration.py` 等へ追加する（新規テーブルの `create_table` のみの
   マイグレーションは対象外）
5. `uv run pytest` をローカルで実行し、追加したテストを含め全て通ることを確認する
6. 下記「実行方法」に従い `backend/build.bat` を実行する（ビルド内でも同じテストが
   再実行されるため、手順5は失敗時の原因切り分けを早めるための事前確認）

上記いずれのケースも、ビルド後に生成される配布物・配布先での更新手順自体に違いはない。
DBスキーマ変更を配布した場合の配布先での自動適用の仕組みは7.5を参照。

**実行方法**（いずれか）

- `backend/build.bat` をダブルクリックする（コマンド操作に慣れていない開発者向けの
  GUI実行手段。完了・失敗のいずれでもウィンドウが自動で閉じないよう `pause` している）
- または、コマンドラインから以下を実行する

```bash
cd backend
uv run python scripts/build_package.py
```

`backend/build.bat`は本体の処理前に`uv sync`を実行する。本リポジトリがOneDrive
同期フォルダ内にあるため、同期中のファイルロックと競合し`.venv`配下のファイル削除が
「アクセスが拒否されました」で失敗することがある（後述の`shutil.rmtree`の`WinError 5`と
同種の問題）。`backend/build.bat`はこの`uv sync`失敗を検知すると3秒待って最大5回まで
自動的に再試行する。コマンドラインから直接`uv run python scripts/build_package.py`を
実行して同じ事象に遭遇した場合は、`uv sync`を単独で再実行してから改めて実行する。

同じ再試行は一時的なネットワーク断にも効く。`uv sync`はビルド依存（`hatchling`）の
解決のためPyPIへ問い合わせるため、名前解決に失敗すると
`Failed to fetch: https://pypi.org/simple/hatchling/` / `dns error` /
`そのようなホストは不明です。(os error 11001)` を伴う
`Failed to build michinari-backend` で止まる。**これは`.venv`のロックでもキャッシュの
問題でもなく、単にPyPIへ到達できていない**ため、ネットワーク接続（VPN・プロキシ・
DNS）を確認して再実行する。再試行中に接続が回復すれば`build.bat`はそのまま
ビルドを継続する。

なお、`uv sync`にはこれとは別に**再試行では解消しない**失敗がある。uvはグローバル
キャッシュ（`%LOCALAPPDATA%\uv\cache`）から`.venv`・ビルド環境へ既定でハードリンクを
張るが、キャッシュ配下のファイルがOneDriveのクラウドファイル（リパースポイント）に
なっていると、ハードリンクが`os error 396`（`クラウド操作は、互換性のないハードリンクの
ファイルでは実行できません`）で失敗し、ビルド依存（`hatchling`→`pluggy`）の導入が
できずに`Failed to build michinari-backend`となる。これを避けるため、
`backend/pyproject.toml`の`[tool.uv]`で`link-mode = "copy"`（ハードリンクではなく
コピー）を指定している。それでも`os error 396`が出る場合は`uv cache clean`で
キャッシュを作り直してから再実行する。

**処理内容**

1. テストスイート（`pytest`）を実行する。**1件でも失敗すればここでビルドを中止する**
   （配布パッケージに不具合を含んだまま出荷しないための最終防波堤。2026-08-29、
   マイグレーション不具合を検出するテストが存在したにもかかわらずビルド時に実行
   されておらず、そのまま配布されてしまった反省による）
2. 配布バージョンの入力を求める（コンソールにプロンプトが表示される）。空欄のまま
   確定することはできず、入力した値がそのままリリースバージョンとなる（現在の
   `backend/pyproject.toml` のバージョンは参考表示のみで、既定値としての自動採用は
   しない）。使用できる文字は半角英数字・ドット・ハイフン・アンダースコアのみ
   （`pyproject.toml` のTOML文字列・zipファイル名へそのまま埋め込むため、それ以外の
   文字を含む入力は再入力を求める）。確定したバージョンは `backend/pyproject.toml` の
   `version` に反映される（`read_current_version`/`write_version`/`resolve_version`）
3. 既存の `backend/dist/Michinari/` があれば、`backend/dist/_archive/Michinari_YYYYMMDD_HHMMSS/`
   へリネームして退避する（削除しない。旧バージョンとの差分調査用）
4. アプリバージョン・使用ライブラリのスナップショットを `backend/build_info.json` へ生成する
   （`generate_build_info`。2で確定した`backend/pyproject.toml`の`[project].version`を
   単一の情報源として読む）
5. フロントエンドを `npm run build` でビルド（`frontend/dist`）
6. PyInstallerでバックエンド一式をパッケージ化（フロントエンドの静的ファイル・
   `alembic/`・`build_info.json` を同梱、`backend/dist/Michinari/` に出力）
7. 起動用 `Michinari.bat`（`backend/scripts/launcher_template.bat` の複製）と
   ユーザ手順書 `ユーザ手順書.pdf`（`docs/ユーザ手順書.pdf`
   の複製）を `backend/dist/Michinari/` 直下へ配置する（`copy_user_manual`。利用者が
   エクスプローラから直接開けるよう、PyInstallerの `--add-data` によるexe内埋め込みでは
   なくファイルコピーで同梱する。手順書が見つからない場合は警告を表示して同梱のみを
   飛ばし、ビルドは継続する）
8. `backend/dist/Michinari/` フォルダを zip 化し、2で確定したバージョンを名前に含む
   `backend/dist/Michinari-v{version}.zip`（例: `Michinari-v0.2.0.zip`）を生成する
   （`create_distribution_zip`）

`build_info.json`（配布パッケージ同梱後は起動画面「システム情報」SC-15から参照できる、
仕様書6.14参照）は`built_at`がビルドの都度変わるため`.gitignore`で除外している
（`frontend/src/types/api.d.ts`のようにAPIスキーマ変更時のみ変わる決定論的な生成物
（コミット対象）とは性質が異なるため、同じ扱いはしない）。

配布時は `backend/dist/Michinari-v{version}.zip` を配布先へコピーして展開し、
`Michinari.bat` を実行する（zipを展開すると `Michinari/` フォルダが得られるため、
3で述べたフォルダ手動コピーの代わりにzipを渡すだけで済む）。データ保存先は配布先
ごとに `%LOCALAPPDATA%\Michinari\data\` を使う（`backend/app/config.py` の
`_default_data_dir` が `sys.frozen` を判定して自動切替。ソースから起動する開発環境
では従来通り `data/` を使うため挙動に影響しない）。

zip（`backend/dist/Michinari-v{version}.zip`）は3のアーカイブ退避（`_archive/`）とは
対象・実行順序が独立している（zip化はビルド完了後に最新の`Michinari/`のみを対象に行う
ため、退避済みの旧パッケージを巻き込むことはない）。zipファイル名にバージョンが入る
ため、異なるバージョンでビルドすれば過去のzipを上書きせず併存する（同一バージョンで
再ビルドした場合のみ上書きされる）。過去バージョンのzipが不要になれば手動で削除して
よい（`backend/dist/` は `.gitignore` で除外済み）。

退避を削除ではなくリネームにしているのは差分調査を可能にするためだが、副次的に、
OneDriveファイルオンデマンド配下（リポジトリがOneDrive同期フォルダ内にある場合）で
既存出力先を`shutil.rmtree`により再帰削除しようとして`WinError 5 アクセスが拒否
されました`になる事象も回避できる（リネームはディレクトリエントリの付け替えのみで
再帰削除を伴わないため）。`backend/dist/_archive/` は自動生成物のため不要になったら
手動で削除してよい（`.gitignore`で`backend/dist/`ごと除外済み）。

#### 配布物の公開方法（GitHub Releases）

`backend/dist/` はビルドのたびに数十〜100MB超が再生成され、かつ`_archive/`に旧版も
残り続けるため、リポジトリ本体には含めない（`.gitignore`で除外を維持）。配布は
GitHub Releasesにzipを添付する方式で行う。

**推奨: `release.bat` をダブルクリックする**（下書きリリースまでを自動で用意する）。

リリースノートを先に書く必要はない。テストを通してからバージョンを尋ね、パッケージ・
タグ・zip添付まで済ませた**下書き**リリースを作る。人の作業は「GitHubの画面で本文を
書き換えて公開する」1点だけになる。

```
1. 開発（dev/YYYY-MM-DD）
2. main へマージする（GitHub 上で PR をマージする）
3. backend/release.bat を実行する   ← ここから下書き作成まで全て自動
4. GitHub Releases の下書きを開き、本文のひな形をリリースノートへ書き換える
5. 「Publish release」を押す（配布開始）
```

**手順3でバッチが行うこと**

| 順 | 内容 |
| --- | --- |
| 1 | 未コミットの変更が無いことを確認する（あれば中止） |
| 2 | `origin` を取得し、**`main` への切り替えと最新化を自動で行う**（ローカルが dev ブランチのままでよい） |
| 3 | テスト（バックエンド `pytest` ＋ フロントエンド `tsc -b` / `npm test`）を実行する。1件でも失敗すれば中止 |
| 4 | コンソールでバージョンを尋ねる（`N.N.N` 形式。テストが通った後にのみ表示される） |
| 5 | パッケージをビルドし zip 化する |
| 6 | ビルド元コミットへタグを付けて push する |
| 7 | zip を添付した**下書き**リリースを作成する（本文は記入用のひな形） |
| 8 | リモートのタグ実体がビルド元コミットを指しているか検証する |
| 9 | 次に何をすればよいか（手順4・5）をコンソールに表示する |

手順2でマージし忘れたまま実行した場合は、`main` へ切り替えずに中止する。切り替えてしまうと
**変更を含まないパッケージを配布する**ことになるため、作業内容が `origin/main` に取り込まれて
いるかをツリーの比較で確認している（PR を squash マージするとコミットは `main` の祖先に
ならないため、祖先関係では判定できない）。

**なぜ下書きにするか**: 本文が未記載のリリースが一般公開されるのを防ぐため。タグとzipは
下書きの時点で作成・添付済みのため、本文を書き換えて公開ボタンを押すだけで配布できる。
下書きは作成者にしか見えないため、放置すると配布されないまま忘れられる点に注意する
（実行後のコンソールに次の操作を表示している）。

**バージョンを指定して一続きに実行する**（従来どおり。詳細リリースノートを先に用意する）:

```bash
cd backend
uv run python scripts/release.py 1.2.2     # バージョンを引数で渡す（対話入力なし）
uv run python scripts/release.py 1.2.2 --skip-merge   # 既に main へマージ済みの場合
uv run python scripts/release.py --skip-merge --draft # release.bat と同じ（バージョンは対話入力）
```

**リリースノートの2層構成との関係**: `docs/release-notes/v{version}.md` が存在する場合は
従来どおりその要約ブロックがRelease本文になり、詳細ノートへのリンクも付く。存在しない
場合は記入用のひな形が本文になる（ファイルが無い状態でリンクすると404になるため、
ひな形にはリンクを載せない）。ノートを先に書く運用と、後から画面で書く運用のどちらも
選べる（切り替えは`publish_release.resolve_release_body`がファイルの有無で自動判定する）。

工程を人が順に叩く運用では、順序違いがそのまま事故になっていた。`release.py` は以下を
まとめて担う。

| 工程 | 内容 |
| --- | --- |
| 事前検証 | バージョン形式（`N.N.N`）・作業ツリーがクリーン・リリースノートと要約ブロックの存在・**タグが未公開であること**。取り返しのつかない操作の前に全て確認する |
| マージ | 現在のブランチを `main` へ squash マージし、`main` を最新化してビルド元コミットを確定する |
| ビルド | `build_package.py` の各工程（テスト → バージョン確定 → ビルド → zip化）をバージョン入力なしで実行 |
| 公開 | `publish_release.py` の `publish` を呼ぶ |
| 公開後検証 | **リモートのタグ実体がビルド元コミットを指しているか**を突き合わせる |

個別に実行する場合（従来どおり）:

```bash
cd backend
uv run python scripts/build_package.py     # バージョンは対話入力
uv run python scripts/publish_release.py
```

`publish_release.py` はバージョンを`pyproject.toml`から自動取得し、`ver{version}`タグ・
`Michinari-v{version}`の表題で `gh release create ... --notes-file` を実行する
（アップロードするzipファイル名も`build_package.py`と同じ`Michinari-v{version}.zip`を使う。
命名規則は`build_package.distribution_zip_filename`に集約し、二重管理しない）。タグ・表題は
公開済みリリース（`ver1.0.0`〜`ver1.2.0`、`Michinari-v1.0.0`〜`Michinari-v1.2.0`）の命名へ
スクリプト側を合わせたものである（タグ名はReleaseページの固定URLに含まれ、READMEや外部からの
参照先になるため、過去タグの付け替えは行わない）。

**タグの作成は `gh` に任せない。** `ensure_release_tag` がビルド元コミットへタグを作成・push
してから、`gh release create --verify-tag`（タグが無ければ中止）で公開する。`--target` を
渡す方式では、**同名のローカルタグが存在すると `gh` がそれを push し、`--target` の指定が
無視される**。2026-09-12 の v1.2.1 公開で、公開前に作られていたローカルタグ（当時の `main`
先端）がそのまま押し出され、タグが配布物と異なるコミットを指す事故が起きた。Release 側の
`target_commitish` には指定値が入るため、Release の情報だけを見ても食い違いに気付けない。
公開済みのタグが別コミットを指している場合は、配布済みの内容を黙って書き換えないよう中止する。同じバージョンで再実行するなど既にタグ・
Releaseが存在する場合は、自動的に `gh release edit ... --notes-file`（本文の差し替え）と
`gh release upload ... --clobber`（zipの差し替え）へフォールバックする。`build_package.py`
からは一切自動呼び出しされない（GitHub上で他者から見える公開操作のため、公開したい
タイミングで開発者が明示的に実行する）。

#### リリースノートの2層構成

**公開前に `docs/release-notes/v{version}.md` を作成しておくこと**（存在しないと
`publish_release.py` はエラー終了する）。Releases一覧ページは各リリースの本文を全文
レンダリングするため、本文が長いと配布zip（Assets）が画面下へ埋もれ、利用者が目的の
バージョンを見つけられなくなる。そこでRelease本文は要約のみとし、全変更点は
`docs/release-notes/` 配下のファイルへ置く。

| 層 | 置き場所 | 分量の目安 |
|---|---|---|
| 要約 | GitHub Release 本文（スクリプトが自動生成） | 15行以内 |
| 詳細 | `docs/release-notes/v{version}.md` | 制限なし |

`publish_release.py` は詳細ノートの `<!-- summary:start -->` 〜 `<!-- summary:end -->` で
囲まれた範囲を抽出し、ダウンロード導線（配布zip名とREADMEへのリンク）と詳細ノートへの
リンクを前後に付けてRelease本文を組み立てる。書き方と追加手順は
[docs/release-notes/README.md](release-notes/README.md) を参照。

詳細ノートへのリンクは**タグではなく`main`**を指す。過去バージョンのタグには当該ファイルが
含まれないうえ、ノートの誤記を後から直した場合にRelease本文からのリンク先へも反映させたい
ためである。したがって**詳細ノートを`main`へマージしてから公開すること**（未マージのまま
公開すると本文のリンクが404になる）。

#### タグは必ずビルド元コミットへ付ける

`gh release create` は `--target` を指定しない場合、タグをリポジトリの既定ブランチ（`main`）
の**その時点の先端**に作成する（GitHub REST API "Create a release" の `target_commitish` の
既定値。https://docs.github.com/en/rest/releases/releases ）。つまりタグの位置は「公開
コマンドを実行した時刻の `main`」だけで決まり、配布物の内容とは無関係になる。

この構造により、2026-09-11 に次の2件が発生した。

| タグ | 誤って指していた先 | 正しい指し先 | 原因 |
|---|---|---|---|
| `ver1.0.0` | `03b5690`（v1.1.0のコミット） | `e71ca078` | ビルド（09-08）から3日後に公開し、その間に`main`がv1.1.0まで進んでいた |
| `ver1.2.0` | `03b5690`（v1.1.0のコミット） | `c582f22` | ビルドの3分後に公開したが、v1.2.0のコードが`main`へ未マージだった |

`ver1.2.0` が示すとおり、**これは公開を急げば防げる問題ではない**。参照先が配布物ではなく
`main` の先端である以上、両者が一致するのは偶然にすぎない。

そこで `build_package.py` はビルド元コミットを `dist/Michinari-v{version}.commit.json`
（`build_commit_filename`）へ記録し、`publish_release.py` はそれを読んで
`gh release create --target <commit>` を実行する。公開前に次を検証し、1つでも満たさない
場合は公開を中止する（`read_build_commit`/`is_merged_into_base`）。

| 検証 | 中止する理由 |
|---|---|
| 記録ファイルが存在する | ビルド元コミットが不明ではタグを正しく付けられない |
| 記録のバージョンが対象と一致する | 別バージョンのビルドを取り違えて公開しないため |
| `dirty` が `false` である | 未コミットの木からのビルドには対応するコミットが存在しない |
| `commit` が `origin/main` へマージ済み | 未マージだとGitHubがタグを作れず、詳細ノートへのリンクも404になる |

`dirty` の判定はバージョン確定（`write_version`）より**前**に行う。本スクリプトはビルドの
過程で `pyproject.toml` のバージョン行を書き換えるため、確定後に判定すると常に「変更あり」
になってしまう。したがって**バージョン更新は事前にコミットしておき、ビルド時のバージョン
入力では同じ値を入力する**（値が変わらなければ書き換えは発生しない）。

なお `--target` はタグが既に存在する場合は無視される（前掲の公式ドキュメント）ため、
再公開時のフォールバック経路（`gh release edit` / `gh release upload`）では指定しない。

配布先には、生成されたReleaseページの固定URLを案内する。ユーザーはそのページから
配布用zip（`Michinari-v{version}.zip`）をダウンロードし、展開して `Michinari.bat` を
実行すればよい。

**既知の制約**（初版時点、Phase 11の実環境検証で解消・調整する想定）:

- AI連携（NewtonX ADK）のPAT認証は配布先の端末ごとに利用者本人が設定画面から入力する
  必要がある（PATは個人アカウントに紐づくため、パッケージに同梱しても共有できない）

### 7.5 DBマイグレーションを伴う配布パッケージの更新（既存インストール先への反映）

**2026-08-29時点、DBスキーマ更新はアプリ起動時に自動で行われる**（`app/main.py`の
`upgrade_database_schema`）。配布先の実行ファイル一式（`Michinari.exe`）を新パッケージへ
入れ替え、`data\michinari.db` はそのまま残した状態で `Michinari.bat` を起動するだけで、
未適用のマイグレーション（Alembicの`alembic upgrade head`相当）が自動適用され、データは
保持される。実行前にはDBファイルの安全退避コピー（`data\backups\backup_*_pre_migration.db`）
が自動で作成される。

この自動マイグレーションは、本機構導入前（`create_all_tables()`のみでスキーマを構築して
いた時期）に配布されたDBも正しく扱える。それらのDBは`alembic_version`テーブルを持たない
ため、まず`_PRE_ALEMBIC_BASELINE_REVISION`（実質スキーマが一致する既知のリビジョン）へ
`stamp`してから未適用分のみを`upgrade`する（テーブルの二重作成エラーを避けるため）。

以下は自動マイグレーションが使えない・使いたくない場合の代替手段。

#### 方式A: 新規DB作成（データ移行不要な場合）

配布先の学習データを保持する必要がない場合の最短手順。

1. 通常どおり `build_package.py` を実行し新パッケージを生成する
2. 配布先の `%LOCALAPPDATA%\Michinari\data\` フォルダを削除またはリネーム退避する
3. 新パッケージ（`backend/dist/Michinari/`）を配布先へコピーし `Michinari.bat` を起動する
4. 初回起動時の自動マイグレーション（空DBのため`upgrade head`がチェーンの先頭から適用
   され、`create_all_tables()`と同じ最終スキーマになる）が全テーブルを新規作成する

#### 方式B: 全データエクスポート/インポート（GUI操作でデータを引き継ぐ）

アプリ内蔵のデータ管理機能（`GET /api/v1/data/export` / `POST /api/v1/data/import`）を使う。
自動マイグレーションがあるため通常は不要だが、DBファイルを直接扱わずGUI操作のみで
引き継ぎたい場合や、新旧バージョン間で大きくスキーマが変わる場合に使う。

1. 配布先で旧バージョンのアプリを起動し、データ管理画面からエクスポートしてJSONを保存する
2. 通常どおり `build_package.py` を実行し新パッケージを生成する
3. 配布先の `data` フォルダを退避し、新パッケージへ入れ替えて起動する
   （自動マイグレーションにより新スキーマでDBが作成される）
4. 新バージョンのアプリのデータ管理画面から、手順1でエクスポートしたJSONをインポートする

**既知の制約**: インポート処理（`backup_service.import_all_data`）はエクスポートJSONに
含まれる列のみを生SQLで `INSERT` するため、SQLAlchemyモデル側の `default=`（例:
`WeeklySummary.is_anonymized`）はORM経由の挿入でのみ適用され、このインポート経路には
適用されない。マイグレーションで**サーバ側デフォルト値を持たないNOT NULL列**を追加した
場合、旧バージョンのエクスポートJSONにはその列が存在せず、インポート時に
`NOT NULL constraint failed` で失敗する。該当する変更を配布する場合はエクスポート/
インポートを使わず、通常どおりDBファイルをそのまま引き継いで自動マイグレーションに
任せる（方式Aの手順3・4のように、DBファイルを配布先に残したまま新パッケージへ入れ替える）。

#### 方式C: 開発機でのAlembic手動実行（自動マイグレーションが使えない例外的なケース）

自動マイグレーション自体に不具合がある、データを段階的に変換する必要がある等、
起動時の自動適用に任せられない例外的な修正でのみ使う。

1. 配布先の `data\michinari.db` をバックアップコピーしたうえで、開発機の作業用フォルダへ
   コピーする
2. 開発機の `backend` ディレクトリで、コピーしてきたDBファイルを指すよう
   `MICHINARI_DATABASE_URL` を指定してマイグレーションを実行する
   （`app/config.py` の `Settings` は `env_prefix="MICHINARI_"` のため、この環境変数で
   `database_url` を上書きできる）
   ```powershell
   cd backend
   $env:MICHINARI_DATABASE_URL = "sqlite:///C:/work/michinari_migrate/michinari.db"
   uv run alembic upgrade head
   ```
3. マイグレーション後のDBファイルの中身を確認する（`sqlite3` 等で主要テーブルを確認）
4. `build_package.py` で新パッケージを生成し、配布先の実行ファイル一式
   （`Michinari.exe` 等）を新パッケージへ入れ替える
5. マイグレーション済みのDBファイルを配布先の `data\michinari.db` へ戻す
6. 配布先で `Michinari.bat` を起動し、データが保持され新機能が動作することを確認する

| 方式 | データ保持 | 作業の複雑さ | 向いているケース |
|---|---|---|---|
| A: 新規DB作成 | ✕（失われる） | 低 | 検証用途、データ保持不要 |
| B: エクスポート/インポート | ○（GUIで完結） | 中 | NOT NULL列追加を伴わない変更 |
| C: Alembicマイグレーション | ○（そのまま） | 高（開発環境が必要） | NOT NULL列追加等、正式な移行が必要な変更 |

### 7.6 開発環境セットアップ（ソースからのローカル起動）

配布パッケージ（7.4）を使わず、ソースコードから直接起動して動作確認する場合の手順。

**バックエンド**

```bash
cd backend
uv sync              # 依存関係のインストール（venv自動作成）
uv run alembic upgrade head   # スキーマ構築
uv run python -m app.main     # 起動（app_setting.server.portに従う。既定値8100）
```

起動時に `app_setting` / `prompt_template` / `day_type_default` の初期データが投入される（冪等）。`GET /health` で疎通確認できる。

```bash
uv run pytest -q --cov=app --cov-report=term-missing   # テスト（カバレッジ100%）
uv run ruff check .                                     # 静的解析
```

**フロントエンド**

```bash
cd frontend
npm install                    # 依存関係のインストール（frontend/.npmrc の legacy-peer-deps が必要。下記参照）
npm run generate:api-types     # backend/app/main.py の OpenAPI スキーマから src/types/api.d.ts を生成
                                # （バックエンドのスキーマ変更時は必ず再実行する。手書き禁止）
npm run dev                    # 開発サーバ起動（vite.config.ts の proxy で /api を backend:8100 へ転送）
```

```bash
npm run build           # 型チェック（tsc -b）+ 本番ビルド
npm run test            # Vitest + カバレッジ計測（閾値100%。下回ると失敗する）
npm run test:no-coverage # 計測なしで素早く回したいとき
```

**フロントエンドのテストとカバレッジ**

テストは Vitest（環境は `jsdom`）で実行する。純粋関数の単体テストに加え、`@testing-library/react` によるコンポーネントの描画テストも書ける。

閾値は行・分岐・関数・文すべて100%（`vite.config.ts` の `test.coverage`）。計測対象は `src/**/*.ts`（判定ロジック）と、描画テストを書いた `.tsx` を個別に追加する方式とする。未計測の `.tsx` を一括で対象にすると 0% が大量に並んで実際の穴が埋もれるため、テストを書いたものから加えていく。

| 除外 | 理由 |
| --- | --- |
| テスト未整備の `src/**/*.tsx` | 一括で対象にすると実際の穴が埋もれる。テストを書いたものから `include` に追加する |
| `src/**/use*.ts` | Reactフック。呼び出しにコンポーネントのレンダリングが必要で、フック単体を検証しても実際の使われ方を再現できない |
| `src/types/**` | `openapi-typescript` による自動生成 |
| `src/constants/**`、`src/locales/**` | 定数・文言のみで分岐を持たない |
| `src/api/**` | API呼び出しの薄いラッパ。実通信なしでは意味のある検証にならない |
| `src/utils/downloadBlob.ts` | ブラウザAPI（`document` / `URL.createObjectURL`）に直接依存 |

到達不能な防御的分岐（型の絞り込みのためだけのガード等）は `/* v8 ignore next N */` と理由コメントで個別に除外する（CODING_RULES.md「除外可」）。

## 任意ツールの導入

開発ツール・CLIのインストールは**仮想環境（`myvenv`）配下に閉じる**（CLAUDE.md「ツール導入ルール」）。システム全体へのインストール（`winget` / `choco` / `scoop` 等）は行わない。環境を汚さず、不要になればディレクトリごと捨てられる状態を保つため。

| 種類 | 手順 |
| --- | --- |
| Python パッケージ | `myvenv` を有効化して `pip install <package>` |
| 単体バイナリ（Go製CLI等） | 公式配布物を取得 → **SHA256 を公式チェックサムと照合** → `myvenv/Scripts/` へ配置 |

`myvenv/Scripts/` は `myvenv` 有効時に PATH に含まれるため、Hook の `command -v <tool>` で解決される。

### osv-scanner（依存脆弱性スキャン）

`vuln-scan.sh`（Stop Hook）が使う。未インストールならスキップされる opt-in 方式。

```bash
# 公式リリース: https://github.com/google/osv-scanner/releases （Google製 / Apache-2.0）
curl -sL -o "$TEMP/osv-scanner.exe" https://github.com/google/osv-scanner/releases/download/v2.5.1/osv-scanner_windows_amd64.exe
curl -sL -o "$TEMP/SHA256SUMS"      https://github.com/google/osv-scanner/releases/download/v2.5.1/osv-scanner_SHA256SUMS
sha256sum "$TEMP/osv-scanner.exe"          # 出力を SHA256SUMS の該当行と照合してから次へ進む
cp "$TEMP/osv-scanner.exe" myvenv/Scripts/osv-scanner.exe
osv-scanner --version                      # 導入確認
```

**スキャン結果の読み方**: 本リポジトリには付属開発キット `newtonx_adk/` のサンプル（`adk_examples/*/requirements.txt`、`tools/local/requirements.txt`）が含まれており、そこに古い `requests` / `click` / `pillow` が記載されているため常に検出される。これらはアプリ本体（`backend/app`）が参照しておらず、インストールもされない。**`backend/` と `frontend/` に検出が出た場合のみ対応を要する**。

なお `.claude/worktrees/`（サブエージェント用の一時worktree）はリポジトリの複製であり、同じ検出が二重三重に出るため `.gitignore` に追加して走査対象から外している。

---

**`.npmrc`（legacy-peer-deps）について**

`openapi-typescript@7.13.0`（最新）の peer 要求が `typescript@^5.x` のままで、本プロジェクトの `typescript@~6.0.2` と衝突する。`frontend/.npmrc` で `legacy-peer-deps=true` を設定していないと、依存を追加していない状態でも `npm install` が ERESOLVE で失敗する。`openapi-typescript` が typescript 6 に対応したら（peerDependencies の更新を確認のうえ）`.npmrc` ごと削除する。

`openapi-typescript` は API 型生成専用の開発依存であり、実行時の依存ではない。依存パッケージに既知脆弱性が出た場合は `npm audit fix` で解消できるか確認する（過去に `@redocly/openapi-core` → `js-yaml@4.3.1` の GHSA-2883-xcg3-v3hh を、`js-yaml@4.3.2` への更新で解消した実績がある）。解消できない場合のみ、本番バンドルに含まれるか・外部入力を扱うかを評価したうえで扱いを判断する。

フロントエンド起動には `backend` を先に起動しておくこと（`uv run python -m app.main`、既定ポート8100）。

---

## 8. トラブルシューティング

### 8.1 Claude Code / Hook 関連

| 症状 | 原因 | 対処 |
|---|---|---|
| SessionStart Hook が発火しない | `.git-automation-config` がない | 作成 or `setup.sh` 再実行 |
| 「初回セットアップが必要」が出続ける | `.git-automation-setup-done` が未作成 | `touch .claude/.git-automation-setup-done` |
| auto-commit が発火しない | 保護ブランチにいる | `dev/YYYY-MM-DD` に移動 |
| auto-commit が発火しない（2） | テストが失敗している | テスト修正 → 再度セッション終了 |
| PreToolUse Hook で編集ブロック | 危険API / 機密ファイル | 代替実装に変更 or テンプレートファイル編集 |
| PR が自動作成されない | `gh` 未認証 | `gh auth login` |

### 8.2 Git / GitHub 関連

| 症状 | 対処 |
|---|---|
| push 失敗（認証） | `gh auth refresh` / PAT 更新 |
| push 失敗（コンフリクト） | `git pull --rebase` で解決 |
| `dev/YYYY-MM-DD` が既に存在（他人のブランチ） | ブランチ名に `-2` 等の suffix を手動付与 |
| 古いブランチが削除されない | PR が OPEN 状態、手動マージ or クローズ |
| 当日ブランチが作成されず前日ブランチのまま | 仕様どおり（前日が未マージ＝作業中）。分けたい場合は PR をマージしてセッションを開き直す |
| 「fast-forward できません」で当日ブランチが作られない | ローカル `main` が `origin/main` と分岐している。`git checkout main && git pull --rebase` 等で最新化してから開き直す |

### 8.3 CI/CD 関連

| 症状 | 対処 |
|---|---|
| gitleaks 検知 | ローカルで `secret-scan.sh` 実行 → 該当箇所を `.env` に移動 |
| npm audit 失敗 | `npm audit fix` or 該当パッケージ更新 |
| Semgrep 警告 | `injection-reviewer` / `xss-reviewer` で詳細確認 |
| CodeQL High | `auth-reviewer` で該当箇所を深掘り |
| ビルド失敗 | `/check-deploy` スキルを実行 |

### 8.4 セキュリティツール関連

| 症状 | 対処 |
|---|---|
| `block-dangerous-edit.sh` で誤検知 | パターンを `.claude/hooks/block-dangerous-edit.sh` で調整 |
| `secret-scan.sh` で誤検知 | パターンの除外条件を追加、または `.env.example` にリネーム |
| Agent が適切な指摘をしない | プロンプト（`.claude/agents/*.md`）を更新 |

### 8.5 配布パッケージ・アプリ起動 関連

| 症状 | 原因 | 対処 |
|---|---|---|
| `Michinari.bat` 実行後、一瞬だけウィンドウが出て閉じる | 起動時エラーで異常終了している | `Michinari.bat` は異常終了時のみ `pause` で停止しエラーを表示する（`backend/scripts/launcher_template.bat`）。表示されない場合は配布物が古いため再ビルドして差し替える |
| 起動時に `Can't locate revision identified by '<リビジョンID>'` | DBに記録されたリビジョンが、exeへ同梱されたマイグレーションより新しい（＝**配布物が古い**） | 最新のソースで再ビルドして配布物を差し替える。開発端末では `git pull` / マージ漏れがないか確認したうえで `backend/build.bat` を再実行する |
| `is not recognized as an internal or external command` でexeが起動しない | 環境変数 `NoDefaultCurrentDirectoryInExePath` が設定された端末では、cmd.exe がカレントディレクトリを探索しない | `Michinari.bat` はexeをフルパス（`"%~dp0Michinari.exe"`）で起動する。旧版のbatを使っている場合は再ビルドして差し替える |

---

## 9. 連絡先・エスカレーション

### 9.1 連絡先一覧

| 役割 | 担当 | 連絡先 | 対応時間 |
|---|---|---|---|
| セキュリティ責任者 | | | |
| インフラ責任者 | | | |
| 開発リード | | | |
| 法務 | | | |
| 広報 | | | |
| 顧客サポート | | | |
| 外部セキュリティベンダー | | | |

### 9.2 エスカレーション基準

| 状況 | エスカレーション先 | タイミング |
|---|---|---|
| SEV-1 インシデント | セキュリティ責任者 + 経営 | 即時 |
| SEV-2 インシデント | セキュリティ責任者 | 1時間以内 |
| シークレット漏洩 | セキュリティ責任者 + 法務 | 即時 |
| 個人情報漏洩（GDPR対象） | 法務 + 経営 + DPO | 即時（72時間以内に当局通知） |
| サービス停止（SEV-1） | インフラ責任者 + 経営 | 即時 |
| 不審アクセス検知 | セキュリティ責任者 | 1時間以内 |

### 9.3 外部通報窓口

| 種別 | 窓口 | URL / 連絡先 |
|---|---|---|
| 脆弱性報告（社外向け） | security@example.com | |
| GitHub セキュリティアドバイザリ | repo の Security タブ | |
| 当局通報（個人情報） | 個人情報保護委員会 | https://www.ppc.go.jp/ |

---

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
