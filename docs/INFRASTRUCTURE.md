# INFRASTRUCTURE.md — インフラ構成・環境情報（Web公開サービス）

| 版 | 日付 | 内容 |
| --- | --- | --- |
| v0.1 | 2026-11-28 | 初版（骨子のみ、単位1）。開発Todo_Web公開_v1.0.md 付録Aを基に作成。最終化は単位6 |
| v0.2 | 2026-11-28 | 単位2実装分の環境変数を追記（D-20の上限値4件・D-09の論理日境界時刻1件） |

本ドキュメントは`publish_server/`（Web公開サービス、開発Todo_Web公開_v1.0 D-12）のサーバー構築者向け
情報を記載する。既存のデスクトップアプリ（`backend/`）はローカル完結のため対象外（配布は
`OPERATIONS.md` 7.4のPyInstaller方式を継続）。

## 1. ホスティング構成（利用者確認済み、2026-11-28）

| 役割 | サービス | 選定理由 |
| --- | --- | --- |
| DB | Supabase（マネージドPostgreSQL） | D-13・D-23で確定したPostgreSQLを、自前運用せずマネージドで利用する |
| アプリ本体（publish_server） | Render（Web Service、Python Native Environment） | Dockerfile不要でFastAPI常駐プロセスを動かせる。CLAUDE.md「Dockerは使わない」（デスクトップ配布前提の既存ルール）の例外化（D-15）を迫らずに済む。TLS終端・環境変数管理・git連携を標準提供 |

Render・Supabaseの無料/低コスト枠の条件は変わりやすいため、実際の契約前に各公式ドキュメントで
最新の仕様を確認すること（CLAUDE.md情報源信頼性ルール。本書作成時点では一次ソース未検証）。

## 2. 環境変数（`publish_server/app/config.py` `Settings`、`PUBLISH_`プレフィックス）

| 変数名 | 用途 | 既定値（開発用） |
| --- | --- | --- |
| `PUBLISH_DATABASE_URL` | DB接続文字列。本番はSupabaseの`postgresql+psycopg://...`を設定する | `sqlite:///./publish_server.db` |
| `PUBLISH_CORS_ALLOWED_ORIGINS` | 公開ビューア（単位3）のオリジン（カンマ区切り、複数可） | 空（CORS無効） |
| `PUBLISH_LOGIN_MAX_ATTEMPTS` | ログイン試行回数制限（D-17） | `5` |
| `PUBLISH_LOGIN_LOCKOUT_MINUTES` | ロック時間（分） | `15` |
| `PUBLISH_SESSION_LIFETIME_HOURS` | セッションの有効期限（時間） | `24` |
| `PUBLISH_MAX_SNAPSHOT_BYTES` | スナップショット1件あたりの最大サイズ（JSON化後、D-20） | `2097152`（2MB） |
| `PUBLISH_MAX_VOCAB_CARDS` | 単語帳カード数上限（公開1件あたり、D-20） | `500` |
| `PUBLISH_MAX_QUIZ_QUESTIONS` | 問題数上限（公開1件あたり、D-20） | `1000` |
| `PUBLISH_MAX_FIELD_CHARS` | 1フィールドの文字数上限（D-20） | `2000` |
| `PUBLISH_TODAY_BOUNDARY_HOUR` | 「今日」の論理日の境界時刻（UTC・0〜23、D-09）。ローカル側`CALENDAR_DAY_BOUNDARY_HOUR`とは異なり、複数利用者が同じプロセスを共有するためサーバ全体で1つの値とする | `0` |
| `PUBLISH_LOG_LEVEL` | ログレベル | `INFO` |

単位1計画時点の付録Aでは上記上限値を`MAX_SNAPSHOT_BYTES`／`MAX_SNAPSHOT_ITEMS`／`MAX_FIELD_CHARS`
の3変数として想定していたが、単位2実装では既存の`PUBLISH_`プレフィックス（他の環境変数と同じ
命名規則）に揃え、かつ単語帳カード数と問題数を別上限値として分離した（`MAX_SNAPSHOT_ITEMS`→
`PUBLISH_MAX_VOCAB_CARDS`・`PUBLISH_MAX_QUIZ_QUESTIONS`の2変数）。

開発Todo_Web公開_v1.0.md 付録Aの計画段階では`SESSION_SECRET`（セッション署名・CSRFトークン
生成用の秘密鍵）も環境変数として想定していたが、単位1の実装ではセッション・CSRFトークンとも
`secrets.token_urlsafe`による乱数（署名なし、DB側で都度ハッシュ照合）とする設計を採用したため
不要になり、実装していない（2026-11-28、secret-reviewerレビューで未使用の既定値であることが
判明し削除）。

## 3. DB

PostgreSQL（Supabase）。Alembicでマイグレーション管理する（`publish_server/alembic/`）。
接続ドライバ`psycopg`／`psycopg-binary`はLGPL-3.0-onlyライセンス（dist-info METADATAで確認済み、
dependency-reviewerレビュー2026-11-28）。publish_serverは自社運用のSaaSとして動かす前提（第三者への
ソース・バイナリ配布は行わない）であればLGPLv3の頒布条項には該当しない。将来、配布形態を変える
場合（セルフホスト向け配布等）は要再確認。
開発・テストはSQLite（既定値）で動作する（`publish_server/app/database.py`、`tests/conftest.py`）。

## 4. TLS

publish_server自体はTLSを終端しない。Renderが前段でTLS終端を行う（Transfer）。

## 5. ログ

パスワード・トークン平文をログへ出力しない（`publish_server/app/api/errors.py`の
`RequestValidationError`ハンドラが入力値そのものをログへ残さない設計、backend/app/api/errors.pyと
同じ方針）。

## 6. バックアップ

Supabase側の定期バックアップ機能を利用する想定（保持期間等の詳細は未確定、
開発Todo_Web公開_v1.0.md 10章9節）。

## 7. デプロイ手順（骨子、単位6で最終化）

1. Supabaseでプロジェクトを作成し、接続文字列を取得する
2. Renderで新規Web Serviceを作成し、`publish_server/`をルートディレクトリに指定する
3. 上記の環境変数を設定する
4. Alembicマイグレーションを実行する（`uv run alembic upgrade head`）
5. publish_serverを起動する（Render側のビルド・起動コマンドは単位6で確定）
6. ヘルスチェック確認（`GET /health`）
7. ドメイン・DNS設定

## 8. 想定する利用規模

個人利用規模（数名〜数十名程度）を想定。
