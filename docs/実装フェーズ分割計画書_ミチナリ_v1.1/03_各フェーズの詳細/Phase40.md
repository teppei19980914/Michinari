### Phase 40：診断ログ出力・トレース強化 + ログ期間エクスポート

| 項目 | 内容 |
| --- | --- |
| 目的 | エラーが起きた際に利用者自身が該当期間のログを取得し、開発者へ共有して原因調査できるようにする |
| 投入文書 | CLAUDE.md、docs/CODING_RULES.md、docs/OPERATIONS.md、docs/仕様書_ミチナリ_v1.1.md（6.14節）、docs/設計書_データ構造編_ミチナリ_v1.1.md（API仕様・セキュリティ設計節） |

**背景**

利用者から「エラーが起きたときの操作・原因をログから追跡し、開発者へ共有して調査を依頼したい」との要望を受けた。既存のログ出力を実機調査した結果、HTTPアクセスログ（method/path/status）は`uvicorn.access`が root ロガーへ伝播する形で既に`michinari.log`へ記録されていたが、業務エラー（400/404/409、`DomainError`系）は一切ログに残らず、利用者が実際につまずくエラーの大半が事後にトレースできない状態だった。またリクエスト相関IDが無く複数のログ行を1操作に紐づけられない、フロントの`ErrorBoundary`はコンソールにしか出さずイベントハンドラ・非同期処理内の例外は構造的に取りこぼす、という欠陥も判明した。

**実装対象**

- バックエンド：新規`app/middleware/request_context.py`（相関ID用ContextVar、`setLogRecordFactory`による全ログレコードへの相関ID自動付与、アクセスログ出力ミドルウェア）。`app/desktop/logging_setup.py`のログ書式に相関IDを追加。`app/desktop/runner.py`でuvicorn標準アクセスログを無効化（`access_log=False`）。`app/api/errors.py`の`handle_domain_error`・`handle_request_validation_error`にログ出力を追加（入力値そのものはログに残さない方針、`RequestValidationError.errors()`の`input`キーは使わない）。新規`POST /api/v1/client-logs`（`app/api/client_logs.py`・`app/schemas/client_logs.py`）。新規`GET /api/v1/system-info/logs/export`（`app/api/system_info.py`に追加、`app/services/system_log_export_service.py`でローテーション世代を横断した期間フィルタ）
- 副次的に発見し修正した既存バグ：alembicの`fileConfig()`（`disable_existing_loggers`既定True）が、呼び出し時点で存在する非alembicロガーを無効化する副作用を持つことが判明（2026-09-17に対処したハンドラ差し替え問題の同根の別症状）。`app/desktop/logging_setup.py`に`preserve_logging_state()`を新設し、`app/main.py`の`upgrade_database_schema`・`backend/tests/conftest.py`・`backend/tests/migration_helpers.py`・`backend/tests/test_migration.py`・`backend/scripts/release_smoke.py`の全てのalembic直接呼び出し箇所へ適用
- フロントエンド：`api/client.ts`がレスポンスの`X-Request-Id`ヘッダを`ApiError.requestId`として保持し、`apiErrorDetail`がToastの詳細欄へ「エラーID」を追記。新規`errorReporting/reportClientError.ts`（`ErrorBoundary`・グローバルハンドラ共有）、新規`errorReporting/registerGlobalErrorHandlers.ts`（`window`の`error`/`unhandledrejection`、`main.tsx`から登録）。`ErrorBoundary.tsx`が捕捉したエラーを`reportClientError`経由でバックエンドへ送信。新規`features/systemInfo/LogExportSection.tsx`（プリセット期間＋手動指定、`api/systemLogs.ts`経由でダウンロード）を`SystemInfoPage`（SC-15）へ追加。「今日」はサーバの論理日（`GET /records/today`）を起点にし、ブラウザの`Date()`を使わない（CLAUDE.md「クライアント側での論理日の判断」禁止）

**設計判断（脅威モデリングSTRIDEで確定した論点）**

- 信頼境界：本アプリはシングルユーザーのローカル常駐デスクトップアプリで無認証のため、`POST /client-logs`は既存の信頼境界内の入力として扱う
- `client-logs`のペイロードは`Field(max_length=4000)`で上限を設け、超過は既存の`RequestValidationError`ハンドラで自動400（DoS対策）
- `message`はログインジェクション対策として改行をエスケープしてから1行で記録。多行が前提の`stack`/`component_stack`は明示的な区切りの下に記録する
- 全クリックを追跡する行動ログ（分析目的のテレメトリ）は今回のスコープ外とする（プライバシー配慮・実装コストの観点で利用者と合意済み）

**完了条件**

- 業務エラー・検証エラーが相関ID付きでログに記録される（入力値そのものは含まれない）
- フロントの描画エラー・イベントハンドラ内の未処理例外が`POST /client-logs`経由でバックエンドのログへ記録される
- Toastのエラー詳細に相関ID（エラーID）が表示される
- システム情報画面（SC-15）で任意期間（プリセット／手動指定）のログをダウンロードでき、ローテーション世代をまたぐ期間でも欠落なく結合される

---

**Phase40完了（2026-09-25）。**

- バックエンド：新規モジュール4件（`middleware/request_context.py`・`api/client_logs.py`・`schemas/client_logs.py`・`services/system_log_export_service.py`）、新規テストファイル4件（`test_request_context.py`・`test_api_client_logs.py`・`test_system_log_export_service.py`ほか既存3ファイルへ追記）。副次的な既存バグ修正（alembic fileConfigのロガー無効化）を含め1521テスト（既知の無関係な既存フレーキーテスト1件を除き全通過）
- フロントエンド：新規ファイル5件（`errorReporting/reportClientError.ts`・`errorReporting/registerGlobalErrorHandlers.ts`・`api/systemLogs.ts`・`features/systemInfo/LogExportSection.tsx`ほか）、新規テストファイル4件。`openapi-typescript`による型再生成を実施。1158テスト・カバレッジ100%
- `tsc -b`・`ruff check`・oxlint（新規の`set-state-in-effect`警告はuseEffectを使わずレンダー中に導出する設計へ変更して解消）通過

---

