# 開発Todo：1年前の今日（過去の記録をときどき表示）

本書は、過去の同じ日（1年前・半年前・1か月前など）の記録をダッシュボードにときどき表示する機能の開発作業の正（Single Source of Truth）である。
新フェーズ Phase 50 として実施する。作業は `dev/2026-11-08`（`origin/main` から作成）で行う。AIは使用しない（DBの読み取りのみで完結、ダッシュボード初期表示2秒以内の性能要件を守る）。

## 0. 決定事項（2026-11-08 時点で確定）

依頼文で「app_settingに置く」「決める」と委任された論点は、フルスキャンの結果（§1）を踏まえて以下のとおり確定する。依頼文に明記済みの前提（アプリ全体の値を推奨・アーカイブ/クローズ済み目標を対象・削除済み目標を対象外・AI不使用・DB読み取りのみ）はそのまま採用し、再確認のための質問はしていない。

| # | 決定 | 値・理由 |
| --- | --- | --- |
| V1 | 候補期間の既定値 | 依頼文の例示そのもの：**1年前（12か月前）・半年前（6か月前）・1か月前（1か月前）** の3件。`app_setting`（`on_this_day.candidate_months_ago`、カンマ区切り昇順int文字列、既存の`setting_reader.get_int_list`をそのまま再利用、新規パース処理は不要） |
| V2 | 「Nか月前」の日付計算 | 新規ヘルパー`on_this_day_service.subtract_months(base, months)`：年・月を減算し、対象月にその日が存在しない場合（うるう年2/29・月末31日等）は`calendar.monthrange`でその月の最終日にクランプする。新規依存ライブラリ（`dateutil`等）は追加しない（CLAUDE.md「新しい依存ライブラリは原則追加しない」、既存コードにも`dateutil`は無い） |
| V3 | 表示するか否かの決定方式 | **確率方式**を採用（`on_this_day.show_probability`、FLOAT、既定`0.3`＝30%）。既存の「頻度」系設定（通知時刻等）は時刻ベースでこの用途に転用できないため新設。後述V4のハッシュ値と比較するだけの単純な判定にする |
| V4 | 決定的な判定アルゴリズム | `hashlib.sha256(f"on_this_day:{today.isoformat()}".encode()).hexdigest()`の先頭16進8バイトを整数化し`/ 2**64`で`[0, 1)`に正規化した値を使う。Python組込みの`hash()`は`PYTHONHASHSEED`でプロセスごとに変わるため**使用不可**（新規実装、既存コードに類例なし）。同日に複数回呼んでも常に同じ値になることをテストで保証し、「再読み込みで変わらない」要件（受け入れ基準）を満たす。DBへの保存は行わない（CLAUDE.mdの「都度算出」の精神に合わせる。費用の高いAI生成物を再利用する`daily_message`とは性質が異なるため同じ保存方式は採らない） |
| V5 | 複数の候補日がヒットした場合の選定 | 候補（オフセット×ヒットした日×カテゴリ×目標）をすべて列挙し、`f"{record_date}:{category}:{goal_id}"`をキーに同じsha256方式で値を振って最小値の1件を選ぶ（決定的タイブレーク、同日は常に同じ1件になる） |
| V6 | 対象とする「記録」の本文 | 資格試験＝`DailyGoalDiary`（`diary_text_expr()`と同じ優先順：`diary_learned`優先、無ければ`diary_body`）、読書＝`ReadingLog.recall_body`、仕事＝`WorkLog.body`。本文が空文字/NULLの行は対象外（表示する抜粋が無いため）。進捗のみ登録（R-17、数値のみ）は上記本文列を持たないため自然に除外される |
| V7 | 対象とする目標の状態 | 削除済み目標は`goal_service_lifecycle.delete_goal`のカスケード削除（`backend/app/services/goal_service_lifecycle.py`）で日記・想起記録・業務記録を含めて物理削除されDBに残らないため、**追加の除外フィルタなしで「削除した目標の記録は表示しない」を自動的に満たす**。アーカイブ済み（`archived_at IS NOT NULL`）は論理フラグのみで物理データは残るため、通常のJOINで自動的に対象へ含まれる（依頼文要件4「アーカイブ・クローズした目標の記録も対象にする」を満たす）。状態（ACTIVE/PAUSED/CLOSED_WITH_RESULT/CLOSED_WITHOUT_RESULT/DRAFT）は問わない |
| V8 | アプリ全体の値か目標タブ連動か | 依頼文の推奨どおり**アプリ全体の値**とする。`GET /dashboard`のトップレベルに`on_this_day`（nullable、1件のみ）を追加し、`goal_cards`配列には含めない。既存の「直近4週間カレンダー」（`RecentActivityCalendarSection`）・「本日の状態」と同じ、目標タブの切り替えに影響されない非goal-tab連動パターンに倣う |
| V9 | バックエンドの実装場所 | 新規`app/services/on_this_day_service.py`（単一責務）。`milestone_service_common.py`・`roadmap_service.py`と同じ「ダッシュボード派生値を算出する専用サービス」の配置パターンに倣う |
| V10 | 新規テーブル・マイグレーション | **不要**。表示するか否か・どの記録を選ぶかは日付から完全に決定的に算出できるため、永続化すべき新規データが無い（フルスキャンの結論）。既存の`study_log`/`reading_log`/`work_log`/`daily_goal_diary`の読み取りのみで完結する |
| V11 | 性能対策（N+1回避） | 候補日（既定3件：today-12か月／-6か月／-1か月）をまとめて`DailyRecord.record_date.in_(candidates)`で1クエリ取得し、ヒットした`daily_record_id`集合に対してのみ3カテゴリ（`DailyGoalDiary`・`ReadingLog`→`Book`→`Goal`・`WorkLog`→`WorkAssignment`→`Goal`）をJOINする。既存の`_build_goal_card_and_stats`（`app/api/dashboard.py`）と同じ「事前にまとめて取得し辞書で引く」設計に倣う。候補日が3件程度である限り、ダッシュボード初期表示2秒以内の性能要件に実質影響しない |
| V12 | 本文抜粋の文字数既定値 | `on_this_day.body_preview_chars`（INTEGER、既定`100`）。既存の「前回はこう書いていました」ヒント（1.1改28、100文字程度）と揃える |
| V13 | 表示を止める設定 | `on_this_day.enabled`（BOOLEAN、既定`true`）。設定画面の「表示」分類に追加（アクセントカラー・フォントサイズ等と同じ場所） |
| V14 | クリック時の遷移先 | 既存の`ROUTES.dailyReportView(date)`（`/records/{date}/view`）をそのまま使う。新規ルーティング・goal_idクエリパラメータは追加しない（`RoadmapDiagram`の足跡マーク・`GoalConsultationAnswer`の根拠日付・`CalendarPage`の日付クリックがいずれも同じ呼び方をしている既存パターンに合わせる、`frontend/src/constants/routes.ts`） |
| V15 | 「どのくらい前か」の表現 | サーバーは`months_ago`（int）のみを返し、文言（「1年前」「半年前」「Nか月前」）はフロントエンドの純粋関数＋ロケールキーで組み立てる。月次報告の`period_display`等とは異なり、本件は単純な整数から機械的に決まる表現であり、日本語の言い回し（「半年前」等）を含むため**サーバー側で文字列を組み立てるとCODING_RULESのゼロハードコーディング（画面文言はロケールファイルへ）に反する**。英語（`half a year ago`等）も`en.json`側で同様に表現する |
| V16 | エクスポート・バックアップへの追加 | 不要（保存するデータが無いため`DATA_SCHEMA_VERSION`・`backup_service.py`の変更なし。フルスキャンの結論） |
| V17 | 既知の制約（対応は見送り） | SC-08（日次報告閲覧）の目標タブ（`useGoalReportTabs`、`frontend/src/features/record/useGoalReportTabs.ts`）は`status === 'ACTIVE'`の目標のみを選択肢にする。紹介した記録がクローズ/アーカイブ済み目標のもので、かつ同日に別のACTIVE目標の記録もある場合、遷移後にタブで対象目標を選べないことがある。これは本機能が生んだ不具合ではなく既存のSC-08の制約であるため、本件のスコープでは対応しない（§6に既知のリスクとして記載） |
| 版 | バージョン | マイナー機能追加（破壊的変更なし）。`pyproject.toml`の版更新は**リリース手順（`release.bat`）で入力する**（開発中は変更しない） |

## 1. 影響範囲（フルスキャンの結果）

### 1.1 バックエンド

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| 設定キー | `app/constants/app_setting_keys.py` | 4キー追加：`on_this_day.enabled`（BOOLEAN）／`on_this_day.candidate_months_ago`（STRING、カンマ区切り）／`on_this_day.show_probability`（FLOAT）／`on_this_day.body_preview_chars`（INTEGER） |
| 初期データ | `app/init/seed_data.py`（`INITIAL_APP_SETTINGS`） | 上記4キーの既定値投入（既存DBにも不足分のみ投入される既存の仕組みに乗る） |
| 設定サービス | `app/services/settings_service.py`（`OnThisDaySettings`データクラス追加、`AppSettings`・`get_app_settings`・`update_app_settings`へ配線） | `MilestoneThresholdSettings`と同じ配線パターン。検証：`candidate_months_ago`は1以上の整数・昇順・重複禁止、`show_probability`は0.0〜1.0、`body_preview_chars`は1以上 |
| 設定スキーマ | `app/schemas/setting.py` | `OnThisDaySettings`相当のPydanticスキーマ追加 |
| 新規サービス | `app/services/on_this_day_service.py` | `subtract_months`（月差分・クランプ）、`resolve_show_today`（確率判定）、`build_on_this_day`（候補日のまとめ取得→3カテゴリJOIN→決定的選定→`OnThisDayRead`組み立て、enabled=falseなら即None） |
| 新規スキーマ | `app/schemas/dashboard.py` | `OnThisDayRead`（`record_date`・`goal_id`・`goal_name`・`category`・`excerpt`・`months_ago`）を追加し、`DashboardRead`に`on_this_day: OnThisDayRead | None`を追加 |
| 既存API拡張 | `app/api/dashboard.py`（`get_dashboard`、315〜328行目付近） | `on_this_day_service.build_on_this_day(session, today)`の呼び出しを追加し、`DashboardRead`へ`on_this_day`を渡す。既存の`active_goals`（`ai_context_common.list_active_goals`、ACTIVE限定）は使わず、本機能専用に全状態の目標をJOINする |
| テスト | `backend/tests/` | 新規`test_on_this_day_service.py`（決定性・候補日・うるう年・月末・論理日境界・アーカイブ/クローズ対象・削除対象外・空本文除外）、既存`test_api_dashboard.py`・`test_settings_service.py`・`test_api_settings.py`への追加 |

### 1.2 フロントエンド

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| API層 | `frontend/src/types/api.d.ts`（`npm run generate:api-types`で再生成） | `DashboardRead`・`OnThisDayRead`型の反映 |
| 機能 | `frontend/src/features/dashboard/OnThisDaySection.tsx`（新規） | 表示コンポーネント（`on_this_day`がnullなら非表示） |
| 機能（純粋関数） | `frontend/src/features/dashboard/onThisDayLabel.ts`（新規） | `months_ago`→ロケールキー・count解決の純粋関数とテスト（CODING_RULES「フロントの分岐は.tsへ切り出す」） |
| ダッシュボード画面 | `frontend/src/pages/DashboardPage.tsx` | `RecentActivityCalendarSection`と同様の位置（目標タブに依存しないセクション群）に`OnThisDaySection`を追加 |
| 設定画面 | `frontend/src/features/settings/DisplaySection.tsx`（既存、アクセントカラー・フォントサイズ等と同じ場所） | 「過去の記録の表示」トグル（on_this_day.enabled）を追加 |
| 文言 | `frontend/src/locales/ja.json`・`en.json` | `dashboard.onThisDay.*`（見出し・「Nか月前」等のcount文言）、`settings.onThisDay.*`新設 |
| 定数 | `frontend/src/constants/queryKeys.ts` | 変更なし（既存の`QUERY_KEYS.dashboard()`に相乗りするため新規キー不要） |

### 1.3 ドキュメント

| 文書 | 変更 |
| --- | --- |
| `docs/要件定義書_ミチナリ_v1.1.md` | 6.20節（R-148〜）の新設、改訂履歴 |
| `docs/仕様書_ミチナリ_v1.1/03_機能一覧.md` | DSH-10（ダッシュボード表示）・CFG-10（設定） |
| `docs/仕様書_ミチナリ_v1.1/06_画面仕様/6.1_SC-01_ダッシュボード.md`・`6.11_SC-11_設定.md` | 表示要素・設定項目一覧への追記 |
| `docs/仕様書_ミチナリ_v1.1.md` | 改訂履歴 |
| `docs/設計書_データ構造編_ミチナリ_v1.1.md`（5.2設定キー、6.2 API） | 設定キー4件、`GET /dashboard`レスポンス拡張、改訂履歴（新規テーブル無し、`DATA_SCHEMA_VERSION`変更なしを明記） |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1.md` | 新章「1年前の今日の算出ロジック」（決定的選定アルゴリズム・月差分計算・STRIDE）、改訂履歴 |
| `docs/実装フェーズ分割計画書_ミチナリ_v1.1/02_フェーズ一覧.md`・`03_各フェーズの詳細/index.md`・`Phase50.md`（新規） | Phase 50 新設（Phase 49の未反映も合わせて`02_フェーズ一覧.md`へ追記） |
| `docs/OPERATIONS.md`（該当章） | 「表示を止める」設定の案内（必要最小限、閾値運用と同水準） |

### 1.4 既存機能への横展開（同じ問題の有無を確認）

| 項目 | 状況 | 対応 |
| --- | --- | --- |
| `setting_reader.get_int_list`（カンマ区切りリスト、milestoneで確立済み） | 既存関数で足りる | そのまま再利用、重複実装しない |
| `goalCategoryVariant.ts`の`resolveByGoalCategory`パターン | 種別ごとの分岐を網羅性チェックで保証する既存方式 | 抜粋元（diary/recall/work）のカテゴリ分岐に適用 |
| `RecentActivityCalendarSection`の app-wide・非goal-tab連動パターン | 目標に紐づかない値の既存の置き方 | 本機能もこれに倣う（V8） |
| `ROUTES.dailyReportView(date)`（RoadmapDiagram・GoalConsultationAnswer・Calendarが共通利用） | 日付→日次報告閲覧への遷移の既存パターン | そのまま流用（V14） |
| `_build_goal_card_and_stats`の事前集計パターン（N+1対策） | 複数カテゴリをまとめて取得し辞書で引く既存方式 | 候補日のまとめ取得に適用（V11） |

## 2. 現状のベースライン（開発前、2026-11-08、`dev/2026-11-08` ＝ `origin/main` 直後）

工程1の実測で、作業ブランチだった`dev/2026-11-01`では`test_build_package_misc.py::test_run_tests_writes_coverage_data_outside_backend_dir`が1件失敗していた（ローカル共有DBが先行マージ済みのPhase49（復習クイズ）のマイグレーション`fa5a81543844`まで進んでおり、`dev/2026-11-01`の移行連鎖（head=`fd8470506d29`）と不整合だったため）。利用者の指示により、最新化した`main`から`dev/2026-11-08`を新規作成して解消した。以下は`dev/2026-11-08`での再計測値。

- backend `ruff check .`：**All checks passed!**（0件）
- backend `pytest --cov=app`：**2203 passed**, 0 failed（約477秒）。カバレッジ100%（stmt 9506/9506・branch 1738/1738）
- frontend `npx oxlint`：**0件**
- frontend `npx tsc -b`：**0件**
- frontend `npm run test`（vitest + coverage）：**182 files / 1542 tests 全通過**、カバレッジ100%（Statements 2218/2218・Branches 1524/1524・Functions 1010/1010・Lines 2127/2127）
- 既存の失敗・既知の不具合は検出されなかった（Phase49完了直後の状態と一致）

## 3. 作業Todo

凡例：`[ ]` 未着手、`[x]` 完了。各項目の完了条件は「テストが通ること」と「カバレッジ100%（例外処理を除く）」。

### 3.1 事前準備

- [x] P-01 STRIDE分析（新規フィールドのみ、新規エンドポイントは追加しない。結果は直下に記載）（2026-11-08、設計書ロジック・プロンプト編27.6へ正式反映済み）

**STRIDE分析（予定）**：本アプリはローカル単一利用者向け。`GET /dashboard`の既存レスポンスへ`on_this_day`フィールドを1件追加するのみで、新規エンドポイント・新規書き込みは発生しない。

| 脅威 | カテゴリ | 対策 | 実装箇所 |
| --- | --- | --- | --- |
| 削除済み目標の記録が誤って表示される | I | カスケード削除（`goal_service_lifecycle.delete_goal`）により物理的にDBへ残らないことを単体テストで保証（削除後にbuild_on_this_dayを呼び候補に出てこないことを確認） | `on_this_day_service.py`、テスト |
| 他の目標・無関係なgoal_idが混入する表示 | I | 3カテゴリのJOINはいずれも`daily_record_id`→本文テーブル→（book/work_assignment経由で）`goal_id`の一意な経路のみを辿り、クライアントからの入力は一切受け付けない（算出は完全にサーバー内部で完結） | `on_this_day_service.py` |
| 候補日計算のロジックエラーによる将来日・不正な日付の参照 | T | `subtract_months`はサーバーの論理日（`goal_service.resolve_today`）のみを基準にし、結果は常に過去日であることをテストで保証 | `on_this_day_service.py` |
| 本機能の追加クエリによるダッシュボード応答遅延 | D | 候補日3件程度のまとめ取得1クエリ＋ヒット時のみのJOINに限定し、既存の2秒要件を壊さないことを性能観点のレビュー・実測で確認 | `on_this_day_service.py` |
| なりすまし・否認 | S/R | ローカル単一利用者アプリのため対象外（Accept。既存の目標CRUDと同様の前提） | ― |

受容したリスク：S（なりすまし）・R（否認）は、単一利用者・ローカル実行という既存アーキテクチャ全体の前提により対象外とする。

### 3.2 文書改訂

- [x] D-01 要件定義書：6.20節（R-148〜R-153）、改訂履歴（1.1改54）（2026-11-08）
- [x] D-02 仕様書：機能一覧（DSH-10・CFG-10）、画面仕様（6.1.7ダッシュボード・6.11設定）、改訂履歴（1.1改66）（2026-11-08）
- [x] D-03 設計書（データ構造編）：設定キー4件（5.2）、`GET /dashboard`レスポンス拡張（6.2）、改訂履歴（1.1改68）（2026-11-08）
- [x] D-04 設計書（ロジック・プロンプト編）：27章「1年前の今日の算出ロジック」を新設（旧27章「未決事項」は28章へ採番替え）、改訂履歴（1.1改67）（2026-11-08）
- [x] D-05 実装フェーズ分割計画書：Phase 50 新設（`02_フェーズ一覧.md`・`03_各フェーズの詳細/index.md`へのPhase48・49追記漏れも合わせて解消）、改訂履歴（1.1改29）（2026-11-08）
- [x] D-06 OPERATIONS.md：変更不要と判断（既存の復習クイズ機能も同様の判断でOPERATIONS.mdを変更していない。本機能に起動時バックフィル・移行・監視上の特記事項が無く、設定項目は既存の「設定画面から変更可能」という一般的な運用の範囲内のため）（2026-11-08）

### 3.3 バックエンド実装

- [x] B-01 `app_setting_keys.py`に4キー追加＋`seed_data.py`の初期値投入（2026-11-08）
- [x] B-02 `settings_service.py`に`OnThisDaySettings`追加、`AppSettings`/`get_app_settings`/`update_app_settings`へ配線（検証：候補月数の正の整数リスト・重複除去・昇順正規化、確率0.0〜1.0、抜粋文字数1以上）。`schemas/setting.py`にスキーマ追加。テスト4件追加（2026-11-08）
- [x] B-03 `on_this_day_service.py`：`subtract_months`（うるう年・月末クランプ）とテスト（2/29・各月末・1月/13か月前の年跨ぎ等）6件（2026-11-08）
- [x] B-04 `on_this_day_service.py`：`resolve_show_today`（sha256決定的確率判定）とテスト3件（同日複数回呼び出しで同値、確率0/1の境界）（2026-11-08）
- [x] B-05 `on_this_day_service.py`：`build_on_this_day_entry`（候補日まとめ取得→3カテゴリJOIN→決定的選定→`OnThisDayEntry`組み立て、enabled=false・候補0件・本文空のみの場合はNone）とテスト13件（削除済み目標除外・アーカイブ/クローズ済み対象・進捗のみ登録除外・複数ヒット時の決定的選定）。カバレッジ100%（2026-11-08）
- [x] B-06 `schemas/dashboard.py`：`OnThisDayRead`追加、`DashboardRead.on_this_day`追加（2026-11-08）
- [x] B-07 `api/dashboard.py`：`get_dashboard`から`build_on_this_day_entry`を呼ぶ配線。既存の`test_dashboard_returns_empty_lists_when_no_active_goals`を更新（2026-11-08）
- [x] B-08 N+1対策：候補日をまとめて`IN`句で1クエリにし、カテゴリごとに1クエリ（計3クエリ）に限定する設計（27.5）。削除済み目標IDの除外は`test_excludes_deleted_goal`で検証済み（2026-11-08）

### 3.4 フロントエンド実装

- [x] F-01 `npm run generate:api-types`で型再生成（2026-11-08）
- [x] F-02 `features/dashboard/onThisDayLabel.ts`（months_ago→ロケールキー・countの純粋関数）とテスト3件（2026-11-08）
- [x] F-03 `features/dashboard/OnThisDaySection.tsx`（null時非表示、クリックで`ROUTES.dailyReportView`へ遷移）と描画テスト2件（2026-11-08）
- [x] F-04 `DashboardPage.tsx`への組み込み（目標タブに依存しない位置、`RecentActivityCalendarSection`の直後）。`test/fixtures.ts`の`makeDashboard`に既定値追加（2026-11-08）
- [x] F-05 専用の`features/settings/OnThisDaySettingsSection.tsx`を新設（`MilestoneThresholdSection`と同じ「独自のAppSettingsグループは独自のセクション」パターン。`DisplaySection.tsx`への統合はせず）。`onThisDaySettings.ts`（検証ロジック）とテスト11件＋9件を追加し、`SettingsPage.tsx`へ組み込み（2026-11-08）
- [x] F-06 `ja.json`・`en.json`：`dashboard.onThisDay.*`・`settings.onThisDay.*`を追加（`localeKeyUsage.test.ts`のドリフト検出で漏れを検知・修正済み）（2026-11-08）

### 3.5 レビュー・最終確認

- [ ] R-01 `dry-reviewer`・`style-reviewer`・`label-checker`・`performance-reviewer`・`test-coverage-reviewer`を並列実行し指摘を解消
- [ ] R-02 ベースライン（§2）と比較して既存テストの無回帰・テスト件数増減の確認
- [ ] R-03 実機確認手順の作成（§5）

## 4. 処理フロー

1. `GET /dashboard`呼び出し時、`goal_service.resolve_today(session)`で論理日`today`を取得（既存、改修なし）。
2. `on_this_day_service.build_on_this_day(session, today)`を呼ぶ。
   1. `on_this_day.enabled`がfalseなら即`None`を返す。
   2. `resolve_show_today(today)`で当日の表示判定（sha256ベースの決定的確率）を行い、falseなら`None`を返す。
   3. `on_this_day.candidate_months_ago`（既定`"1,6,12"`）の各値について`subtract_months(today, months)`で候補日を算出する。
   4. 候補日の集合で`DailyRecord.record_date.in_(candidates)`を1クエリで取得し、ヒットした`daily_record_id`について3カテゴリ（資格試験の日記・読書の想起記録・仕事の業務記録）をJOINし、本文が空でない行だけを候補として列挙する（削除済み目標は存在しないため自動除外、アーカイブ/クローズ済み目標は対象のまま残る）。
   5. 候補が0件なら`None`を返す。1件以上あれば、決定的タイブレーク（V5）で1件を選ぶ。
   6. 選んだ候補の`record_date`・`goal_id`・`goal_name`・`category`・本文を`on_this_day.body_preview_chars`で切り詰めた抜粋・`months_ago`から`OnThisDayRead`を組み立てて返す。
3. フロントエンドは`on_this_day`がnullでなければ`OnThisDaySection`を表示し、`months_ago`をロケール文言（「1年前」「半年前」「Nか月前」）に変換して表示する。クリックで`ROUTES.dailyReportView(record_date)`へ遷移する。

## 5. 検証の基準

- 候補日に記録がある場合／ない場合の双方で、表示の有無が仕様どおりになること
- 同じ`today`に対して`resolve_show_today`・候補選定が常に同じ結果を返すこと（再読み込みで変わらない要件）
- 2/29（うるう年）・各月末日・1日の境界時刻の前後（論理日の境界）で`subtract_months`・候補日算出が正しく動くこと
- 削除済み目標の記録が候補に出てこないこと、アーカイブ済み・クローズ済み目標の記録は候補に出ること
- 進捗のみ登録（本文なし）の日は候補にならないこと
- `on_this_day.enabled=false`で常に非表示になること
- ダッシュボードのレスポンス時間が既存の性能要件（2秒以内）を壊さないこと（追加クエリが1〜数回に収まることをテストで確認）
- フロントエンド：`months_ago`の境界値（1, 6, 12, 13, 24等）でラベルが正しく出ること、`on_this_day`がnullの場合にセクション自体が非表示になること

## 6. 既知のリスクと対策

| リスク | 対策・方針 |
| --- | --- |
| V17：SC-08の目標タブがACTIVE限定のため、クローズ/アーカイブ済み目標の記録を紹介したときに同日の別ACTIVE目標の内容が既定表示され、紹介した目標のタブを選べないことがある | 既存のSC-08の制約であり本機能が新たに生む不具合ではないため、本件のスコープでは対応しない。将来的にSC-08側でタブの対象をACTIVE限定から広げる別件として切り出す候補とする |
| 確率方式のため、利用者によっては「全く表示されない」期間が運用開始直後に発生し得る（統計的な偶然） | 既定値30%は実用上妥当な頻度と判断（依頼文「毎日は表示しない」を満たす範囲で、極端に低い値は避けた）。利用者は設定画面から調整できる |
| 候補月数リストの件数が増えるとJOIN対象の候補日も増え、将来的に性能要件に影響する可能性 | 既定3件を前提に設計。件数が大きく増える運用は想定しないが、将来必要なら候補日ごとのクエリをバッチ化する設計（V11）のまま件数増にも線形に対応できる |

## 7. 完了の定義

- [ ] §3の全項目が完了している
- [ ] バックエンド`ruff check .`・`pytest --cov-fail-under=100`が通る
- [ ] フロントエンド`oxlint`・`tsc -b`・`npm run test`（カバレッジ100%）が通る
- [ ] §2のベースラインと比較して既存テストが1件も壊れておらず、テスト件数の増減が意図どおりであること
- [ ] §1.3の全ドキュメントが更新されていること
- [ ] 利用者による実機確認（ダッシュボードでの表示・非表示の切り替え、クリックでの遷移、設定画面でのON/OFF）が完了していること

## 8. 作業記録

- 2026-11-08：工程1（前提資料読み込み・ベースライン記録）。`dev/2026-11-01`でベースライン計測中にバックエンドテスト1件が失敗（Alembicリビジョン不整合、`data/michinari.db`がPhase49のマイグレーションまで進んでいたのに対し`dev/2026-11-01`の移行連鎖が追いついていなかったことが原因。コードの不具合ではない）。利用者の指示により、最新化した`main`から`dev/2026-11-08`を新規作成し、ベースラインを再計測して全項目クリアであることを確認した（§2）。工程2（フルスキャン）をサブエージェントに依頼し、影響範囲・新規テーブル不要の結論・決定的アルゴリズムの技術的方針・既存`previous-diary`等の転用可否を確認した。工程3として本文書を作成し、依頼文で委任された論点をすべて確定した（§0）。残っていた未決事項は無かったため、工程4（実装）へ進む。
