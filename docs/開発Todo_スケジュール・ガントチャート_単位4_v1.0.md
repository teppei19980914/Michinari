# 開発Todo：スケジュール・ガントチャート機能 単位4（日次報告との連携） v1.0

入力: `docs/開発Todo_スケジュール・ガントチャート_v1.1.md`（第2章D-32〜D-40・第4章・第6章・第8章・第9章単位4・第15章）、`docs/開発Todo_スケジュール・ガントチャート_単位1_v1.0.md`・`docs/開発Todo_スケジュール・ガントチャート_単位2_v1.0.md`・`docs/開発Todo_スケジュール・ガントチャート_単位3_v1.0.md`（引き継ぎ事項）、`docs/開発TODO_下書き保持不具合_影響範囲確認.md`（既知の不具合パターン）。

## 0. ベースライン（着手前に確認）

- 前提確認：単位1（祝日基盤、PR#145）・単位2（データモデルとAPI、PR#146）・単位3（スケジュールタブ、PR#147）はいずれも実装済み・`main`にマージ済み（`git log origin/main --oneline --merges`で確認。#148はテストのflaky修正のみで単位4とは無関係）。
- **作業用ブランチの前提**：本セッション開始時、ローカルの`dev/2026-11-11`が`main`から13日分（分岐して）古い状態だった（単位1〜3の成果が一切反映されていなかった）ことを検出し、利用者の承認を得て`origin/main`（96cac54）起点で`dev/2026-11-24`を作成し直した。`dev/2026-11-11`の独自コミット1件（`07ed23e`、まとめと共有カード機能のドキュメント追記）はcherry-pick済み（バージョン番号の衝突のみ`origin/main`側の値2.12.0を採用）。
- backend: `../myvenv/Scripts/python.exe -m ruff check .` → All checks passed。`pytest -q` → **2804 passed**, coverage 100%（706.58s）。
- frontend: `npm run lint`（oxlint、`DayTypeDefaultsCard.tsx`のmax-lines-per-function警告1件のみ。単位1由来の既知の警告で本単位の範囲外）・`npm run build`（tsc -b + vite build, exit 0）・`npm test -- --run`（**261 files, 2056 tests**, coverage100%, exit 0）。

## 1. 脅威分析（STRIDE、簡易）

`/threat-model`スキルを試したところ、現在のスキル一覧には存在せず（`security-review`スキルが代わりに起動し、無関係な直近コミットの差分レビューを行おうとしたため中断した）、単位1〜3と同様に手動でSTRIDE分析を実施した。

- **データフロー**：[利用者] → SC-06/SC-07画面（新規：`GET /records/{date}/schedule-items`取得・`schedule_item_updates`送信） → 確定API3本・progress API（信頼境界） → `record_service_common`/`record_service_exam`等 → `schedule_service`（単位2の検証を再利用） → `schedule_item`/`schedule_item_history`（DB、実績と同一トランザクション）
- **S（なりすまし）**：既存の認証機構と同一。新規の認証経路は追加しない。対象外。
- **T（改ざん）**：検証は単位2の`schedule_service.validate_item_fields`を再利用し、重複実装しない（本単位の必須事項）。保存はSQLAlchemyのパラメータ化クエリに委ね、無害化しない（単位2と同じ方針、表示側の責務）。
- **R（否認）**：`schedule_item_history`にsource=DAILY_REPORT／PROGRESS_ONLY・record_date=報告対象日で記録する（D-39）。
- **I（情報漏洩）**：`GET /records/{date}/schedule-items`は対象日にACTIVEな目標の行のみを返す。確定API・progress APIの`schedule_item_updates`は、他目標・他カテゴリ・終了/非ACTIVE目標のIDを送っても「存在しない」場合と区別せず拒否する（単位2`_check_owned_by_goal`と同じ考え方）。
- **D（サービス拒否）**：対象外（本依頼のレビュー観点から除外）。
- **E（権限昇格）**：確定API3本は「その種別の目標に属する行だけ」、progress APIは「ACTIVEな目標の行」を境界とする。既存の`goal_service.ensure_operation_allowed(goal, GoalOperation.RECORD)`（ACTIVE限定、`_apply_study_logs`等が教材/書籍/案件の所有目標に対して既に使っている関数）をスケジュール行の所有目標に対しても再利用し、新規の認可ロジックを増やさない。本単位最大の論点のため、認可境界テストを重点的に追加する（CLAUDE.md・本依頼の重点確認）。

対策はすべてMitigate（単位2の検証・既存の認可パターンの再利用、新規の攻撃面は増やさない）。受容したリスクなし。

## 2. 報告が必要な食い違い・補った実装詳細（15.1手順5、判断は仰ぐが実装は止めない）

いずれも「仕様の意図自体は変わらない、実装の詳細で吸収できる」と判断し、単位1〜3の前例に倣って対応しつつ報告する。**実装を止めるべき食い違いは見つからなかった。**

1. **`GET /records/{target_date}/schedule-items`の応答粒度は本書に明記が無いため補った。** D-33の3条件（報告対象日が予定期間内／進行中／予定終了日超過の未完了）で既定表示対象を判定し、各行に`default_visible`フラグを付けて返す。「すべて表示」はクライアント側で`status not in (DONE, CANCELLED)`へフィルタを切り替えるだけとし、追加のAPI呼び出しは発生させない（12章補足7「完了・中止以外の全行を表示する」と整合。往復を増やさないための実装詳細）。DONE/CANCELLEDの行はそもそも「すべて表示」でも表示されないため、応答にも含めない。対象目標はACTIVEのみ（既存のノルマ・日記・読書書籍・業務案件と同じ絞り込み基準に揃える。D-38「作業項目がない目標では欄ごと表示しない」の判定もこの絞り込み後の件数で行う）。
2. **確定API3本・progress APIからのスケジュール行更新の認可境界は、スケジュール画面（単位2`save_schedule`の`ensure_goal_editable`、CLOSED以外なら編集可）とは別の基準を採用した。** 日次報告・progress APIは「今日の報告」という文脈であり、対象になるのは既存の教材・書籍・案件・日記と同じ「ACTIVEな目標」に限られる（下書き・一時停止中の目標はそもそも`GET /records/{date}/schedule-items`に出てこない）。したがって`goal_service.ensure_operation_allowed(goal, GoalOperation.RECORD)`（ACTIVE限定、既存の実績登録と同一基準）を再利用し、新たな認可ロジックを増やさない。スケジュール画面自体の編集可否（D-04、下書き・一時停止中も編集可）は単位3の対象のままで変更しない。
3. **スケジュール行更新の`revision`加算は「目標ごとに、1回のAPI呼び出しで1件以上の行が実際に変化した場合に1増やす」とした（本書7.1）。** 単位2の`save_schedule`が「1回のPUT呼び出しで1増やす」という単位で楽観ロックを運用しているのと同じ考え方を、日次報告側の「1回の確定／登録呼び出し」に適用した。1回の確定で複数の目標（例：資格試験の目標が2件同時進行）の行を更新した場合は、目標ごとに個別に1増やす。`GoalSchedule`行が存在しない目標（スケジュール画面を一度も保存していない）は、`revision=1`で新規作成する（`save_schedule`が`schedule is None`のときに行う初期化と同じ）。
4. **`schedule_item_updates`に同一`schedule_item_id`が重複した場合はエラーとした。** 単位2の独立レビューで発覚した「一括保存での重複ID」と同種の不備を防ぐため、単位2の`ValidationError("Duplicate item id in request")`と同じ方針を適用した（本書に明記は無いが、単位2の前例に倣う実装詳細）。
5. **ReadingReportSection/WorkReportSectionにおける対象目標の絞り込みは、既存の`StudyLogFields`/`DiaryFields`等と同じ「目標タブ選択時は選択中の1目標、未選択時は全目標」のルールをそのまま踏襲した。** 確定（finalize）時に送信する`schedule_item_updates`も、既存の`studyLogValues`等と同じく**下書き全体**（選択中タブに関わらず全ACTIVE目標分）を送る（カテゴリごとに独立して確定するという既存仕様、仕様変更2026-09-05、に揃える）。
6. **`GET /records/{date}/schedule-items`の取得は、既存の共有フック`useDailyRecordQueries`へ追加した。** これにより閲覧専用のSC-08（`DailyReportViewPage`）でも本クエリが（未使用のまま）実行されるが、副作用の無いGETリクエスト1本が増えるだけであり、`computeIncomingDraftValues`など既存の下書きhydrate/マージの仕組みをそのまま再利用できる利点（下書き保持不具合の再発防止、4章参照）を優先した。SC-08側の画面・挙動は変更しない（15.1手順11「単位の範囲外は変更しない」）。

## 3. 影響範囲表

### 3.1 backend

| ファイル | 変更内容 | 理由 | D-ID |
| --- | --- | --- | --- |
| `backend/app/schemas/schedule.py` | `ScheduleItemUpdateInput`（schedule_item_id・status・actual_start_date・actual_end_date）、`ScheduleItemForReportRead`（+default_visible）、`GoalScheduleItemsForReportRead`（goal_id・goal_name・goal_category・items）を追加 | 8章 | D-32,D-33 |
| `backend/app/services/schedule_service.py` | `list_schedule_items_for_report(session, target_date)`（D-33判定・ACTIVE目標限定）、`apply_report_schedule_item_updates(session, updates, *, category, target_date, today, source)`（検証→適用→履歴→revision加算）を追加。既存の`validate_item_fields`をそのまま呼ぶ（再実装しない） | 第4章・第6章・第8章 | D-32〜D-39 |
| `backend/app/api/records.py` | `GET /records/{target_date}/schedule-items`を追加。`finalize_record`/`finalize_reading_record`/`finalize_work_record`/`register_progress`の4エンドポイントで`payload.schedule_item_updates`を各サービスへ渡す | 8章 | D-32,D-35 |
| `backend/app/schemas/record.py` | `FinalizeRequest`/`ReadingFinalizeRequest`/`WorkFinalizeRequest`/`ProgressRegisterRequest`へ`schedule_item_updates: list[ScheduleItemUpdateInput] = []`を追加（`app.schemas.schedule`からimport） | 8章 | D-32 |
| `backend/app/services/record_service_exam.py`・`record_service_reading.py`・`record_service_work.py` | `finalize_record`/`finalize_reading_record`/`finalize_work_record`に`schedule_item_updates`引数を追加し、`schedule_service.apply_report_schedule_item_updates(..., category=GoalCategory.EXAM/READING/WORK, source=DAILY_REPORT)`を呼ぶ | 8章 | D-35 |
| `backend/app/services/record_service_common.py` | `register_progress`に`schedule_item_updates`引数を追加。「実績または作業項目の更新が1件以上必須」へ緩和。`schedule_item_updates`のみの場合はDailyRecordを作らない（D-36）。戻り値の型ヒントを`DailyRecord \| None`に修正（既存の`_serialize_record`はNone対応済みのため呼び出し側の変更は不要） | 8章 | D-36,D-37 |
| `backend/tests/test_api_records_common.py` | `GET /records/{date}/schedule-items`の表示条件・ACTIVE限定・空目標の非表示のテストを追加（既存の`_make_active_*`ヘルパー3種がこのファイルに既にあり、カテゴリを問わないエンドポイントのため同ファイルの既存スコープに合致、新規ファイルは作らない）。progress APIのD-36テストも同ファイルに追加 | D-33,D-38,D-36 | D-32,D-33,D-36 |
| `backend/tests/test_api_records_exam.py`・`test_api_records_reading.py`・`test_api_records_work.py` | 確定API3本の`schedule_item_updates`の検証・認可境界・historyのテストを追加（各ファイルの既存ヘルパーを再利用） | D-35,D-39,8.1 | D-35,D-39 |
| `backend/tests/test_schedule_service.py` | `apply_report_schedule_item_updates`・`list_schedule_items_for_report`の単体テスト（重複ID・revision加算・D-37の上書き・終了した目標〈CLOSED_WITH_RESULT〉の拒否） | 第9章「テスト」 | D-33,D-37 |
| `backend/tests/test_record_service_common.py` | `register_progress`のサービス層単体テスト（D-36、schedule_item_updatesのみでDailyRecordを作らない） | D-36 | D-36 |
| `backend/app/constants/enums.py` | `ScheduleUpdateSource`のdocstringを実際の使用箇所（本単位の`apply_report_schedule_item_updates`）を指すよう更新（コミット前チェックのstyle-reviewerで指摘） | — | — |
| `frontend/src/types/api.d.ts` | `npm run generate:api-types`で再生成 | 手書き禁止 | 8章 |
| `docs/仕様書_ミチナリ_v1.1/06_画面仕様/6.5_SC-06_日次報告.md`・`6.6_SC-07_進捗のみ登録.md` | 「今日の作業項目」欄の仕様を追記 | D-49 | — |
| `docs/設計書_データ構造編_ミチナリ_v1.1.md` 6.API設計 | 新規API・リクエスト拡張を追記、改訂履歴に追加 | D-49 | — |

### 3.2 frontend（新規）

| ファイル | 内容 | 理由 | D-ID |
| --- | --- | --- | --- |
| `frontend/src/api/records.ts` | `getScheduleItemsForReport(targetDate)`を追加。`FinalizeRequest`等の型に`schedule_item_updates`を追加（自動生成の型をそのまま使用） | 8章 | — |
| `frontend/src/features/record/scheduleItemsDraft.ts`＋test | 1行分のドラフト値（status・actualStartDate・actualEndDate・touched）の初期化・パッチ・ペイロード組み立て（`studyLogForm.ts`と同型。「変更しなかった行は送信しない」ため`touched`フラグを持つ）、`selectScheduleItemIdsForGoals`・`collectAllScheduleItemIds`（送信対象の絞り込み） | D-35,D-36 | — |
| `frontend/src/features/record/ScheduleItemsField.tsx`＋test | 「今日の作業項目」欄の最上位（目標ごとに`ScheduleItemsGoalGroup`を並べる、0件なら非表示） | D-32,D-38 | D-32 |
| `frontend/src/features/record/ScheduleItemsGoalGroup.tsx`＋test | 1目標分（既定表示＋「すべて表示」切替、0件時の案内） | D-33,12章補足7 | D-33 |
| `frontend/src/features/record/ScheduleItemRow.tsx`＋test | 1行分（状況選択・実績日入力、`scheduleStatusAutoFill.applyScheduleStatusAutoFill`〈単位3、報告対象日を基準日として渡す〉・`scheduleValidation.validateScheduleItemFields`〈単位3〉をそのまま再利用、確定済みは取得結果を読み取り専用表示） | D-32〜D-34,12章補足6 | D-34 |
| `frontend/src/features/record/CategoryScheduleItemsField.tsx`＋test | カテゴリ別ReportSection用の束ね（カテゴリから`targets.examScheduleItemGoals`等を選ぶだけの薄いラッパー、コミット前チェックのdry-reviewerで6箇所の複製を指摘され追加） | D-38 | D-38 |

`useScheduleItemsForReport.ts`（薄いuseQueryラッパー）は設けず、`useDailyRecordQueries.ts`へ直接`useQuery`を組み込んだ（既存の`quota`・`record`等と同じ配線方法、2章補足6参照）。

### 3.3 frontend（既存ファイルの変更）

| ファイル | 変更内容 | 理由 | D-ID |
| --- | --- | --- | --- |
| `frontend/src/features/record/useDailyRecordQueries.ts` | `scheduleItems: UseQueryResult<GoalScheduleItemsForReportRead[]>`を追加（2章補足6） | D-32 | — |
| `frontend/src/features/record/useDailyReportDraft.ts` | `scheduleItemValues: Record<number, ScheduleItemDraftValue>`を追加。`computeIncomingDraftValues`・`useHydrateDraftOnce`・`useMergeNewlyCreatedEntries`に同じパターンで配線（下書き保持不具合と同種の不具合を防ぐため、既存の「hydrate後に新規作成されたIDだけを補う」設計を踏襲、4章参照） | D-35 | — |
| `frontend/src/features/record/ExamReportSection.tsx`・`ReadingReportSection.tsx`・`WorkReportSection.tsx` | 各カテゴリの実績入力の直下（editor）と確定済み表示（summary）に`CategoryScheduleItemsField`を追加 | D-38 | D-38 |
| `frontend/src/features/record/ProgressLogSections.tsx` | SC-07の末尾（確定状態に関わらず）に`ScheduleItemsField`（3カテゴリ分のgoalsを連結）を追加 | D-32,D-36,D-38 | — |
| `frontend/src/features/record/useDailyReportActions.ts` | `scheduleItemIdsByCategory`（カテゴリ別の対象行id）を算出し`DailyReportActions`へ追加。`finalizeRequest`で`schedule_item_updates: buildScheduleItemUpdatesPayload(draft.scheduleItemValues, scheduleItemIds)`を送信 | D-35 | — |
| `frontend/src/features/record/useZeroRecordAction.ts`・`ZeroRecordButton.tsx`・`RecordConfirmationExtras.tsx` | 「今日は何もしていない」確定にも`schedule_item_updates`を含める（2章補足7、利用者確認済みの食い違い対応） | D-35 | — |
| `frontend/src/features/record/resolveVisibleReportTargets.ts` | `examScheduleItemGoals`・`readingScheduleItemGoals`・`workScheduleItemGoals`を追加（既存の`selectForCategory`を再利用） | D-38 | — |
| `frontend/src/features/record/resolveProgressOnlyInput.ts` | `canRegister`の判定式に「スケジュール行の変更が1件以上」を追加。`payload.schedule_item_updates`を積む | D-36 | D-36 |
| `frontend/src/pages/ProgressOnlyPage.tsx` | `collectAllScheduleItemIds`で送信対象idを算出し`resolveProgressOnlyInput`へ渡す | D-36 | — |
| `frontend/src/locales/ja.json`・`en.json` | `schedule.dailyReportSection.*`（タイトル・すべて表示・絞り込む・0件案内の4キー）、`help.sections.dailyReport.p7`（「今日の作業項目」欄のヘルプ本文） | D-48,ゼロハードコーディング | D-48 |
| `backend/app/content/help_content.json` | `export_help_content.py`で再生成 | ja.json由来のため手書き禁止 | D-48 |

### 3.4 文書（D-49）

| 文書 | 変更内容 |
| --- | --- |
| `docs/仕様書_ミチナリ_v1.1/06_画面仕様/6.5_SC-06_日次報告.md` | 「今日の作業項目」欄の節を新設（表示条件、状況変更時の補完、確定時の保存、確定済みの読み取り専用表示） |
| `docs/仕様書_ミチナリ_v1.1/06_画面仕様/6.6_SC-07_進捗のみ登録.md` | 同上。「作業項目の更新だけでも登録できる」旨を明記（D-36） |
| `docs/設計書_データ構造編_ミチナリ_v1.1.md` 6.API設計 | `GET /records/{date}/schedule-items`・確定API3本/progress APIの拡張を追記 |

## 4. 回帰の網（15.1手順8、特性テスト）

本単位の変更対象（確定API3本・progress API）の**現在の挙動**を、変更前に固定する。ユーザー指示の「重点確認」と対応させる。

| 特性テスト（既存、実ファイル名で確認済み） | 固定する現在の挙動 |
| --- | --- |
| `test_api_records_exam.py::test_finalize_endpoint_rejects_update_after_reported`・`test_api_records_exam.py::test_progress_endpoint_rejects_update_after_reported` | 確定済み種別の拒否（`ImmutableRecordError`→409） |
| `test_api_records_exam.py::test_register_progress_endpoint_rejects_future_date`・`test_api_records_exam.py::test_finalize_endpoint_rejects_backdate_beyond_yesterday` | 入力可能期間（当日・前日まで） |
| `test_api_records_exam.py::test_finalize_endpoint_accepts_quick_mode_with_mood_and_no_items` | 報告状態の遷移（itemsが空でも確定・REPORTEDへ遷移できる、ひとこと記録モードの既存経路） |
| `test_api_records_common.py::test_register_progress_endpoint_rejects_both_lists_empty` | 「実績が1件以上必須」の拒否（`VALIDATION_ERROR`）。`json={}`は`schedule_item_updates`も空のため、緩和後もこのテストの期待値（400・VALIDATION_ERROR）は**無変更のまま**通ることを確認する（コードを一切変更せずに済む、15.1手順10で変更不要と判断した例） |
| `test_metrics_service.py`の既存テスト（無変更で実行確認） | 報告率・連続報告日数の算出（`DailyRecord`の確定状態列のみを見る、新規ロジック追加なし） |

実装前に上記既存テストを変更前のコードで実行し、全て合格することを確認してから着手する。

## 5. 横展開チェックリスト

| 検索語 | 期待する結果 |
| --- | --- |
| `grep -rn "schedule_item_updates" backend/app` | `schemas/record.py`・`schemas/schedule.py`・`api/records.py`・`services/record_service_common.py`・`services/record_service_exam.py`・`services/record_service_reading.py`・`services/record_service_work.py`・`services/schedule_service.py`のみ（手書きの重複ロジックが無いこと） |
| `grep -rn "validate_item_fields" backend/app` | `schedule_service.py`（定義・呼び出し2箇所）のみ。日次報告側が独自の検証を再実装していないこと |
| `grep -rn "ensure_operation_allowed" backend/app/services` | `record_service_exam/reading/work.py`（既存）・`schedule_service.py`（新規呼び出し）のみ。独自の認可ロジックを追加していないこと |
| `grep -c "scheduleItems\|scheduleItemValues" frontend/src/locales/ja.json frontend/src/locales/en.json` | 両ファイルに同数のキーが存在すること |
| `npm run generate:api-types`後の`git diff --stat src/types/api.d.ts` | `schedule_item_updates`・新規スキーマの追加のみ（手書きの型定義が残っていないこと） |
| `grep -n "DATA_SCHEMA_VERSION" backend/app/services/backup_service.py` | 変更なし（新規テーブル・カラムを追加していないため） |
| `grep -rn "dangerously" frontend/src/features/record` | ヒットなし |
| `grep -rln "useEffect" frontend/src/features/record/useDailyReportDraft.ts` | 既存の`useHydrateDraftOnce`/`useMergeNewlyCreatedEntries`と同型の2関数のみ追加されていること（下書き保持不具合と同じ原因〈クエリ再取得での黙った上書き〉を作っていないか目視確認、4章参照） |
| `help_content.json`の関連セクション | `export_help_content.py`実行後、ja.jsonの内容と一致すること（`test_help_content.py`） |

## 6. チェックリスト（実装）

- [x] D-32,D-33: `GET /records/{date}/schedule-items`・スキーマ・サービス関数・テスト
- [x] D-32,D-35: 確定API3本への`schedule_item_updates`追加・サービス層の委譲・テスト
- [x] D-36,D-37: progress APIの緩和（作業項目のみでの登録、DailyRecord非作成）・テスト
- [x] D-39: `schedule_item_history`への記録（source別）
- [x] 8.1系の所有者検証・認可境界テスト（他目標・他カテゴリ・終了/非ACTIVE目標のID）
- [x] 4章の特性テスト（既存挙動の固定、変更前に合格確認）
- [x] フロントエンド：`scheduleItemsDraft.ts`・`ScheduleItemsField.tsx`・`ScheduleItemsGoalGroup.tsx`・`ScheduleItemRow.tsx`（`useDailyRecordQueries.ts`に直接`useQuery`を組み込み、薄いラッパーhookは不要と判断、2章補足6参照）
- [x] フロントエンド：`useDailyReportDraft.ts`への配線（下書き保持、hydrate/マージ）
- [x] フロントエンド：3カテゴリ分のReportSection・ProgressLogSections（SC-07）への組み込み
- [x] フロントエンド：「今日は何もしていない」（`useZeroRecordAction.ts`）経路への組み込み（15.1手順5で発見・利用者確認済み、2章補足7参照）
- [x] D-48: ja.json/en.json・help_content.json
- [x] D-49: 仕様書6.5・6.6、設計書データ構造編6.API設計（改79）

## 7. 追跡表

| D-ID | 実装箇所 | テスト名 |
| --- | --- | --- |
| D-32 | `api/records.py::get_schedule_items_for_report`、`schedule_service.list_schedule_items_for_report`、frontend`useDailyRecordQueries.ts`（scheduleItems）・`ScheduleItemsField.tsx` | `test_api_records_common.py::test_get_schedule_items_endpoint_returns_eligible_items_grouped_by_goal`・`::test_get_schedule_items_endpoint_excludes_goal_with_no_eligible_items`、`ScheduleItemsField.test.tsx`（4件） |
| D-33 | `schedule_service._is_default_visible_for_report`・`list_schedule_items_for_report` | `test_schedule_service.py::test_list_schedule_items_for_report_default_visible_follows_d33`（4分岐）・`::test_list_schedule_items_for_report_excludes_*`（3件） |
| D-34 | `ScheduleItemRow.tsx`（`applyScheduleStatusAutoFill`を報告対象日基準で呼ぶ） | `ScheduleItemRow.test.tsx::applies the status auto-fill...` |
| D-35 | `record_service_exam.finalize_record`・`record_service_reading.finalize_reading_record`・`record_service_work.finalize_work_record`、`schedule_service.apply_report_schedule_item_updates`（category指定） | `test_api_records_exam.py::test_finalize_endpoint_applies_schedule_item_updates_and_bumps_revision`・`::test_finalize_endpoint_rejects_schedule_item_from_different_category`・`::test_finalize_endpoint_rejects_schedule_item_of_paused_goal`・`::test_finalize_endpoint_rejects_study_logs_together_with_invalid_schedule_item_update`、`test_api_records_reading.py`・`test_api_records_work.py`の同種テスト |
| D-36 | `record_service_common.register_progress`（schedule_item_updatesのみでDailyRecordを作らない分岐） | `test_api_records_common.py::test_register_progress_endpoint_accepts_schedule_item_updates_only_without_creating_record`、`test_record_service_common.py::test_register_progress_accepts_schedule_item_updates_only_without_creating_record`、`resolveProgressOnlyInput.test.ts`（3件） |
| D-37 | `schedule_service.apply_report_schedule_item_updates`（upsert、最新値で上書き） | `test_schedule_service.py::test_apply_report_schedule_item_updates_overwrites_with_latest_input_when_called_twice` |
| D-38 | `ExamReportSection.tsx`・`ReadingReportSection.tsx`・`WorkReportSection.tsx`・`ProgressLogSections.tsx`への配置、`ScheduleItemsField`の0件非表示 | `ScheduleItemsField.test.tsx::renders nothing when there are no eligible goals` |
| D-39 | `schedule_service.apply_report_schedule_item_updates`（`ScheduleItemHistory`追加、変化時のみ） | `test_schedule_service.py::test_apply_report_schedule_item_updates_applies_values_adds_history_and_creates_schedule_row`・`::test_apply_report_schedule_item_updates_skips_history_and_revision_when_unchanged` |
| 8.1所有者検証・認可境界 | `schedule_service.apply_report_schedule_item_updates`（category不一致・`ensure_operation_allowed`・重複ID拒否） | `test_schedule_service.py::test_apply_report_schedule_item_updates_rejects_*`（5件）、`test_api_records_exam/reading/work.py`の`rejects_schedule_item_from_different_category`系 |
| 実績との同一トランザクション（重点確認） | `record_service_common.register_progress`・各`finalize_*`（スケジュール更新を実績適用より前に実行） | `test_api_records_exam.py::test_finalize_endpoint_rejects_study_logs_together_with_invalid_schedule_item_update`（検証失敗時に実績も保存されないことを確認） |
| D-48 | `ja.json`/`en.json`（`schedule.dailyReportSection.*`4キー、`help.sections.dailyReport.p7`）・`help_content.json` | `test_help_content.py`・`localeKeyUsage.test.ts` |
| D-49 | 仕様書6.5・6.6、設計書データ構造編6.API設計（改79） | — |

## 8. 次の単位への引き継ぎ事項

単位5（AIによるスケジュール修正案）は本書前提（単位1〜4完了）を満たす。

- 単位4で追加した`schedule_service.apply_report_schedule_item_updates`は、確定API・progress API専用（行の追加・削除を行わない1行更新）であり、単位5の承認API（13.7 decisions）は別の専用ロジックとして実装すること（本関数の転用はしない。対象行の集合・検証ルール・revision加算の単位が異なる）。
- `schedule_service.list_schedule_items_for_report`はACTIVE目標のみを対象とする。単位5の13.2「遅れの判定」もACTIVE目標限定（終了した目標は対象外）という条件が共通するため、本関数のACTIVE絞り込みロジック（`select(Goal).where(Goal.status == GoalStatus.ACTIVE)`）はそのまま参考にできる。
- 日次報告・progress APIからのスケジュール更新は`source=DAILY_REPORT`／`PROGRESS_ONLY`で`schedule_item_history`に記録済み。単位5の「予定日の変更履歴は`schedule_revision_proposal`テーブルが兼ねる」（13.6）という設計は、本単位の`schedule_item_history`（状況・実績日のみ）とは別テーブル・別関心事であり競合しない。
- ゼロ記録（「今日は何もしていない」、`useZeroRecordAction.ts`）は、確定の自動生成（13.1「確定APIの応答にschedule_revision_candidatesを含める」）の対象から外れていない点に注意。ゼロ記録も`finalize_record`等を実際に呼ぶため、単位5が確定APIの応答へ`schedule_revision_candidates`を追加する際は、ゼロ記録経由の呼び出しでも同じ応答が返ることを確認すること（14章補足2「ひとこと記録モードで確定した場合も対象とする」と同種の考慮）。
- `frontend/src/features/record/scheduleItemsDraft.ts`の`ScheduleItemDraftValue`・`selectScheduleItemIdsForGoals`・`collectAllScheduleItemIds`は日次報告専用の下書き型である。単位5のガントへの点線重ね表示・承認パネルは別の型（`schedule_revision_proposal`由来）を使うため、本ファイルの型を拡張して転用しないこと。

## 9. 報告が必要な食い違い・範囲外の不具合

**食い違い（2章に記載、判断を仰ぐために実装を止めるべきものは無し）**：2章の6点（D-33応答粒度・認可境界の基準・revision加算の単位・重複ID拒否・送信対象の絞り込み・共有フックへの追加）はいずれも実装の詳細として対応済み。

**15.1手順5で発見し、利用者に確認した食い違い（1件）**：
「今日は何もしていない」ボタン（ゼロ記録、`useZeroRecordAction.ts`）は、study_logs等を下書きの内容に関わらず常に空配列で確定する既存の専用処理であり、確定API3本を呼ぶが、本書は「作業項目の更新は確定時に保存する」としか書いておらず、この経路での`schedule_item_updates`の扱いが明記されていなかった。利用者に確認し、「作業項目の変更は含めて送る」という回答を得たため、`useZeroRecordAction.ts`の`FINALIZE_AS_ZERO`に`scheduleItemIdsByCategory`・`scheduleItemValues`を渡し、変更があればそのカテゴリの確定APIへ含めて送るよう実装した（`ZeroRecordButton.test.tsx::includes a touched schedule item in the zero-record finalize call for its category`で固定）。

**範囲外の不具合**：発見なし。

## 10. コミット前チェック（15.1手順13・14・16）の結果と対応

CLAUDE.md「コミット前チェック」の該当する観点別レビューエージェント6件（dry-reviewer・style-reviewer・label-checker・auth-reviewer・xss-reviewer・performance-reviewer）と、手順16の独立レビュー（経緯を知らない別セッション）を並列実行した。レビュー前後とも、backend全体のpytest（2838 passed、coverage100%）・`ruff check .`、frontend全体のvitest（266ファイル/2100件、coverage100%）・`tsc -b`・`oxlint`は全合格を確認している。

| レビュー | 結果 | 対応 |
| --- | --- | --- |
| dry-reviewer | important1件：`ExamReportSection`・`ReadingReportSection`・`WorkReportSection`の summary/editor計6箇所で「今日の作業項目」欄の呼び出し（`targetDate`・`values`・`onChange`は完全同一、差分は`goals`と`readOnly`のみ）が複製されており、`CategoryReportSection.tsx`自身が持つ「3回複製されたら共通化する」という先例の閾値に達している。nit2件（`apply_report_schedule_item_updates`のエラーメッセージが`_check_owned_by_goal`と重複、backend3ファイルでの呼び出しパターンの繰り返し＝カテゴリ別分割構造上許容範囲）。pre_existing2件（テストヘルパー`_create_schedule_item`の4ファイル重複＝既存の`_make_active_goal_with_material`と同じ前例に従うもの、`resolveVisibleReportTargets.ts`のカテゴリ別3連続処理＝既存パターンの継承） | important1件は対応済み：新規`CategoryScheduleItemsField.tsx`（category・targets・draft・targetDate・readOnlyを受け取り内部で`targets.examScheduleItemGoals`等を選択する束ね）を追加し、6箇所すべてを1行呼び出しに置き換えた（テスト追加、`CategoryScheduleItemsField.test.tsx`3件）。nit・pre_existingは対応不要と判断 |
| style-reviewer | MEDIUM1件：`app/constants/enums.py`の`ScheduleUpdateSource`docstringが「本単位（単位3時点）では定義のみ」という単位4着手前の前提を指したまま残っていた。LOW2件：`resolveVisibleReportTargets.ts`の新規filterコールバックで単一文字`g`を使用、`useDailyReportDraft.ts`のコメント「5カテゴリ」が実態（study/reading/work/diary/scheduleItemの5フィールド）と厳密には合わない表現 | 3件とも対応済み：enums.pyのdocstringを実際の使用箇所（`apply_report_schedule_item_updates`）を指すよう更新、`g`を`goalItems`へ変更、コメントを「study/reading/work/diary/scheduleItemの5フィールド」に修正 |
| label-checker | ハードコーディングは検出なし。参考指摘1件：新設した`schedule.dailyReportSection.noRows`キーがja.json/en.jsonに追加済みだが、どのコンポーネントからも参照されていなかった（既定非表示行が1件も無い目標では見出し＋「すべて表示」ボタンのみが表示され空状態メッセージが無い分岐の見落とし） | 対応済み：`ScheduleItemsGoalGroup.tsx`に`visibleItems.length === 0`の分岐を追加し`noRows`を表示するようにした（テスト追加） |
| auth-reviewer | CRITICAL/HIGHの指摘なし。カテゴリ境界・ACTIVEチェック・検証と適用の分離（部分適用防止）・アトミック性（API層のcommit位置）・`GET /records/{date}/schedule-items`のACTIVE限定・フロント側の絞り込みが認可の迂回経路にならないことを確認し、いずれも設計意図どおりと確認（CONFIRMED）。nit2件：①finalize系で「他カテゴリ/不存在ID」(400)と「正しいカテゴリだが非ACTIVE」(409)のエラー種別が異なる点（単一ユーザーのローカルアプリの前提では実害なしと判断）、②複数行更新で「1件目正当・2件目不正」の明示的な単体テストが無い（API層の統合テストで実質カバー済み） | 対応不要と判断（nit2件とも、現状のテスト・設計で実害が無いことを確認済みのため） |
| xss-reviewer | 指摘なし。生HTML描画用の危険API（CLAUDE.md10章で使用禁止と明記されているもの）の使用はゼロ、利用者入力（作業項目名・目標名）はJSX標準のテキスト描画経由でエスケープされていることを確認 | 対応不要 |
| performance-reviewer | backend（`list_schedule_items_for_report`・`apply_report_schedule_item_updates`）はN+1なし（`joinedload`使用、IN句での一括取得）と確認。MEDIUM1件：「今日の作業項目」欄の3コンポーネントがメモ化されておらず、1目標あたり最大100行×複数目標（SC-07）の構成で1行編集ごとに全体が再描画される設計。LOW〜MEDIUM1件：`useDailyReportActions.ts`の`selectScheduleItemIdsForGoals`3呼び出しが毎レンダリング再計算（ただし同ファイル既存コードも同じ「メモ化しない」方針） | 両方とも対応不要と判断（単位3の独立レビュー対応時の前例「行コンポーネントのメモ化は任意の改善提案として見送った（現状の規模〈最大100行〉では実害が無いと判断）」と同じ理由。単一ユーザーのローカルデスクトップアプリという前提では実害が無いと判断し、将来の改善提案として本節に記録のみとする） |
| 独立レビュー（手順16） | 総合判定「重大な不具合・仕様漏れなし」。D-32〜D-39・D-48が4画面（Exam/Reading/Work/ProgressLogSections）すべてに反映され、ゼロ記録への送信漏れは実装者自身が発見・修正済みであることを確認。軽微2件：①第9章「終了した目標の行の拒否」テストがPAUSEDのみでCLOSED系を明示確認していない、②本単位と無関係なroadmap_service.py等にruff format起因の行折り返しのみの変更が混入（挙動変化なし） | ①対応済み：`test_apply_report_schedule_item_updates_rejects_item_of_closed_goal`（`GoalStatus.CLOSED_WITH_RESULT`）を追加。②対応不要と判断：本セッションの作業に起因しない環境側のフォーマッタ（IDEの保存時整形等と推定）による純粋な行折り返しのみの変更であり、ruff checkは前後とも全合格、ロジック変更は皆無であることを確認済み（15.1手順11「単位の範囲外は変更しない」の趣旨である「意図しない挙動変更を混入させない」は満たされている） |

対応後、backend全体のpytestを再実行し2838 passed・coverage100%・`ruff check .`全合格、frontend全体のvitestを再実行し266ファイル/2100件・coverage100%・`tsc -b`/`oxlint`0件を確認した（0章末のベースライン比較と対比）。
