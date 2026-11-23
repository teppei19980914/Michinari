# 開発Todo：スケジュール・ガントチャート機能 単位3（スケジュールタブ：表・ガント・固定） v1.0

入力: `docs/開発Todo_スケジュール・ガントチャート_v1.1.md`（第2章・第3章・第6章・第9章単位3・第10章・第15章）、`docs/開発Todo_スケジュール・ガントチャート_単位1_v1.0.md`・`docs/開発Todo_スケジュール・ガントチャート_単位2_v1.0.md`（引き継ぎ事項）。

## 0. ベースライン（着手前に確認）

- 前提確認：単位1（祝日基盤、PR#145）・単位2（データモデルとAPI、PR#146）はいずれも実装済み・`main`にマージ済み（`git merge-base dev/2026-11-23 main` で現HEADがmainの祖先であることを確認済み）。`GET/PUT /goals/{goal_id}/schedule`・`PUT .../view-setting`・`GET /holidays`が利用可能。
- backend: `ruff check .` → All checks passed。`pytest` → 2804 passed, coverage 100%（322.06s）。
- frontend: `npm run lint`（oxlint、`DayTypeDefaultsCard.tsx`のmax-lines-per-function警告1件のみ。単位1由来の既知の警告で本単位の範囲外）・`npm run build`（tsc -b + vite build, exit 0）・`npm test -- --run`（231 files, 1839 tests, coverage100%, exit 0）。

## 1. 脅威分析（STRIDE、簡易）

`/threat-model`スキルが本セッションで利用不可のため、単位1・単位2と同様に手動でSTRIDE分析を実施。

- **データフロー**：[利用者（ローカル単独利用）] → ブラウザ（React SPA、本単位の新規コード） → 単位2で実装済みの`GET/PUT /goals/{goal_id}/schedule`・`PUT .../view-setting`・`GET /holidays`（HTTP、信頼境界） → 既存のサービス層（検証）→ DB
- **S（なりすまし）**：既存の認証機構と同一。本単位で新たな認証経路は追加しない。対象外。
- **T（改ざん）**：
  - 入力検証の最終判定は単位2で実装済みのサーバー側（`schedule_service`）に委ねる（本書6.1）。本単位のフロントエンドの検証（`scheduleValidation.ts`）はあくまで入力中の即時フィードバック用であり、保存は必ずサーバー検証を経る。
  - 利用者が入力した文字列（作業項目・作業内容・追加列名・セルの値・却下理由等）はReactの標準のテキスト描画（JSX中の`{value}`）でエスケープされる。生HTML描画用の特別prop（CLAUDE.md10章・本書10章で使用禁止と明記されているもの）は使用しない。
  - 新規追加する`ScheduleRead`の4フィールド（`max_items`等）は表示用の設定値で、改ざんされても実害はない（保存時の上限チェックはサーバー側`save_schedule`が別途行う、単位2実装済み）。
- **R（否認）**：単位2で実装済みの`schedule_item_history`が更新履歴を記録する。本単位はフロントエンドのみで新たな否認リスクの導線を追加しない。
- **I（情報漏洩）**：`GET /goals/{goal_id}/schedule`は対象目標のみを返す仕様は単位2で確認済み。フロントエンドのルーティング（`/goals/:id`）が`goalId`をそのままAPIへ渡すのみで、新たな漏洩経路は増えない。
- **D（サービス拒否）**：100行×数百日のデータでの描画・スクロールが重くなることがDoS相当のリスク（本書3.4）。「1日ごとのセルをDOMに並べない」設計（3章参照）で対策する。横展開チェック・パフォーマンスチェック（15.1手順13）で確認する。
- **E（権限昇格）**：フロントエンドは単位2のAPIが行う所有者検証（revision・ID所有者チェック）に依存するのみで、新規の認可ロジックは追加しない。

対策はすべてMitigate実装済み（単位2のサーバー側検証に依拠、本単位はDoS対策の描画設計のみ新規）。受容したリスクなし。

## 2. 報告が必要な食い違い（15.1手順5、判断は仰ぐが実装は止めない）

いずれも「仕様の意図自体は変わらない、実装の詳細で吸収できる」と判断し、単位1・単位2の前例（`DATA_SCHEMA_VERSION`のズレ等、判断を仰ぐために実装を止めるべき食い違いではないと判断したもの）に倣って対応しつつ報告する。

1. **本書3.4「予定日が未入力の行は、表には表示するがガントには描かない」は、本書7.1・D-09（予定開始日・予定終了日は必須、`schedule_item`テーブルはNOT NULL、単位2で実装済み・マイグレーション済み）と矛盾する。** 予定日が未入力の行はデータモデル上存在し得ない（APIが返す`ScheduleItemRead.planned_start_date`/`planned_end_date`は必須フィールド）。単位2のスキーマ変更は本単位の範囲外であり、ここで必須性を緩めることはしない。したがって3.4のこの一文は到達不能な分岐を指しており、**ガント側に「予定日未入力」の特別処理は実装しない**（全行が必ず予定帯を持つ前提で実装する）。
2. **`ScheduleRead`に、画面側が必要とする内部パラメータ（`schedule.max_items`・`max_custom_columns`・`gantt_day_width_min/max_rem`）が含まれていない。** 単位2時点では画面を持たないため未配線だった。本書7.4・D-14・D-20の「app_settingで管理する」を画面へ反映するため、単語帳機能の前例（`VocabDeckRead.session_default_questions`/`session_max_questions`、設計書データ構造編1.1改75）に倣い、`ScheduleRead`へ読み取り専用の4フィールドを追加する（4章・6章参照）。新規テーブル・新規カラムは無く、`DATA_SCHEMA_VERSION`への影響もない。
3. **`schedule.gantt_day_width_min_rem`/`max_rem`（1.75/4.5、単位2で暫定値として投入済み）は、本単位の影響範囲確定時にフォント・セル余白を実際に見て妥当性を見直す予定だった（単位2引き継ぎ事項）。** 見直した結果、2桁の日付数字（例: "23"、本文文字サイズ0.75rem想定）＋左右パディング0.25rem×2の下限として1.75rem、月初等に月表記を追加表示する際の上限として4.5remは現行値のままで妥当と判断し、**値は変更しない**。

## 3. 影響範囲表

### 3.1 backend（小規模な追加のみ。データモデル自体は単位2で完結済み）

| ファイル | 変更内容 | 理由 | D-ID |
| --- | --- | --- | --- |
| `backend/app/schemas/schedule.py` | `ScheduleRead`へ`max_items`・`max_custom_columns`・`gantt_day_width_min_rem`・`gantt_day_width_max_rem`を追加 | 2章食い違い2。画面が上限・ガント幅レンジを知る手段が無かった | D-14,D-20 |
| `backend/app/api/schedule.py` | `_serialize_view`で上記4値を`setting_reader.get_int`/`get_float`で読み取りセット | 同上 | D-14,D-20 |
| `backend/tests/test_api_schedule.py` | 既存の`GET /goals/{goal_id}/schedule`テストへ4フィールドのアサーションを追加 | 回帰防止 | D-14,D-20 |
| `frontend/src/types/api.d.ts` | `npm run generate:api-types`で再生成 | 手書き禁止 | — |
| `docs/設計書_データ構造編_ミチナリ_v1.1.md` 改訂履歴（改78）・6.API設計 | `ScheduleRead`のフィールド追加を記録 | D-49 | — |

### 3.2 frontend（新規：共通ユーティリティ）

| ファイル | 変更内容 | 理由 | D-ID |
| --- | --- | --- | --- |
| `frontend/src/utils/dateRange.ts`（新規） | `ganttGeometry.ts`から`daysBetween`を切り出し | 3.4「日付の差の計算など共通にできる部分だけを切り出す」。デグレ禁止のため既存`ganttGeometry.test.ts`（6件）を変更前後で無変更のまま通す | 3.4 |
| `frontend/src/utils/dateRange.test.ts`（新規） | `daysBetween`の直接テスト | 共通化した関数の単体テスト | — |
| `frontend/src/features/analytics/ganttGeometry.ts` | `daysBetween`を`utils/dateRange`からimportするよう変更。それ以外のロジック（百分率方式）は無変更 | 共通化。既存の教材ガント（ANL-04）の表示は変えない | 3.4 |

### 3.3 frontend（新規：`frontend/src/features/schedule/`ディレクトリ）

既存の`features/vocab/`（35ファイル、フラット配置）を前例とし、同様にフラット配置する。

| ファイル | 内容 | 理由 | D-ID |
| --- | --- | --- | --- |
| `scheduleColumnLayout.ts`＋test | 既定7列＋追加列の列定義（key・labelKey・幅rem）、行操作列を含めた固定列のsticky left offset算出（`frozen_column_count`・`readOnly`で可変） | D-08,D-13,D-15,D-24,D-25 |
| `scheduleGanttGeometry.ts`＋test | 表示期間（全行の予定・実績・本日のうち最早〜最遅）算出、1日分の幅算出（コンテナ幅÷期間日数をmin/max remへクランプ）、帯のleft/width算出（rem）、本日線位置算出、土日祝の連続区間の圧縮（日ごとではなく区間単位でoverlay用の矩形リストを作る） | D-17,D-19,D-20,D-22,D-23 |
| `scheduleDelay.ts`＋test | 遅れ日数算出（未完了&本日>予定終了日→本日－予定終了日、完了&実績終了日>予定終了日→実績終了日－予定終了日）、警告印の要否判定 | D-18,3.4 |
| `scheduleValidation.ts`＋test | 本書6.2のクライアント側ミラー（1行分の検証、サーバーと同じルール。最終判定はサーバー、本書6.1） | D-09,D-10,D-11,6.2 |
| `scheduleStatusAutoFill.ts`＋test | 本書6.3の実績日補完ルール（基準日=本日固定、スケジュール画面用） | 6.3,D-34注1 |
| `scheduleRowOrdering.ts`＋test | 行配列の上へ・下へ・下に挿入・削除の純粋関数（`vocabDeckOrder.ts`と同型） | D-13 |
| `useScheduleEditorState.ts`＋test | 中心フック。`GET`取得→ローカル編集状態（行・列・セル、仮キー採番）→差分編集→`ScheduleSaveRequest`組み立て→保存ミューテーション（409時は`conflict`状態を立てるのみで編集内容は破棄しない）→破棄→`hasUnsavedChanges`算出 | D-05,D-06,D-07,D-08,D-12,D-13 |
| `ScheduleTab.tsx`＋test | エントリ。`GanttTab.tsx`と同型（`goalId`のみ受取り自前fetch）。ローディング/エラー表示・ツールバー/グリッド/空状態の出し分け・ページ幅拡張の通知 | 3.1 |
| `ScheduleToolbar.tsx`＋test | 固定行数・固定列数の`<select>`、今日へ・行を追加・列を追加・変更を破棄（確認）・保存ボタン | D-24,D-25,D-26,3.1,3.3 |
| `ScheduleGrid.tsx`＋test | 一体型グリッド本体（CSS Grid）。見出し2段・固定列/固定行のsticky適用（固定行はResizeObserverで実測した高さからtopを算出、固定列は`scheduleColumnLayout`の静的remから算出）・行操作列・既定7列・追加列・ガント列の描画分岐 | D-02,D-08,D-21,D-24 |
| `ScheduleRowActionsCell.tsx`＋test | 上へ・下へ・下に挿入・削除ボタン（閲覧のみの目標では非表示） | D-04,D-13,3.2 |
| `ScheduleStatusSelect.tsx`＋test | 状況の`<select>`＋`scheduleStatusAutoFill`の適用 | D-10,6.3 |
| `ScheduleCustomColumnHeaderCell.tsx`＋test | 追加列見出しの名前変更・左右移動・削除（値があれば確認） | D-12,3.3 |
| `ScheduleGanttRow.tsx`＋test | 1行分の予定帯・実績帯・遅れ印・Tooltip | D-17,D-18,D-27 |
| `ScheduleGanttOverlay.tsx`＋test | 土日祝の網掛け・本日線（グリッド全体に1回だけ重ねる共有オーバーレイ） | 3.4 |
| `ScheduleGanttHeader.tsx`＋test | 年月・日の2段見出し、収録範囲外年の注記 | D-21,D-45 |
| `ScheduleEmptyState.tsx`＋test | 0行時の案内文＋「行を追加」 | D-28 |
| `ScheduleConflictDialog.tsx`＋test | 409時の「最新を読み込む（編集内容は破棄）」「編集を続ける」（既存`Modal`を使用、選択肢ダイアログは前例が無いため新規） | D-07,12章補足8 |

### 3.4 frontend（既存ファイルの変更）

| ファイル | 変更内容 | 理由 | D-ID |
| --- | --- | --- | --- |
| `frontend/src/api/schedule.ts`（新規） | `getSchedule`・`saveSchedule`・`updateScheduleViewSetting`の薄いラッパー（`analytics.ts`と同型） | 第8章 | — |
| `frontend/src/api/resources.ts` | `getHolidayCoverage()`に任意引数`dateFrom?`・`dateTo?`を追加（既存のDayTypeDefaultsCardからの無引数呼び出しは無変更で動作） | D-45、期間指定の祝日取得 | — |
| `frontend/src/constants/queryKeys.ts` | `holidayCoverage(dateFrom?, dateTo?)`へキー拡張、`schedule(goalId)`を追加 | 第8章 | — |
| `frontend/src/components/Tooltip.tsx` | `position`任意prop（既定`'bottom'`、ガント帯用に`'top'`を追加）を追加。既存呼び出し（タブツールチップ等）は無指定のため無変更で動作 | D-27。既存のTooltipは位置固定（`bottom-full`）で帯の上に出せない | D-27 |
| `frontend/src/pages/GoalDetailPage.tsx` | `EXAM_TABS`・`READING_TABS`・`WORK_TABS`へ`schedule`タブを追加（`goalConsultation`の直前）。`GoalDetailTabContent`に`<ScheduleTab>`描画分岐を追加。スケジュールタブ表示中のみ外殻の`max-w-3xl`を`max-w-full`に切り替える | D-01,D-31 |
| `frontend/src/pages/GoalDetailPage.test.tsx` | 3カテゴリ分のタブ一覧テストへ`schedule`を追加。ScheduleTab描画・幅拡張のテストを追加 | 回帰・新機能 | D-01 |
| `frontend/src/index.css` | `--success`（完了帯専用の固定色）、`--schedule-saturday-bg`・`--schedule-holiday-bg`・`--schedule-planned-bg`・`--schedule-today-line`・`--schedule-delay-mark`をlight/dark両方・`@theme inline`に追加 | D-18,3.4 | D-18 |
| `frontend/src/locales/ja.json`・`en.json` | `goals.detail.tabs.schedule`・`tabTooltips.schedule`、新設`schedule.*`セクション（ツールバー・列見出し・状況選択肢・検証メッセージ・空状態・409ダイアログ・祝日未収録注記等）、`help.sections.schedule.*`、`help.sections.goals.p2/p5/p6`へスケジュールタブの言及を追記 | D-48,ゼロハードコーディング | D-48 |
| `backend/app/content/help_content.json` | `export_help_content.py`で再生成 | ja.json由来のため手書き禁止 | D-48 |

### 3.5 文書（D-49）

| 文書 | 変更内容 |
| --- | --- |
| `docs/技術選定書_ミチナリ_v1.0.md` 4.3 | 表示対象の前提に「1目標あたり最大100行×表示期間（横スクロール）」を追記。固定列・固定行を`position: sticky`で実現する方針、ドラッグ操作なしを維持する旨を追記 |
| `docs/仕様書_ミチナリ_v1.1\06_画面仕様\6.2_SC-03_目標詳細・編集.md` | 3種別共通のタブとして「スケジュール」タブの節を新設（本書3章の要約、閲覧のみの判定・一括保存・409・固定・ガント・祝日未収録注記） |
| `docs/設計書_データ構造編_ミチナリ_v1.1.md` | 改訂履歴（改78）に`ScheduleRead`フィールド追加を記録 |

## 4. 回帰の網（15.1手順8、特性テスト）

- **既存の教材ガント（ANL-04）**：`frontend/src/features/analytics/ganttGeometry.test.ts`（6ケース）が`computeGanttLayout`（内部で`daysBetween`を使用）の入出力を既に固定している。`daysBetween`抽出の前後で本テストを実行し、変更前後で同一の6/6合格であることを確認してから実装に入る（新規の特性テストは追加しない。既存テストが本単位の変更対象関数を直接カバーしているため、15.1手順8の「変更前の挙動を固定するテスト」の要件を既に満たしていると判断）。
- **`GoalDetailPage.test.tsx`の3カテゴリタブ一覧テスト**：本単位でタブが1つ増えるため期待値の変更が必要になる（15.1手順10「既存テストの期待値の変更」に該当）。変更前に現状（スケジュールタブが無い状態のタブ一覧）が通ることを確認した上で、スケジュールタブを追加した期待値へ更新する。理由：D-01「3種別すべてにタブを追加する」という本単位の意図した変更そのものであり、デグレではない。
- **`DayTypeDefaultsCard.test.tsx`（単位1）**：`getHolidayCoverage()`への引数追加が既存の無引数呼び出しに影響しないことを、変更前後でテストを再実行して確認する（新規の特性テストは追加しない。既存のテストスイートがそのまま回帰テストとして機能する）。

## 5. 横展開チェックリスト

| 検索語 | 期待する結果 |
| --- | --- |
| `grep -rn "ScheduleItemStatus" frontend/src` | `types/api.d.ts`（自動生成）と、`scheduleStatusAutoFill.ts`・`ScheduleStatusSelect.tsx`・`scheduleValidation.ts`等の新規ファイルのみから参照。状態の色分けマッピングが1箇所（`scheduleGanttGeometry.ts`またはindex.css参照箇所）に集約されていること |
| `grep -c "\"schedule\"" frontend/src/locales/ja.json frontend/src/locales/en.json`、`goals.detail.tabTooltips.schedule`の有無 | 両ファイルに同数のキーが存在すること（`localeKeyUsage.test.ts`で検出） |
| `npm run generate:api-types`後の`git diff --stat src/types/api.d.ts` | `ScheduleRead`への4フィールド追加のみ（手書きの型定義が残っていないこと） |
| `grep -rn "DATA_SCHEMA_VERSION" backend/app/services/backup_service.py` | 変更なし（新規テーブル・カラムを追加していないため） |
| `grep -n "SCHEDULE_" backend/app/services/settings_service.py` | ヒットなし（本単位でも設定画面への配線は追加しない。`ScheduleRead`経由での画面への値渡しのみ） |
| `grep -rn "max-w-3xl" frontend/src/pages/GoalDetailPage.tsx` | スケジュールタブ表示中だけ条件分岐しており、他の19画面の`max-w-3xl`（各ページファイル）には触れていないこと |
| `grep -rln "ganttGeometry" frontend/src` | `GanttTab.tsx`（呼び出し元、無変更）・`ganttGeometry.ts`・`ganttGeometry.test.ts`のみ。`scheduleGanttGeometry.ts`は独立ファイルであり`ganttGeometry.ts`を参照しない（百分率方式とrem方式は別物、3.4） |
| `grep -rn "isClosedGoalStatus" frontend/src/features/schedule` | 独自の終了判定を作らず、`ScheduleTab`が`GoalDetailPage`から受け取った`readOnly` propをそのまま使っていること |
| `grep -rn "useUnsavedChangesWarning" frontend/src/features/schedule` | 既存フックをそのまま使用（カスタム文言を追加していないこと、仕様上の制約） |
| `grep -rn "dangerously" frontend/src/features/schedule` | ヒットなし（生HTML描画用propを使用していないこと） |
| `grep -rnE "#[0-9a-fA-F]{3,6}|bg-(blue|green|gray|red|amber)-[0-9]+" frontend/src/features/schedule` | ヒットなし（index.cssのトークン経由のみ） |
| `help_content.json`の`schedule`・`goals`セクション | `export_help_content.py`実行後、ja.jsonの内容と一致すること（`test_help_content.py`） |

## 6. チェックリスト（実装）

- [ ] 2章食い違い2：`ScheduleRead`へ4フィールド追加・テスト・型再生成
- [ ] 3.2：`utils/dateRange.ts`抽出・`ganttGeometry.ts`更新・既存テスト無変更で合格確認
- [ ] 3.3：`features/schedule/`配下の純粋関数群（`scheduleColumnLayout`・`scheduleGanttGeometry`・`scheduleDelay`・`scheduleValidation`・`scheduleStatusAutoFill`・`scheduleRowOrdering`）とテスト
- [ ] 3.3：`useScheduleEditorState`（差分編集・保存・409・破棄・未保存判定）とテスト
- [ ] 3.3：`ScheduleTab`・`ScheduleToolbar`・`ScheduleGrid`・`ScheduleRowActionsCell`・`ScheduleStatusSelect`・`ScheduleCustomColumnHeaderCell`・`ScheduleGanttRow`・`ScheduleGanttOverlay`・`ScheduleGanttHeader`・`ScheduleEmptyState`・`ScheduleConflictDialog`とテスト
- [ ] 3.4：`api/schedule.ts`・`resources.ts`拡張・`queryKeys.ts`拡張・`Tooltip.tsx`拡張・`GoalDetailPage.tsx`（タブ追加・幅拡張・描画分岐）・`index.css`トークン追加
- [ ] D-45：祝日未収録年の注記（`ScheduleGanttHeader`）
- [ ] D-48：ja.json/en.json・help_content.json
- [ ] D-49：技術選定書4.3・仕様書6.2
- [ ] 性能確認：100行×365日相当のフィクスチャでの描画・スクロールの手動確認（DOM要素数が行数×日数に比例しないことをコードレビューで確認）
- [ ] fontScale確認：`data-font-scale='small'/'large'`切替時に1日分の幅・固定列位置が崩れないことを手動確認
- [ ] ライト/ダーク確認：新規トークンの両モードでの見た目を手動確認

## 7. 追跡表

（実装完了後に実装箇所・テスト名を記入する）

| D-ID | 実装箇所 | テスト名 |
| --- | --- | --- |
| D-01 | `GoalDetailPage.tsx`の`EXAM_TABS`/`READING_TABS`/`WORK_TABS` | `GoalDetailPage.test.tsx` |
| D-02 | `ScheduleGrid.tsx`（CSS Grid、表部分+ガント部分を1つのグリッド） | `ScheduleGrid.test.tsx` |
| D-04 | `GoalDetailPage.tsx`→`ScheduleTab`への`readOnly` prop伝播（`isClosedGoalStatus`） | `ScheduleTab.test.tsx` |
| D-05,D-06,D-07 | `useScheduleEditorState.ts` | `useScheduleEditorState.test.ts` |
| D-08,D-09 | `scheduleColumnLayout.ts`・`scheduleValidation.ts` | 各test |
| D-10,6.3 | `ScheduleStatusSelect.tsx`・`scheduleStatusAutoFill.ts` | 各test |
| D-11 | `scheduleValidation.ts` | `scheduleValidation.test.ts` |
| D-12 | `ScheduleCustomColumnHeaderCell.tsx` | test |
| D-13 | `scheduleRowOrdering.ts`・`ScheduleRowActionsCell.tsx` | 各test |
| D-14 | `ScheduleToolbar.tsx`（行・列上限での追加ボタン無効化） | test |
| D-15,D-16 | `scheduleColumnLayout.ts`・`ScheduleGrid.tsx`（固定幅・折り返し・行高さ自動調整） | 各test |
| D-17,D-18 | `scheduleGanttGeometry.ts`・`ScheduleGanttRow.tsx`・`index.css` | 各test |
| D-19 | `useScheduleEditorState.ts`（ローカル編集値をそのままガントへ反映） | test |
| D-20 | `scheduleGanttGeometry.ts`（クランプ計算） | test |
| D-21 | `ScheduleGanttHeader.tsx` | test |
| D-22,D-23,D-26 | `scheduleGanttGeometry.ts`（表示期間・初期スクロール位置）・`ScheduleToolbar.tsx`（今日へ） | 各test |
| D-24,D-25 | `ScheduleGrid.tsx`（sticky）・`ScheduleToolbar.tsx`（選択欄） | 各test |
| D-27 | `ScheduleGanttRow.tsx`・`Tooltip.tsx` | 各test |
| D-28 | `ScheduleEmptyState.tsx` | test |
| D-29 | `scheduleValidation.ts`・`ScheduleGrid.tsx`（赤枠・エラースクロール） | 各test |
| D-30 | `ScheduleGrid.tsx`（横スクロール） | — |
| D-31 | `GoalDetailPage.tsx` | `GoalDetailPage.test.tsx` |
| D-45 | `ScheduleGanttHeader.tsx`（`getHolidayCoverage`拡張呼び出し） | test |
| D-48 | ja.json/en.json・help_content.json | `test_help_content.py`・`localeKeyUsage.test.ts` |
| 3.4（共通化） | `utils/dateRange.ts` | `dateRange.test.ts`、既存`ganttGeometry.test.ts`無変更 |

## 8. 次の単位への引き継ぎ事項

- スケジュールタブ（単位3）は完成し、資格試験・読書・仕事の全種別で利用できる。単位4（日次報告との連携）は、`frontend/src/features/schedule/scheduleValidation.ts`（検証）・`scheduleStatusAutoFill.ts`（実績日の補完。ただし基準日は本単位では本日固定。日次報告では報告対象日を渡せるよう、`applyScheduleStatusAutoFill`の`today`引数に報告対象日を渡すだけで再利用できる設計にした）をそのまま再利用できる。
- `backend/app/services/schedule_service.validate_item_fields`（単位2で日次報告からの再利用を想定して用意済み）と、フロントエンドの`scheduleValidation.validateScheduleItemFields`は同じ6.2のルールを別言語で実装したミラーである。単位4でサーバー側の検証エラーをSC-06/SC-07の画面へ出す際、同じエラーコード（`TITLE_REQUIRED`等ではなく、サーバー側は`ValidationError`の文言のみ）の対応関係が無いため、画面側の表示方法を単位4の影響範囲確定時に決めること。
- `frontend/src/api/schedule.ts`・`frontend/src/features/schedule/scheduleDraftTypes.ts`（`ScheduleDraftItem`等の型）は単位4のSC-06/SC-07「今日の作業項目」欄からも再利用できる想定で作ってある。
- `frontend/src/features/schedule/ScheduleStatusSelect.tsx`・`ScheduleDateCell.tsx`等の小さな部品は、単位4の「今日の作業項目」欄（状況選択・実績日表示）からそのまま再利用できる可能性がある（影響範囲確定時に検討すること）。
- `schedule.gantt_day_width_min_rem`/`max_rem`（1.75/4.5rem）は本単位で実装したセルのフォント・余白に対して妥当であることを確認済み（2章食い違い3）。単位4・単位5でこの値を変更する必要が生じた場合も、同じ設定キーをそのまま使う。
- ガントの遅れの印（D-18、`scheduleDelay.computeDelayDays`）は、3.4の「終了の遅れ」のみを実装している。単位5（13.2）で「開始の遅れ」を追加する際は、既存の`computeDelayDays`を拡張するか、13.2の共通判定関数側で両方を判定してガント側に渡す設計にすること（開発Todo14章補足4参照）。

## 9. 報告が必要な食い違い・範囲外の不具合

**食い違い（2章で報告済み、判断を仰ぐために実装を止めるべきものではないと判断し対応済み）**:
1. 3.4「予定日が未入力の行」は単位2のNOT NULL制約と矛盾するため、ガント側に特別処理は実装しなかった。
2. `ScheduleRead`に画面が必要な内部パラメータ（行・列の上限、ガント幅レンジ）が無かったため、単語帳機能の前例に倣い4フィールドを追加した。
3. `schedule.gantt_day_width_min_rem`/`max_rem`の暫定値（1.75/4.5）を実装後に見直し、変更なしと判断した。

**独立レビュー（15.1手順16）で見つかり、本単位内で対応済みの不具合**：
- 固定行（D-24で`frozen_row_count`>0を設定した場合）のガントに、土日祝の網掛け・本日線が重ならない不具合（`ScheduleOverlaidRows.tsx`を新設し解消）。
- D-21「日の見出しの色分け」が未実装（`ScheduleGanttHeader.tsx`に`holidayIsoDates`を渡し、土曜・日曜祝日の背景色を追加）。
- `ScheduleGanttRow.tsx`のTooltipトリガーで、CSSの詳細度により`absolute`指定が無効化されていた（`wrapperClassName`から`absolute inset-0`を外し、`h-full w-full`のみに変更）。

**範囲外の不具合**：発見なし。

## 10. コミット前チェック（15.1手順13・14・16）の結果と対応

CLAUDE.md「コミット前チェック」の該当する観点別レビューエージェント5件（dry-reviewer・style-reviewer・label-checker・xss-reviewer・performance-reviewer）と、手順16の独立レビュー（経緯を知らない別セッション）を実行した。バックエンド全体のpytest（2804 passed）・`ruff check .`、フロントエンド全体のvitest（最終261ファイル/2056件、coverage100%）・`npx tsc -b`・`npx oxlint`はレビュー前後とも合格を確認している。

| レビュー | 結果 | 対応 |
| --- | --- | --- |
| dry-reviewer | HIGH1件：`stickyStyle`関数が5ファイルに完全重複。MEDIUM1件：セル編集対象フィールドのUnion型が4箇所に重複定義 | 両方対応済み：`scheduleColumnLayout.ts`に`stickyStyle`を1つだけexportして5ファイルから使う形に統合、`scheduleDraftTypes.ts`に`ScheduleDraftFieldKey`を1つ定義して4箇所から使う形に統合 |
| style-reviewer | MEDIUM2件：`useScheduleRowActions.ts`/`useScheduleColumnActions.ts`のコメントが、開発中にリネームされ存在しない関数名（`useScheduleDraftActions`）を指していた。設計意図を説明する大きなJSDocが、本来の対象（`useScheduleEditorState`本体）ではない別の関数の直上に置かれていた。LOW2件：`toDraft`/`buildSaveRequest`・`validateScheduleItemFields`/`hasScheduleFieldErrors`に一行docが無い | 全件対応済み：コメントを実在する関数名（`useScheduleEditorState`）に修正、JSDocを対象の関数直上へ移動、4関数に一行docを追加 |
| label-checker | 問題なし | 対応不要 |
| xss-reviewer | 問題なし（危険API不使用、利用者入力はすべてJSXのテキスト描画経由） | 対応不要 |
| performance-reviewer | MEDIUM1件：`useScheduleGridGeometry`が未メモ化で、無関係な入力（作業項目名等）のたびに毎レンダリング再計算される。LOW3件：`ScheduleTab.tsx`側の同様の再生成、`useViewportWidthRem`のresizeリスナー未デバウンス、行コンポーネント未メモ化（任意） | MEDIUM・LOW2件対応済み：座標計算に`useMemo`を導入（依存値は座標に関係する値のみの署名文字列）、`ScheduleTab.tsx`側も`useScheduleHolidays`フックへ分離した上で同様にメモ化、resizeリスナーを100msデバウンス。行コンポーネントの`React.memo`化は任意の改善提案として見送った（現状の規模〈最大100行〉では実害が無いと判断） |
| 独立レビュー（手順16） | 総合判定「軽微な指摘あり」。HIGH1件：固定行のガントに土日祝の網掛け・本日線が重ならない。MEDIUM2件：D-21の日の見出しの色分けが未実装、Tooltipトリガーの`absolute`指定がCSSの詳細度により無効化される懸念。LOW2件：一部のフック（`useScheduleColumnActions`等）に直接テストが無い、Tooltipの`position`命名が開発Todoの記述（bottom/top）と実装（above/below）で異なる | HIGH・MEDIUM全件対応済み（本章上記参照）。LOWのうち、`useScheduleRowActions`・`useScheduleColumnActions`に直接テストを追加した。`useScheduleSaveClick`・`useScheduleSaveMutations`・`useScrollToToday`・`ScheduleGridBody`は`ScheduleTab.test.tsx`・`ScheduleGrid.test.tsx`の統合テストで実質的に検証されているため専用テストは追加していない（対応不要と判断）。Tooltipの命名差異は実装側がより明確なため変更不要と判断した |

対応後、フロントエンド全体のvitest（261ファイル・2056件、coverage100%）・`tsc -b`・`oxlint`、バックエンド全体のpytest（2804 passed、coverage100%）・`ruff check .`を再実行し全合格を確認した（0章末のベースライン比較と対比）。
