# 開発Todo：節目のお祝い（キャラクターの演出）

本書は、記録が節目（連続記録日数・累計記録日数・読書の累計ページ数/読了冊数・資格の教材1周完了/全体進捗率・仕事の記録件数/評価期間完走）に届いたときに、キャラクターと一緒にお祝いする演出を追加する開発作業の正（Single Source of Truth）である。
新フェーズ Phase 48 として実施する。作業は `dev/2026-11-01` で行う。AIは使用しない（AI未設定でも全く同じ動作にする）。

## 0. 決定事項（2026-11-02 時点で確定）

依頼文で「Todoで決める」「検討する」と委任された論点は、フルスキャンの結果（§1）を踏まえて以下のとおり確定する。依頼文に明記済みの前提（キャラクターアイコンを使う／DBに保存する／AI不要）はそのまま採用し、再確認のための質問はしていない。

| # | 決定 | 値・理由 |
| --- | --- | --- |
| M1 | 連続日数の数え方 | **3種別共通で`metrics_service.compute_consecutive_report_days`を使う。** これは`GET /dashboard`が全目標（種別を問わず同一コードパス、`app/api/dashboard.py:268`の`_build_goal_card_and_stats`）に対して呼び、`GoalStatsRead.consecutive_report_days`（文字通り「統計」サマリ）として表示している既存の唯一の連続日数指標であり、依頼文の「既存の統計サマリと合わせる」に最も忠実な選択。`DailyRecord`のカテゴリ別状態列のみを見るため、「何もしていない」記録・予備日（BUFFER/OFF）でも連続記録が維持される（3種別で対称）。**なお、`book_service.get_book_progress`/`work_service.get_work_assignment_progress`が返す`current_streak`は別の指標**（実ログ`ReadingLog`/`WorkLog`とのINNER JOINが前提、ゼロ記録日は途切れる。読書・仕事の進捗表示専用として設計書21.3等に明記された意図的な別定義）であり、節目判定には使わない（前者が「統計サマリ」、後者は「進捗表示の内訳」という役割の違い） |
| M2 | 既に祝った状態の永続化 | 新規テーブル `goal_milestone_achievement`（出来事の記録であり、CLAUDE.mdの「ノルマ・残量・周回等の算出値を保存しない」規約の対象外。理由：これは毎回算出し直せる現在値ではなく、「いつ初めて到達したか」という一度確定したら不変の履歴である） |
| M3 | 節目の閾値の外部化方法 | `app_setting`（`AppSettingValueType.STRING`）にカンマ区切り文字列で保存する新形式を追加する（例：`"3,7,14,30,50,100,200,365"`）。`AppSettingValueType.JSON`は列挙値として存在するが、`settings_service`・`seed_data`・フロント設定画面のいずれにも実装がなく（全70件超の既存設定はSTRING/INTEGER/FLOAT/BOOLEANのみ使用）、本件のためだけに配列型の配線一式を新設するのは過大なため採用しない。新テーブルを閾値保存に使うと「設定」と「履歴」が混在するため、閾値はあくまで設定画面から編集可能な`app_setting`に置き、履歴のみ新テーブルに置く。パース処理は`milestone_service_common.py`に1箇所集約する |
| M4 | 節目の種類・初期閾値 | 依頼文の初期値案を採用し、読書ページ数のみ具体例の先を1つ補う。詳細は§4「閾値一覧」 |
| M5 | 表示手段 | **新規モーダル（既存`Modal.tsx`をラップした`MilestoneCelebrationModal`）。トースト（`Toast.tsx`）は不採用。** 理由：既存トーストは`info`/`error`の2variantのみで4〜8秒で自動消滅する設計であり、「特別感のあるお祝い」を見落とされずに伝える用途に合わない。モーダルは手動で閉じるまで表示し、キャラクター画像を大きく配置できる |
| M6 | 複数の節目が同時到達した場合の表示順 | 1つずつ順番に表示するキュー方式（モーダルを閉じたら次の節目を表示）。一度に全部重ねて表示しない |
| M7 | キャラクター演出の具体像 | **新規イラストは追加しない。** 既存の`achieved`アイコン（紙吹雪・金色基調）は目標「完了」専用のモチーフであり、節目（完了前の途中経過）に転用すると「前倒し≠達成」を明確に区別する既存のアイコン設計思想（アイコンセット仕様書18章）と矛盾する。節目のお祝いでは当該カテゴリの既存アイコン（`exam`/`reading`/`work`）をモーダルに表示し、**CSSアニメーション主体**（画像を使わない紙吹雪風オーバーレイ）で特別感を出す。`prefers-reduced-motion`時は静止表示のみ |
| M8 | AIの使用 | 使用しない。文言はすべて`ja.json`/`en.json`の固定テンプレート（カテゴリ・節目種別ごとの文言キー） |
| M9 | 既存利用者への大量表示防止 | **Alembicマイグレーション自体には業務ロジックを持たせない**（既存の全マイグレーションがスキーマ変更のみという規約に合わせる）。代わりに`app_setting`の一度きりフラグ`milestone.backfill_completed`（BOOLEAN、既定`false`）を新設し、`main.py`の`bootstrap_database()`（`run_all(session)`の直後、既存の`ai_logger.purge_expired`と同じ起動時一括処理の位置）から`milestone_service_common.backfill_achievements_if_needed`を呼ぶ。フラグが`true`なら即return、`false`なら全目標の現在到達済み節目を通常判定と同じ関数で算出し`achieved_at`=`celebrated_at`=現在時刻でINSERTしてフラグを`true`にする（新規インストールでも目標0件のため実質無害に完了する） |
| M10 | 一覧の設置場所 | **分析画面（Analyticsページ）に新規セクションを追加。ダッシュボードには置かない。** 理由：ダッシュボードは初期表示2秒以内の性能要件があり、節目一覧は「振り返り」用途で分析画面の役割に合致する |
| M11 | 道のりマップへの重ね表示 | **本件のスコープ外とする（検討した上で見送り）。** 既存の`feedbackMarks`/`replanMarks`は道のりマップ専用のデータ構造（山・道・足跡それぞれの図形上の位置計算）であり、統合には追加設計が必要になる。後続の開発Todoとして切り出す候補として明記し、本件では分析画面の一覧のみを実装する |
| M12 | データ管理・エクスポートJSONへの含有 | 新規テーブルは全データバックアップ/エクスポート（`Base.metadata`を動的に辿る既存方式）に自動的に含まれるため追加コード不要。`export.py`の`DATA_SCHEMA_VERSION`を`1.5`→`1.6`へ上げる。匿名化ナレッジエクスポート（AI向け、`export_service_*`）には**含めない**（AIの目標相談・日次フィードバックの文脈に不要なため） |
| M13 | 累計ページ数・読了冊数のスコープ | **目標単位ではなく利用者の読書全体（lifetime）の累計とする。** `Book.goal_id`にUNIQUE制約があり1目標=1冊のため、「累計ページ数」「読了冊数」は1冊の範囲では意味が小さい（依頼文の閾値例`500・1000・3000…`は複数冊分を想定した値）。読了冊数＝`category=READING`かつ`status=CLOSED_WITH_RESULT`の目標数（`goal_service_lifecycle.py`の既存の「読了」概念と同じ）、累計ページ数＝全READING目標の書籍の現在ページの合計（`book_service.py`に`count_completed_books`・`sum_cumulative_pages_read`を新規追加）。**既知の簡略化**：`GoalMilestoneAchievement.goal_id`は到達を検知した「そのときに記録していた目標」に紐付ける（lifetime集計のため本来は特定の1目標に属さないが、スキーマを複雑にしない簡略化。分析画面の一覧はその目標の下にのみ表示される。§6リスクに記載） |
| M14 | 資格「教材1周完了」の一意性 | `(goal_id, material_id, cycle_number)`を節目キーとし、`cycle_service`で`current_cycle`が増えた時点を検知する。同じ周回を二重に祝わないよう一意制約で保証する |
| M15 | バックエンドのファイル分割方針 | `CONSECUTIVE_DAYS`/`TOTAL_RECORD_DAYS`は3種別共通（M1）のため`milestone_service_common.py`が判定も担う。種別固有の判定（読書のページ数/冊数、資格の周回/進捗率、仕事の件数/評価期間）は内容が大きく異なるため、置き場所ルール（CODING_RULES.md）の分割規約に従い`milestone_service_exam.py`／`milestone_service_reading.py`／`milestone_service_work.py`へ分ける（4ファイル構成） |
| M16 | 文言のトーン | 「〇日連続記録、達成おめでとうございます」等、継続を褒める表現のみ。途切れ・失敗を示す語（「途切れました」等）は使わない | 
| 版 | バージョン | マイナー機能追加（破壊的変更なし）。`pyproject.toml`の版更新は**リリース手順（`release.bat`）で入力する**（開発中は変更しない） |

## 1. 影響範囲（フルスキャンの結果）

### 1.1 バックエンド

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| 列挙 | `app/constants/enums.py` | `MilestoneType`（StrEnum）新設：`CONSECUTIVE_DAYS`/`TOTAL_RECORD_DAYS`/`READING_TOTAL_PAGES`/`READING_COMPLETED_BOOKS`/`EXAM_MATERIAL_CYCLE_COMPLETED`/`EXAM_OVERALL_PROGRESS`/`WORK_RECORD_COUNT`/`WORK_EVALUATION_PERIOD_COMPLETED` |
| 設定キー | `app/constants/app_setting_keys.py` | 6キー追加（§4の閾値一覧）。カンマ区切り文字列を保存する初の`app_setting`（`AppSettingValueType.STRING`） |
| 設定読み出し | `app/services/setting_reader.py` | `get_int_list`追加（カンマ区切りの共通パース。重複箇所を作らない） |
| 設定サービス | `app/services/settings_service.py`（`MilestoneThresholdSettings`追加、`AppSettings`・`get_app_settings`・`update_app_settings`・`_update_milestone_thresholds`） | 仕様書6.11「全ての設定項目は画面上から変更可能」を満たすため、既存の`threshold`等と同じ配線パターンで追加。カンマ区切りの検証（整数のみ・昇順・重複禁止）を行う |
| 設定スキーマ | `app/schemas/setting.py` | `MilestoneThresholdSettings`相当のPydanticスキーマ追加 |
| モデル | 新規 `app/models/milestone.py` | `GoalMilestoneAchievement`（`id`, `goal_id` FK, `milestone_type`, `milestone_key`, `achieved_at`, `celebrated_at` nullable, 一意制約`(goal_id, milestone_type, milestone_key)`） |
| マイグレーション | `backend/alembic/versions/`（新規リビジョン、head=`4e665f950a10`から連番） | `create_table`のみ（既存テーブル変更なし、CODING_RULESの「既存データに対する安全性」テスト対象外）。業務ロジックは持たせない（M9） |
| 起動時バックフィル | `app/main.py`（`bootstrap_database`）、`app/constants/app_setting_keys.py`（`MILESTONE_BACKFILL_COMPLETED`追加）、`app/init/seed_data.py`（既定値`false`を追加） | `run_all(session)`の直後で`milestone_service_common.backfill_achievements_if_needed`を呼ぶ（M9） |
| 新規サービス | `app/services/milestone_service_common.py`（閾値パース、CRUD、未祝い一覧取得、祝い済み更新、バックフィル、`CONSECUTIVE_DAYS`/`TOTAL_RECORD_DAYS`の判定＝`metrics_service.compute_consecutive_report_days`呼び出し＋`DailyRecord`の累計REPORTED件数カウント）／`milestone_service_exam.py`（`cycle_service`/`metrics_service`を使い教材1周完了・全体進捗率を判定）／`milestone_service_reading.py`（`book_service`を使い累計ページ数・読了冊数を判定）／`milestone_service_work.py`（`work_service`を使い記録件数・評価期間完走を判定） | 種別固有の判定ロジックを追加。共通部分は`milestone_service_common.py`が一括で担う |
| 既存サービス拡張 | `app/services/book_service.py` | `count_completed_books`・`sum_cumulative_pages_read`追加（lifetime集計、M13） |
| 既存サービス拡張 | `app/services/export.py` | `DATA_SCHEMA_VERSION`を`1.6`へ（M12） |
| 新規API | `app/schemas/milestone.py`、`app/api/milestones.py`（`GET /goals/{goal_id}/milestones`＝全履歴一覧、`GET /goals/{goal_id}/milestones/pending-celebrations`＝未お祝いの節目〈読み取りのみ、副作用なし〉、`POST /goals/{goal_id}/milestones/{milestone_id}/celebrate`＝お祝い済みにする）、`app/main.py`（登録） | 追加 |
| 既存API拡張 | `app/api/records.py`（記録確定エンドポイント） | 記録確定の直後に新規到達節目を判定するトリガー呼び出しを追加（既存のレスポンスへ影響を与えず、別エンドポイントで取得させる設計のため変更は呼び出し追加のみ） |
| テスト | `backend/tests/` | 新規（`test_milestone_service_*.py`、`test_api_milestones.py`、マイグレーションの適用テスト） |

### 1.2 フロントエンド

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| API層 | `src/api/milestones.ts`（新規）、`src/types/api.d.ts`（`npm run generate:api-types`で再生成） | 追加 |
| 機能 | `src/features/milestone/`（新規：`MilestoneCelebrationModal.tsx`、`useMilestoneCelebrationQueue.ts`、`milestoneContent.ts`（種別→文言キー・アイコンの対応、純粋関数）） | 追加 |
| 記録確定フロー | `src/features/record/`（日次報告の確定処理フック、`useZeroRecordAction.ts`も含む） | 確定直後に未お祝いの節目を取得してモーダルキューに積む呼び出しを追加 |
| 分析画面 | `src/pages/AnalyticsPage.tsx`またはその配下の機能コンポーネント | 「節目の記録」セクション新設（一覧表示） |
| 定数 | `src/constants/characterIcons.ts` | 変更なし（既存アイコンを再利用、確認のみ） |
| 設定画面 | `src/features/settings/`（閾値編集欄一式、`assistantFields.ts`等の既存パターンに合わせる） | 仕様書6.11「全ての設定項目は画面上から変更可能」を満たすため、6閾値（カンマ区切りテキスト欄）を追加 |
| 定数 | `src/constants/queryKeys.ts` | 節目関連のクエリキー追加 |
| 文言 | `src/locales/ja.json`・`en.json` | `milestone.*`名前空間新設（カテゴリ×節目種別の文言、分析画面の見出し等） |
| アニメーション | 新規CSS（`prefers-reduced-motion`分岐） | 紙吹雪風オーバーレイ |

### 1.3 ドキュメント

| 文書 | 変更 |
| --- | --- |
| `docs/要件定義書_ミチナリ_v1.1.md` | 新規節（R-132〜）、改訂履歴 |
| `docs/仕様書_ミチナリ_v1.1/`（該当章） | 機能一覧表、画面仕様（分析画面・モーダル）、改訂履歴 |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1.md` | 処理フロー（§4相当） |
| `docs/設計書_データ構造編_ミチナリ_v1.1.md` | 設定キー、`goal_milestone_achievement`、`DATA_SCHEMA_VERSION`改訂、改訂履歴 |
| `docs/実装フェーズ分割計画書_ミチナリ_v1.1/`（該当ファイル） | Phase 48 の追加 |
| `docs/OPERATIONS.md`（該当章） | 閾値の運用（設定画面からの変更手順）、既存利用者への移行時バックフィルの説明 |

### 1.4 既存機能への横展開（同じ問題の有無を確認）

| 項目 | 状況 | 対応 |
| --- | --- | --- |
| 連続日数の指標が2種類存在する（`GoalStatsRead.consecutive_report_days`＝統計サマリ、`BookProgress`/`WorkAssignmentProgress`の`current_streak`＝進捗表示の内訳） | 両者は設計書に明記された別目的の指標（§0 M1） | 節目判定は統計サマリ側（`compute_consecutive_report_days`）のみを使い、混同しない |
| `goalCategoryVariant.ts`の`resolveByGoalCategory`パターン | 種別ごとの分岐をTypeScriptの網羅性チェックで保証する既存方式 | 節目の文言・アイコン対応にも同パターンを使う（追加漏れをコンパイルエラーで検知） |
| `app_setting_keys.py`の`_reading`/`_work`接尾辞命名 | 種別ごとに値を分ける既存命名規則 | 新設する閾値キーも同命名規則に従う（§4） |
| 「一度だけ表示」のUI実装（`AutostartBanner.tsx`の`*_dismissed`フラグ） | グローバル1フラグ方式で、目標・節目ごとの多値管理には使えない | 採用しない。新規テーブル（M2）で個別に管理する |

## 2. 現状のベースライン（開発前、2026-11-02、調査エージェントによる実測）

- backend `ruff check .`：**All checks passed!**（0件）
- backend `pytest`（カバレッジ計測込み）：**2098 passed**, 0 failed（約817秒）。カバレッジ100%（stmt 8965/8965・branch 1662/1662）
- frontend `npx oxlint`：**0件**
- frontend `npx tsc -b`：**0件**
- frontend `npm run test`（vitest + coverage）：**171 files / 1468 tests 全通過**、カバレッジ100%（Statements/Branches/Funcs/Lines）
- 既存の失敗・既知の不具合は検出されなかった（道のりマップPhase47完了直後の状態と一致）

## 3. 作業Todo

凡例：`[ ]` 未着手、`[x]` 完了。各項目の完了条件は「テストが通ること」と「カバレッジ100%（例外処理を除く）」。

### 3.1 事前準備

- [x] P-01 `/threat-model` でSTRIDE分析（新規APIエンドポイント・新規テーブルが対象、結果は直下に記載）

**STRIDE分析結果（2026-11-02）**：本アプリはローカル単一利用者向け（`User`モデルが存在せず、マルチテナント境界が無い）。新規3エンドポイント（`GET /goals/{goal_id}/milestones`・`GET /goals/{goal_id}/milestones/pending-celebrations`・`POST /goals/{goal_id}/milestones/{milestone_id}/celebrate`）は既存の目標CRUDと同じ信頼境界（ブラウザ↔localhost限定のFastAPI）に収まる。

| 脅威 | カテゴリ | 対策 | 実装箇所 |
| --- | --- | --- | --- |
| 存在しない`goal_id`/`milestone_id`の指定による予期しない情報露出 | T/I | 既存の目標取得パターンに合わせ、存在しない場合はドメイン例外→404（他画面と同一のエラー変換経路） | `api/milestones.py` |
| クライアントから`achieved_at`等の計算値を直接書き込めること | T | `POST /goals/{goal_id}/milestones/{milestone_id}/celebrate`は`celebrated_at`のみサーバー側で更新し、他フィールドはリクエストボディで受け取らない（判定・算出はサーバー側の`milestone_service_*`のみが行う）。到達判定自体は`finalize`系POSTの副作用として行い、GETに副作用を持たせない | `api/milestones.py`、`api/records.py`、`schemas/milestone.py` |
| 記録確定ごとの節目判定によるDoS相当の負荷増 | D | 既存のstreak/進捗算出関数を1回呼ぶのみで軽量。ダッシュボードの2秒要件には含めない（記録確定後の別エンドポイントでのみ発生） | `milestone_service_common.py` |
| エクスポートJSON経由の情報漏洩 | I | 新規テーブルの内容は進捗情報のみで機密性は既存の目標データと同水準。既存の全データエクスポート（ローカルファイルのみ、外部送信なし）と同じ扱いとし追加対策なし（Accept） | `export.py` |
| なりすまし・否認 | S/R | ローカル単一利用者アプリのため対象外（Accept。既存の目標CRUDも同様の前提） | ― |

受容したリスク：S（なりすまし）・R（否認）は、単一利用者・ローカル実行という既存アーキテクチャ全体の前提により対象外とする。

### 3.2 文書改訂

- [ ] D-01 要件定義書：新規節（R-132〜）、改訂履歴
- [ ] D-02 仕様書：機能一覧、画面仕様（分析画面セクション・モーダル）、改訂履歴
- [ ] D-03 設計書（ロジック・プロンプト編）：処理フロー、改訂履歴
- [ ] D-04 設計書（データ構造編）：設定キー、`goal_milestone_achievement`、`DATA_SCHEMA_VERSION`、改訂履歴
- [ ] D-05 実装フェーズ分割計画書：Phase 48
- [ ] D-06 OPERATIONS.md：閾値の運用、移行時バックフィルの説明

### 3.3 バックエンド実装

- [ ] B-01 `enums.py`に`MilestoneType`追加
- [ ] B-02 `app_setting_keys.py`に閾値6キー追加＋`seed_data.py`の初期値投入（既存DBにも不足分のみ投入される既存の仕組みに乗せる）
- [ ] B-02b `setting_reader.py`に`get_int_list`追加。`settings_service.py`に`MilestoneThresholdSettings`を追加し`AppSettings`/`get_app_settings`/`update_app_settings`へ配線（カンマ区切りの検証：整数のみ・昇順・重複禁止）。`schemas/setting.py`にスキーマ追加
- [ ] B-03 `models/milestone.py`：`GoalMilestoneAchievement`モデル
- [ ] B-04 マイグレーション：`create_table`のみ（業務ロジックを持たせない、M9）
- [ ] B-05 マイグレーションの適用テスト（既存データ＝他テーブルの既存行がある状態で適用し、エラーにならず既存行が保持されることを確認。新規テーブルのみの追加のため`CODING_RULES.md`の対象外だが、念のため確認する）
- [ ] B-06 `milestone_service_common.py`：閾値パース、`GoalMilestoneAchievement`のCRUD、未祝い一覧取得、祝い済み更新、`backfill_achievements_if_needed`（起動時バックフィル、M9）、`CONSECUTIVE_DAYS`/`TOTAL_RECORD_DAYS`の判定（3種別共通、`metrics_service.compute_consecutive_report_days`＋累計REPORTED件数カウント）
- [ ] B-06b `app_setting_keys.py`に`MILESTONE_BACKFILL_COMPLETED`追加＋`seed_data.py`の初期値（`false`）投入、`main.py`の`bootstrap_database`から`backfill_achievements_if_needed`を呼ぶ配線＋テスト（既存目標がある状態での初回起動で大量表示されないことを検証）
- [ ] B-07 `milestone_service_exam.py`：全体進捗率・教材1周完了の判定（連続/累計記録日数はB-06の共通判定を利用）
- [ ] B-08 `milestone_service_reading.py`：累計ページ数・読了冊数の判定（連続/累計記録日数はB-06の共通判定を利用）
- [ ] B-09 `milestone_service_work.py`：記録件数・評価期間完走の判定（連続/累計記録日数はB-06の共通判定を利用）
- [ ] B-10 `book_service.py`に`count_completed_books`・`sum_cumulative_pages_read`追加（lifetime集計、M13）
- [ ] B-11 `api/records.py`の3つのfinalize系POST（`finalize_record`／`finalize_reading_record`／`finalize_work_record`）から、既存の`session.commit()`より前に対象カテゴリのACTIVE目標それぞれへ`milestone_service_common.detect_and_record_new_achievements`を呼ぶ（GETには副作用を持たせない。確定処理自体のレスポンスは変えない）
- [ ] B-12 `schemas/milestone.py`、`api/milestones.py`（`GET /goals/{goal_id}/milestones`＝全履歴、`GET /goals/{goal_id}/milestones/pending-celebrations`＝未お祝い〈読み取りのみ〉、`POST /goals/{goal_id}/milestones/{milestone_id}/celebrate`の3エンドポイント）、`main.py`登録
- [ ] B-13 `export.py`の`DATA_SCHEMA_VERSION`を`1.6`へ
- [ ] B-14 セキュリティテスト：他者の目標IDを指定した節目取得・お祝い済み更新の認可境界（目標の所有確認）

### 3.4 フロントエンド実装

- [ ] F-01 `api/milestones.ts`、型の生成し直し（`npm run generate:api-types`）
- [ ] F-02 `features/milestone/milestoneContent.ts`（種別→文言キー・アイコンの純粋関数、`resolveByGoalCategory`パターン）とテスト
- [ ] F-03 `MilestoneCelebrationModal.tsx`（キャラクターアイコン表示、CSSアニメーション、`prefers-reduced-motion`分岐）と描画テスト
- [ ] F-04 `useMilestoneCelebrationQueue.ts`（複数到達時のキュー管理）とテスト
- [ ] F-05 記録確定フローへの組み込み（確定直後に未お祝い節目を取得→キューへ）
- [ ] F-06 分析画面：「節目の記録」セクション（一覧表示）と描画テスト
- [ ] F-07 `ja.json`・`en.json`：`milestone.*`文言（カテゴリ×節目種別、途切れを責めない表現）
- [ ] F-08 `queryKeys.ts`：節目関連キー追加
- [ ] F-08b 設定画面：節目閾値6件の編集欄（カンマ区切りテキスト、既存の`assistantFields.ts`等と同じ配線パターン）とテスト
- [ ] F-09 `npm run lint`（warn 0件）・`tsc -b`・`npm run test`の閾値確認

### 3.5 検証

- [ ] V-01 ruff・pytest・vitest（新規機能のカバレッジ100%。全体の最終実行は§8）
- [ ] V-02 既存DBからのアップグレード確認：利用者DBのコピーで、既存目標が持つ到達済み節目が大量表示されず「お祝い済み」として記録されること（受け入れ基準の核心）
- [ ] V-03 3種別それぞれで、節目に届いたときに一度だけお祝いが表示されることを実機（またはE2E相当のシナリオテスト）で確認
- [ ] V-04 AI未設定環境での動作確認（固定文言のみで完結すること）
- [ ] V-05 配布物への同梱確認（`backend/tests/test_build_package.py`、Dockerは使わない）
- [ ] V-06 フルスキャンの再確認（横展開：データ管理・エクスポートJSON、既存の呼び出し経路）

## 4. 処理フロー（確定版）

1. 記録確定（資格・読書・仕事いずれかの`finalize`系POST）が成功すると、既存の`session.commit()`の前に、対象カテゴリのACTIVE目標それぞれについて`milestone_service_common.detect_and_record_new_achievements`を呼ぶ（確定処理と同じトランザクション。確定処理自体のレスポンスは変えない）。
2. この関数は`milestone_service_common.py`で3種別共通の`CONSECUTIVE_DAYS`/`TOTAL_RECORD_DAYS`を判定し、対象目標のカテゴリに応じた`milestone_service_<category>.py`で種別固有の節目（`metrics_service`/`book_service`/`work_service`/`cycle_service`の既存算出関数を利用）を判定し、§4閾値一覧と比較する。
3. 到達済みだが`GoalMilestoneAchievement`に未登録の節目があれば、`achieved_at`=現在時刻・`celebrated_at`=NULLで新規登録する（finalize系POSTの副作用としてここで確定。以降のGETはこの結果を読むだけ）。
4. フロントエンドは記録確定の成功後に`GET /goals/{goal_id}/milestones/pending-celebrations`（読み取りのみ、副作用なし）を呼び、返された節目をキューに積んで1件ずつ`MilestoneCelebrationModal`で表示する（閾値の種別とカテゴリから`milestoneContent.ts`が文言・アイコンを解決）。
5. 利用者がモーダルを閉じるたびに `POST /goals/{goal_id}/milestones/{milestone_id}/celebrate` を呼び、`celebrated_at`を記録する。キューの次の節目があれば表示する。
6. 分析画面の「節目の記録」セクションは `GET /goals/{goal_id}/milestones` で全履行済み節目（お祝い済み・未済問わず）を取得して一覧表示する。
7. 起動時バックフィル（`bootstrap_database`、`milestone.backfill_completed`が`false`の間のみ）：全目標について現在到達している節目を一括算出し、`achieved_at`=`celebrated_at`=起動時刻で登録してフラグを`true`にする（以後の新規お祝いはこの初回起動より後に新たに到達する節目のみになる）。

### 閾値一覧（初期値、すべて`app_setting`の`AppSettingValueType.STRING`・カンマ区切り）

| キー | 対象 | 初期値 |
| --- | --- | --- |
| `milestone.consecutive_days_thresholds` | 3種別共通・連続記録日数 | `3,7,14,30,50,100,200,365` |
| `milestone.total_record_days_thresholds` | 3種別共通・累計記録日数 | `10,30,100,365` |
| `milestone.reading_total_pages_thresholds` | 読書・累計ページ数 | `500,1000,3000,5000,10000` |
| `milestone.reading_completed_books_thresholds` | 読書・読了冊数 | `1,3,5,10` |
| `milestone.exam_overall_progress_thresholds` | 資格・全体進捗率(%) | `25,50,75` |
| `milestone.work_record_count_thresholds` | 仕事・記録件数 | `10,50,100` |

資格の「教材1周完了」・仕事の「評価期間を通して記録し続けたこと」は閾値を持たないイベント型のため、設定キーを持たない（§0 M14、該当時点で都度1件のみ記録）。

## 5. 検証の基準

| 指標 | 基準 |
| --- | --- |
| 同一節目の重複お祝い表示 | 0件（一意制約＋`celebrated_at`判定で保証） |
| 既存利用者の移行直後の一括表示件数 | 0件（バックフィルにより全て祝い済みとして記録） |
| AI未設定環境での動作差異 | 無し（固定文言のみで完結） |
| `prefers-reduced-motion`時のアニメーション再生 | 無し（静止表示のみ） |
| 新規追加コードのカバレッジ | 100%（例外処理を除く） |

## 6. 既知のリスクと対策

| リスク | 対策 |
| --- | --- |
| 移行時バックフィルの計算が既存のstreak/進捗算出と食い違い、過去に到達済みの節目が「新規到達」と誤判定される | バックフィルも通常判定と同じ`milestone_service_*`の判定関数を呼ぶ（判定ロジックを2つ持たない） |
| 記録確定の都度、節目判定でDBクエリが増え記録確定のレスポンスが遅くなる | 判定は既存のstreak/進捗算出関数の再利用のみ（N+1を避け、目標1件につき必要な集計を1回で取得）。ダッシュボードの初期表示（2秒以内要件）には判定を入れない（記録確定後の別エンドポイントでのみ発生） |
| 複数の節目に同時到達した際にモーダルが連続表示され体験を損ねる | キュー方式（M6）で1件ずつ表示 |
| カンマ区切り文字列のパース失敗（運用で不正な値を設定画面に入力） | `milestone_service_common.py`でパース失敗時は該当閾値を無視してログに記録し、機能全体を停止させない |
| `DATA_SCHEMA_VERSION`更新漏れによる旧バージョンとの非互換エクスポート | `export.py`の改訂履歴コメントに追記し、テストで版数と`_IMPORTABLE_SCHEMA_VERSIONS`の整合を確認 |
| 読書の累計ページ数・読了冊数（lifetime集計、M13）が「記録していた目標」に紐付くため、過去に読了した別の本（別目標）を見返しているときにその節目の記録が表示されない | 受容する（既知の簡略化。スキーマに`category`列やnullable `goal_id`を追加して利用者全体の節目として扱う案は本件の範囲外とし、後続の開発Todoの候補として記録） |

## 7. 完了の定義

- 全項目（§3）が `[x]` になり、テストが通る（バックエンド・フロントエンドとも）。
- カバレッジは例外処理を除き100%。
- §5 の基準を満たす。
- 受け入れ基準（依頼文）を全て満たす：3種別それぞれで節目到達時に一度だけお祝いが表示される／既存利用者の更新直後に大量表示されない／AI未設定でも同じ動作。
- 文書（§1.3）が実装と一致する。

## 8. 作業記録

（作業の進行に応じて追記する）
