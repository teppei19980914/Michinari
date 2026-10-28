# 開発Todo：記録リマインドと自動起動の案内

本書は、記録リマインド通知を確実に届けるための導線追加（新規利用者への1問案内／既存利用者へのダッシュボード案内）の開発作業の正（Single Source of Truth）である。作業は`dev/2026-10-26`で開始し、同日のPRがmainへマージ済みと確認できたため2026-10-28に`dev/2026-10-28`へ移行した（作業内容はそのまま持ち越し）。

## 0. 決定事項

| # | 決定 | 値・理由 |
| --- | --- | --- |
| D1 | 新規利用者向け質問の表示場所 | **ダッシュボード画面のマウント時**（ウェルカム画面の作成モーダル／資格ウィザードの中ではない）。理由：いずれの作成経路（`QuickCreateGoalModal`のonCreated、`useExamGoalWizard.activate`）も成功後に`navigate(ROUTES.dashboard)`する単一の合流点があり、`DashboardPage.tsx`の`showFirstRecordBanner`（dashboard.has_ever_reported_recordという実データに基づく判定、location.stateに依存しない）と同じ設計方針に揃えられる。表示条件をサーバ側の1フラグに一本化できるため、作成経路が将来増えても個別対応が不要（CLAUDE.md DRYの原則） |
| D2 | 表示条件（新規） | `GET /dashboard`レスポンスの新フィールド`show_reminder_onboarding_prompt`（= `!desktop.reminder_onboarding_shown`）。ダッシュボードは目標0件では`/welcome`へリダイレクトされる（既存実装）ため、このフラグは「目標が1件以上あり、かつ未案内」の場面でのみ画面に現れる |
| D3 | 「表示済み」フラグの保存先 | 新規`app_setting`キー`desktop.reminder_onboarding_shown`（真偽値）。既存の`desktop.notification_check_interval_seconds`と同様、**Alembicマイグレーションではなく起動時シード（`app/init/seed_data.py`）で投入する**（同ファイル冒頭のdocstring「マイグレーションではなくアプリケーション起動時に行う」を根拠とする。新規テーブル追加ではなく既存テーブルへの行追加のため、CODING_RULES.mdの「既存データに対する安全性」マイグレーションテスト規定の対象外） |
| D4 | 既存利用者が誤って新規案内を見ない対策 | D3のシード投入時、**既に目標が1件以上あるDBでは初期値を`true`（＝既に案内済み扱い）、無ければ`false`**で投入する専用関数を`seed_data.py`に追加する（既存の`INITIAL_APP_SETTINGS`フラット辞書は値が固定のため、条件分岐が要るこのキーだけは対象外とし、`backfill_reading_assistant_defaults`と同じ「個別シード関数」の前例に従う） |
| D5 | 既存利用者向けダッシュボード案内の表示条件 | `GET /dashboard`の新フィールド`show_reminder_autostart_banner`（= `desktop.notification_enabled AND NOT desktop.launch_at_login AND NOT desktop.autostart_banner_dismissed`）。「閉じたら再表示しない」は新規`app_setting`キー`desktop.autostart_banner_dismissed`で管理する（初期値`false`、こちらは既存目標の有無に関わらず常に`false`でよいため`INITIAL_APP_SETTINGS`に通常追加する） |
| D6 | 自動起動の即時反映 | `autostart.apply()`は現状**常駐起動時（`app/desktop/runner.py: run()`）にしか呼ばれない**ため、設定を保存しただけではWindowsレジストリに即時反映されない（次回起動まで有効化されない）。新規`POST /desktop/autostart/sync`エンドポイント（bodyなし）を追加し、保存済みの`desktop.launch_at_login`を読み直して`autostart.apply()`を呼ぶ「今すぐ反映」専用の薄いAPI層処理とする（サービス層は実行環境を知らない、の既存方針どおりAPI層に置く）。**既存の設定画面（`DesktopSection.tsx`）の保存ボタンは変更しない**（本件要件が求めるのは新規2経路の即時反映のみであり、既存の設定画面の挙動を変えるのは本依頼のスコープ外と判断。既存動作は`backend/app/services/settings_service.py:340-346`のコメントどおりの既知の仕様） |
| D7 | 開発環境・失敗時の扱い | `autostart.is_supported()`が`False`（ソース起動）の場合は**情報メッセージ**（「開発環境のため自動起動の登録は反映されません」、エラー扱いしない）。`autostart.enable/disable`が`OSError`を投げた場合（レジストリ書き込み失敗）は`POST /desktop/autostart/sync`がこれを捕捉し`applied=false`を返す（例外を外に出さない）。フロントエンドは`{supported, applied}`に応じて情報/エラーの文言を切り替える |
| D8 | 自動起動の即時反映の対象範囲 | 新規2経路（新規利用者への1問案内の「受け取る」、既存利用者向け案内の「有効にする」）のみ`POST /desktop/autostart/sync`を呼ぶ。設定画面からの変更は対象外（D6） |
| D9 | AI・通信への影響 | なし。本機能はAIを呼ばない。「AI未設定時の挙動」確認は対象外（通知・自動起動はAI接続設定と独立） |
| D10 | DBマイグレーション | 不要（D3・D5のとおり`app_setting`への行追加のみで、既存テーブルのスキーマ変更を伴わないため） |
| D11 | 新規依存ライブラリ | 追加なし |

## 1. 影響範囲（フルスキャンの結果）

### 1.1 バックエンド（変更する箇所）

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| 設定キー | `app/constants/app_setting_keys.py` | 2キー追加：`DESKTOP_REMINDER_ONBOARDING_SHOWN`、`DESKTOP_AUTOSTART_BANNER_DISMISSED` |
| 初期データ | `app/init/seed_data.py` | `DESKTOP_AUTOSTART_BANNER_DISMISSED`を`INITIAL_APP_SETTINGS`へ追加（既定`false`）。`DESKTOP_REMINDER_ONBOARDING_SHOWN`は専用関数`seed_desktop_reminder_onboarding_flag(session)`を新設し`run_all`から呼ぶ（D4） |
| サービス | `app/services/settings_service.py` | `DesktopSettings`データクラス・`get_app_settings`・`_update_desktop`に2フィールド追加。新規関数`resolve_reminder_onboarding_flags(session) -> ...`（dashboard APIが使う2条件の算出。DRYのため算出ロジックをここに集約） |
| スキーマ | `app/schemas/setting.py` | `DesktopSettingsRead`・`DesktopSettingsUpdate`に2フィールド追加。新規`backend/app/schemas/desktop.py`に`DesktopAutostartSyncResult`（`launch_at_login: bool`／`supported: bool`／`applied: bool`） |
| API（新規） | `backend/app/api/desktop.py`（新規ファイル） | `POST /desktop/autostart/sync`。`app/main.py`へ`include_router`追加 |
| API（既存） | `backend/app/api/dashboard.py`、`backend/app/schemas/dashboard.py` | `DashboardRead`に`show_reminder_onboarding_prompt`・`show_reminder_autostart_banner`の2フィールド追加。`get_dashboard`内で`settings_service.resolve_reminder_onboarding_flags(session)`を呼ぶ |
| テスト | `backend/tests/test_settings_service.py`・`test_api_settings.py`・`test_desktop_autostart.py`・`test_api_dashboard.py`・新規`test_api_desktop.py` | 追加 |

### 1.2 バックエンド（確認のみ・横展開チェック）

| 項目 | 確認内容 | 結果 |
| --- | --- | --- |
| `app/desktop/autostart.py` | 既存の`is_supported`/`apply`/`enable`/`disable`は変更不要（新規APIから呼ぶだけ） | 変更なし |
| `app/desktop/scheduler.py`・`notification_service.py` | 通知の判定ロジックへの影響なし（設定値を読むだけで、本件は値の保存経路を増やすのみ） | 変更なし |
| DBマイグレーション（既存データ安全性） | 新規テーブルなし、既存テーブルのカラム変更なしのため対象外 | 対応不要（D10） |
| バックアップ・リストア（`app/services/backup_service.py`） | DBファイル単位の`shutil.copy2`でまるごと複製する実装（`backup_service.py:113,129,145`）。新しい`app_setting`行も自動的に含まれる | 対応不要（確認のみ） |
| 匿名化した書き出し・ナレッジエクスポート（`export_service_*.py`） | 目標・記録データのみを対象とし`app_setting`を参照しない | 対応不要（確認のみ） |
| エクスポートJSONの形式（データ管理） | 同上の理由で影響なし | 対応不要（確認のみ） |
| 3目標種別（EXAM/READING/WORK）とすべての状態 | 本機能は目標のカテゴリ・状態を見ない（ダッシュボードに目標が1件以上あるかどうかのみ） | 対応不要（確認のみ） |
| AI未設定時の挙動 | 本機能はAIを呼ばない（D9） | 対応不要（確認のみ） |
| OpenAPIから生成した型（`frontend/src/types/api.d.ts`） | `npm run generate:api-types`の再実行が必須 | 作業Todoに記載 |

### 1.3 フロントエンド（変更する箇所）

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| API型 | `frontend/src/types/api.d.ts` | 生成し直し（新エンドポイント・新フィールド反映） |
| API層 | `frontend/src/api/desktop.ts`（新規） | `syncAutostart(): Promise<DesktopAutostartSyncResult>` |
| 判定ロジック（`.ts`切り出し） | `frontend/src/features/desktop/reminderOnboarding.ts`（新規） | 時刻入力の妥当性判定は既存`desktopSettings.ts`の`isValidNotificationTime`を再利用（DRY）。登録結果（supported/applied）から表示する文言キーを選ぶ純粋関数 |
| 画面部品（新規） | `frontend/src/features/desktop/ReminderOnboardingPrompt.tsx` | 新規利用者向け1問モーダル（既存`Modal.tsx`を使用） |
| 画面部品（新規） | `frontend/src/features/dashboard/AutostartBanner.tsx` | 既存利用者向けダッシュボード案内（一度だけ表示、ワンクリック有効化・閉じるボタン） |
| 画面 | `frontend/src/pages/DashboardPage.tsx` | 上記2部品を`dashboard.show_reminder_onboarding_prompt`／`show_reminder_autostart_banner`で条件表示 |
| 定数 | `frontend/src/constants/queryKeys.ts` | 既存`QUERY_KEYS.dashboard()`・`QUERY_KEYS.settings()`を再利用（新規キー追加は不要の見込み。実装時に再確認） |
| ロケール | `frontend/src/locales/ja.json`・`en.json` | `desktop.onboardingPrompt.*`・`dashboard.autostartBanner.*`を両言語追加（キー片方のみの追加は`localeKeyUsage.test.ts`で検出されるため必ず両方） |
| テスト | `DashboardPage.test.tsx`、新規`ReminderOnboardingPrompt.test.tsx`・`AutostartBanner.test.tsx`・`reminderOnboarding.test.ts`、`desktopSettings.test.ts`（再利用部分の既存確認） | 追加 |

### 1.4 フロントエンド（確認のみ）

| 項目 | 確認内容 |
| --- | --- |
| `frontend/src/pages/WelcomePage.tsx`、`useExamGoalWizard.ts` | D1により変更不要（ダッシュボード側のみで完結） |
| `frontend/.oxlintrc.json`のmax-lines-per-function/max-depth | 新規コンポーネントも対象。実装後に`npm run lint`で0件を確認 |
| ダークモード・`prefers-reduced-motion` | 新規UIはセマンティックトークン（`bg-surface`等）のみを使用し、アニメーションは追加しない（モーダルの開閉のみ、既存`Modal.tsx`の挙動に従う） |

### 1.5 ドキュメント（変更する箇所）

| 文書 | 変更 |
| --- | --- |
| `docs/要件定義書_ミチナリ_v1.1.md` | 記録リマインドの到達性に関する要件の追記、改訂履歴 |
| `docs/仕様書_ミチナリ_v1.1.md` | SC-01（ダッシュボード）への案内表示の追記、設定項目表、改訂履歴 |
| `docs/設計書_データ構造編_ミチナリ_v1.1.md` | 新規`app_setting`キー2件、`GET /dashboard`レスポンス2フィールド、`POST /desktop/autostart/sync`の追記、改訂履歴 |
| `docs/実装フェーズ分割計画書_ミチナリ_v1.1.md` | 新規Phaseの追加（既存最終Phase番号を確認して採番） |
| `docs/OPERATIONS.md`（分割後の該当章） | 影響なしの見込み（運用手順自体は変わらない）。実装後に再確認 |
| `README.md` | 「起動と通知の設定（任意）」節（108〜123行）に、新規利用者への1問案内・既存利用者への案内の説明を追記 |
| `frontend/src/locales/ja.json`の`help.sections.desktop`（p1〜p5） | 新しい案内の説明を追記（p6を追加） |
| `frontend/src/locales/en.json`の同セクション | 同上（日英同時） |
| `backend/app/content/help_content.json` | `uv run python backend/scripts/export_help_content.py`で再生成（ja.json変更後に必須。手動実行） |

## 2. 現状のベースライン（2026-10-27、開発前）

- バックエンド：`ruff check .` 全通過（0件）。`pytest`：2053件全通過（1 warning）。カバレッジは99%（TOTAL、`--cov-fail-under`を渡さない通常実行のため未達は想定内。リリースゲート相当の100%確認はC4で実施する）
- フロントエンド：`npm run lint`（oxlint）全通過（0件）。`npx tsc -b`全通過。`npx vite build`全通過。`npm run test`（vitest、カバレッジ付き）：161ファイル・1381件全通過、カバレッジ100%（statements/branches/functions/lines）
- 既存の開発Todo・計画との重複・競合：確認済み、本件と重なる未完了の開発Todoは無い（`開発TODO_初学者導線ウィザード.md`は2026-09-18に実装済み・本件と競合しない前提部分のみ参照）

## 3. 作業Todo

凡例：`[ ]` 未着手、`[x]` 完了。各項目の完了条件は「テストが通ること」と「カバレッジ100%（例外処理を除く）」。

### 3.1 バックエンド

- [x] B1 `app/constants/app_setting_keys.py`に`DESKTOP_REMINDER_ONBOARDING_SHOWN`・`DESKTOP_AUTOSTART_BANNER_DISMISSED`を追加（2026-10-28）
- [x] B2 `app/init/seed_data.py`：`DESKTOP_AUTOSTART_BANNER_DISMISSED`を`INITIAL_APP_SETTINGS`へ追加。`seed_desktop_reminder_onboarding_flag(session)`を新設し`Goal`の件数で初期値を分岐、`run_all`へ組み込み（2026-10-28）
- [x] B3 `app/services/settings_service.py`：`DesktopSettings`・`get_app_settings`・`_update_desktop`の拡張、`resolve_reminder_onboarding_flags`の新設（2026-10-28）
- [x] B4 `app/schemas/setting.py`：`DesktopSettingsRead`・`DesktopSettingsUpdate`の拡張（2026-10-28）
- [x] B5 `backend/app/schemas/desktop.py`（新規）：`DesktopAutostartSyncResult`（2026-10-28）
- [x] B6 `backend/app/api/desktop.py`（新規）：`POST /desktop/autostart/sync`（`autostart.is_supported()`/`apply()`の呼び出しとOSError捕捉）。`app/main.py`へ登録（2026-10-28）
- [x] B7 `backend/app/schemas/dashboard.py`・`backend/app/api/dashboard.py`：`show_reminder_onboarding_prompt`・`show_reminder_autostart_banner`の追加（2026-10-28）
- [x] B8 バックエンドテスト追加（B1〜B7に対応する単体・API統合テスト、異常系含む。`test_api_desktop.py`新規、`test_seed_data.py`・`test_settings_service.py`・`test_api_settings.py`・`test_api_dashboard.py`拡張。新規/変更モジュールはいずれもカバレッジ100%、2026-10-28）

### 3.2 フロントエンド

- [x] F1 `npm run generate:api-types`実行、差分確認（2026-10-28）
- [x] F2 `frontend/src/api/desktop.ts`（新規）（2026-10-28）
- [x] F3 `frontend/src/features/desktop/reminderOnboarding.ts`（新規、純粋関数）＋テスト（2026-10-28）
- [x] F4 `frontend/src/features/desktop/ReminderOnboardingPrompt.tsx`（新規）＋テスト（2026-10-28）
- [x] F5 `frontend/src/features/dashboard/AutostartBanner.tsx`（新規）＋テスト（2026-10-28）
- [x] F6 `frontend/src/pages/DashboardPage.tsx`の組み込み＋既存`DashboardPage.test.tsx`の拡張（2026-10-28）
- [x] F7 ロケール：`ja.json`・`en.json`両方に`desktop.onboardingPrompt.*`・`dashboard.autostartBanner.*`を追加（2026-10-28）
- [x] F8 `help.sections.desktop`にp6を追加（ja/en）＋`helpContent.ts`の`bodyKeys`更新（2026-10-28）

### 3.3 ドキュメント

- [x] D-1 `docs/要件定義書_ミチナリ_v1.1.md`改訂（2026-10-28、6.16 R-122〜R-125を新設、改訂履歴1.1改49）
- [x] D-2 `docs/仕様書_ミチナリ_v1.1.md`改訂（2026-10-28、6.1.4・6.11更新、改訂履歴1.1改61）
- [x] D-3 `docs/設計書_データ構造編_ミチナリ_v1.1.md`改訂（2026-10-28、5.2キー追加・Phase37既存キー記載漏れ補完、6.2 API追記、改訂履歴1.1改63）
- [x] D-4 `docs/実装フェーズ分割計画書_ミチナリ_v1.1.md`改訂（2026-10-28、Phase46新設・Phase44/45の索引漏れ補完、改訂履歴1.1改27）
- [x] D-5 `README.md`「起動と通知の設定（任意）」改訂（2026-10-28）
- [x] D-6 `uv run python backend/scripts/export_help_content.py`実行（ja.json改訂後。2026-10-28、`app/content/help_content.json`へp6反映済み、`test_help_content.py`全通過）
- [x] D-7 `docs/OPERATIONS.md`の該当章、影響有無を最終確認（2026-10-28。`08_トラブルシューティング.md`の既存行「自動起動を有効にしたのに起動しない」はソース起動時の制約を説明しており本改訂と矛盾しないため変更不要と判断。運用手順自体の変更もなし）

### 3.4 テスト・静的解析・コミット前チェック（実装完了後）

- [x] C1 `/threat-model`（STRIDE分析）の実施（2026-10-28。本環境では`/threat-model`スキルが利用できなかったため、代替として`security-review`スキルの手順でdiff全体を分析。新規`POST /desktop/autostart/sync`は既存の「認証なし・単一利用者・ローカル動作」という設計方針の範囲内であり、既存の`PATCH /settings`が既に許している変更（`launch_at_login`のオン）を即時反映するだけで新たな権限境界は作らない。HIGH/MEDIUM該当の脆弱性は検出なし）
- [x] C2 該当レビューエージェント並列実行：`dry-reviewer`／`style-reviewer`／`label-checker`／`test-coverage-reviewer`相当のレビューをサブエージェントで実施（2026-10-28）。DRY違反・命名規則違反・ハードコード文言・テストカバレッジ漏れ、いずれも指摘なし（`resolveAutostartSyncMessageKey`呼び出しが2箇所で構造的に似る点のみ軽微な所見としたが、各呼び出し元の送信内容が異なり共通化の明確な利点がないため対応不要と判断）。`secret-reviewer`相当は本体diffに秘密情報・環境変数の新規追加がないため対象外と判断
- [x] C3 `cd backend && ruff check .`（全通過、2026-10-28）
- [x] C4 `cd backend && pytest --cov=app --cov-branch --cov-fail-under=100`（2064件全通過・カバレッジ100%、2026-10-28）
- [x] C5 `cd frontend && npm run lint`（oxlint、0件、2026-10-28）
- [x] C6 `cd frontend && npm run test`（カバレッジ100%確認。初回実行でブランチ99.92%の不足を検出（`AutostartBanner.tsx`の失敗時トースト分岐）、テスト追加後に100%達成、2026-10-28）
- [x] C7 `cd frontend && npx tsc -b`（全通過、2026-10-28）
- [x] C8 `cd frontend && npx vite build`（成功、2026-10-28）
- [x] C9 横展開チェック（同種のフラグ・案内UIの重複実装がないか再検索。`_dismissed`/`_shown`相当のパターンは本機能の新規ファイルのみで、既存の重複実装なしを確認、2026-10-28）
- [x] C10 実機確認（2026-10-28。当初`MICHINARI_DATABASE_URL`での隔離DB起動がポート8100の競合で失敗し、利用者の実稼働中インスタンスへGETが2回届いてしまう事象が発生（読み取りのみ、変更なし）。利用者に報告し、利用者が実機を終了した後、隔離DBで再度起動してAPIシーケンスを検証：新規インストール相当（`show_reminder_onboarding_prompt=true`・`show_reminder_autostart_banner=true`）→「受け取る」相当のPATCH+syncで両方falseへ→自動起動を手動でオフに戻すと`show_reminder_autostart_banner`のみ再度trueへ→閉じる相当のPATCHでfalseへ、の一連を確認。開発環境のため`POST /desktop/autostart/sync`は`supported=false・applied=false`を返すことも確認。終了後、プロセス停止・DBファイル削除済み）

## 4. 処理フロー

### 4.1 新規利用者（1問案内）

1. 目標0件→`/welcome`→いずれかの経路で最初の目標を作成→`navigate(ROUTES.dashboard)`
2. `DashboardPage`が`GET /dashboard`を取得。`show_reminder_onboarding_prompt === true`なら`ReminderOnboardingPrompt`を表示（既定時刻は`desktop.notification_time`の現在値）
3. 「受け取る」：`PATCH /settings`（`desktop.notification_enabled=true`／`notification_time`／`launch_at_login=true`／`reminder_onboarding_shown=true`）→`POST /desktop/autostart/sync`→結果に応じてトースト表示→`QUERY_KEYS.dashboard()`を無効化しモーダルを閉じる
4. 「受け取らない」：`PATCH /settings`（`desktop.reminder_onboarding_shown=true`のみ）→`QUERY_KEYS.dashboard()`を無効化しモーダルを閉じる

### 4.2 既存利用者（ダッシュボード案内）

1. `show_reminder_autostart_banner === true`の間、`AutostartBanner`をダッシュボードに表示
2. 「有効にする」：`PATCH /settings`（`desktop.launch_at_login=true`）→`POST /desktop/autostart/sync`→結果に応じてトースト表示→`QUERY_KEYS.dashboard()`を無効化（launch_at_login=trueになるため条件が自然に偽になり再表示されない）
3. 「閉じる」：`PATCH /settings`（`desktop.autostart_banner_dismissed=true`）→`QUERY_KEYS.dashboard()`を無効化

## 5. 検証の基準

- 新規利用者・既存利用者のいずれも、案内が一度だけ表示され、選択どおりに設定値（`GET /settings`の値）が変わること
- 設定画面（`DesktopSection.tsx`）の表示値と、案内で変更した値が食い違わないこと（同じ`PATCH /settings`経路を使うため自動的に一致する想定だが、実機確認で最終確認する）
- `POST /desktop/autostart/sync`が開発環境（`sys.frozen`なし）で`supported=false`を返し、エラー扱いにならないこと
- 既存のデスクトップ・通知・ダッシュボード関連テストが1件も壊れないこと
- アップグレード相当のシナリオ（既存目標がある状態からの起動）で、`desktop.reminder_onboarding_shown`が`true`で投入され、新規案内が表示されないこと（B2のテストで検証）

## 6. 既知のリスクと対策

| リスク | 対策 |
| --- | --- |
| `POST /desktop/autostart/sync`を2画面から呼ぶことで、意図せず異なるタイミングでレジストリ書き込みが競合する | `winreg`への書き込みはHTTPリクエストの範囲内の短い処理であり、並行呼び出しは通常operationとして許容する（既存の`autostart.enable/disable`自体に排他制御は無く、今回新設する呼び出し元を増やすだけで新たなリスクを追加しない） |
| シードの条件分岐（D4）が将来の「全目標削除」操作と組み合わさり、意図と異なる判定になる可能性 | 判定は**起動時シード（行が存在しない場合のみ）**で1回だけ行い、以後は`app_setting`の値をそのまま使う（都度算出しない）ため、目標を後から削除しても再判定されない。これは意図した仕様（一度案内済みなら再度出さない） |
| ヘルプ本文（ja.json）の変更後に`export_help_content.py`の再生成を忘れる | 作業Todo D-6に明記し、コミット前チェックで`app/content/help_content.json`の差分有無を確認する |
| 実機確認時、`MICHINARI_DATABASE_URL`での隔離DB起動が既定ポート（8100）の競合で失敗し、作業中の実稼働インスタンスへ意図せず到達する（2026-10-28に実際に発生。読み取りのみで変更は無かった） | 隔離DBでの実機確認を行う前に、同ポートで稼働中のインスタンスが無いことを`netstat`等で確認する。稼働中の場合は利用者に終了を依頼してから行う（自動で終了させない） |

## 7. 完了の定義

- 作業Todo（§3）の全項目が完了していること
- §5の検証の基準を全て満たしていること
- バックエンド・フロントエンドとも既存テストの失敗が0件、カバレッジ100%（例外処理を除く）
- §1.5の全文書が更新されていること
- 実機確認（C10）を実施し、結果を§8に記録していること

## 8. 作業記録

- 2026-10-27：工程1〜3（前提資料の読み込み、全ソースコードの影響範囲確認、本Todoの作成）を実施。バックエンドのベースラインは`ruff check .`全通過・`pytest`2053件全通過（カバレッジ99%、`--cov-fail-under`なしの通常実行）。フロントエンドのベースラインは`npm run lint`全通過・`npm run test`161ファイル1381件全通過・カバレッジ100%。
- 2026-10-27→28：作業中にdev/2026-10-26のPRがmainへマージ済みと確認できたため、未コミットの作業一式を`dev/2026-10-28`へ引き継いで継続（作業内容の損失なし、git stash経由で復元）。
- 2026-10-28：工程4（実装）を実施。バックエンド（B1〜B8）・フロントエンド（F1〜F8）・ドキュメント（D-1〜D-7）の全項目完了。
- 2026-10-28：工程5（検証）を実施。
  - セキュリティレビュー（`/threat-model`が本環境で未提供のため`security-review`スキルで代替）：HIGH/MEDIUM該当なし。
  - レビューエージェント（dry/style/label-checker/test-coverage相当）：指摘なし。
  - バックエンド：`ruff check .`全通過、`pytest --cov=app --cov-branch --cov-fail-under=100`で2064件全通過・カバレッジ100%（ベースライン比+11件）。
  - フロントエンド：`npm run lint`・`npx tsc -b`・`npx vite build`全通過。`npm run test`は初回実行でブランチカバレッジ99.92%（`AutostartBanner.tsx`の失敗時トースト分岐が未検証）で不足を検出し、テストを1件追加して100%達成（ベースライン比+8件、169ファイル）。
  - 実機確認（C10）：隔離DB起動が既定ポート8100の競合で失敗し、利用者の実稼働インスタンスへGETが2回届く事象が発生（読み取りのみ、変更なし。利用者へ即時報告）。利用者が実機を終了後、`MICHINARI_DATABASE_URL`で隔離DBを使い`uv run python -m app.main --console`を起動し、curlで新規利用者（受け取る）・既存利用者（有効化・再表示・閉じる）の全シナリオと、開発環境での`POST /desktop/autostart/sync`の`supported=false`応答を確認。終了後、プロセスを停止し隔離DBファイルを削除、利用者の実機ポートが空いていることを確認した。
