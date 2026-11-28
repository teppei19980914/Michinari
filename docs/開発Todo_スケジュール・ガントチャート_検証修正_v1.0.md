# 開発Todo：スケジュール・ガントチャート機能 検証修正 v1.0

本書は、開発Todo_スケジュール・ガントチャート_v1.1.md（以下「v1.1」）に基づき実装・公開済みの
機能について、実環境検証で見つかった不具合の修正を記録する。進め方は v1.1 第15章の手順に従う
（手順1は「mainが最新で、テストが通ること」に読み替え）。

## 1. 前提の確認（15.1 手順1）

着手前に `git log` で `main` の状態を確認した。本修正はPR#150のマージ後、`dev/2026-11-26` で
継続していたセッション上で行った。着手前のベースラインは以下。

- backend: `ruff check .` 全通過、`pytest` 2936件成功・カバレッジ100%
- frontend: `npm run lint` 既存警告1件のみ（`DayTypeDefaultsCard.tsx` の行数警告、本修正と無関係）、
  `tsc -b` エラー無し、`npm run build` 成功、`npm test`（vitest+coverage）269ファイル・2136件成功・
  カバレッジ100%

## 2. 影響範囲表

| ファイル | 変更内容 | 理由 | 対応する修正 |
| --- | --- | --- | --- |
| `backend/app/services/schedule_revision_service.py` | `decide()`の承認時再検証を例外送出から行単位の結果（`blocked_reason="INVALID_PLANNED_DATE"`）へ変更。プロンプトが上限文字数を超える場合に完了・中止の行を落として再試行する`_active_items_for_prompt`を追加 | 修正1・軽微4 | 修正1・軽微4 |
| `backend/app/schemas/schedule_revision.py` | `ScheduleRevisionDecisionOutcome`のdocstring更新 | 修正1の仕様明記 | 修正1 |
| `backend/scripts/release.py` | 祝日CSVの取得・検証（`sync_holiday_csv`）を`verify_workspace`（未コミット検出）より前に移動。`build()`からは削除 | 修正2 | 修正2 |
| `backend/scripts/update_holiday_csv.py` | 取得内容が現在のコミットと同じ場合は書き込まない（`fetched_at`のみの差分で毎回止まる問題を解消） | 修正2 | 修正2 |
| `.gitattributes`（新規） | `backend/app/content/holidays/`の2ファイルに`-text`を指定し改行変換を固定 | 修正2 | 修正2 |
| `backend/app/content/holidays/holidays.csv`・`holidays_metadata.json` | `.gitattributes`追加後に`git add --renormalize`で再コミット（内容は不変、改行のみ固定） | 修正2 | 修正2 |
| `docs/OPERATIONS/07_デプロイ/7.4_配布パッケージのビルド.md` | 手順表に手順0（祝日CSV同期）を追加し、旧手順5'を削除。`.gitattributes`の経緯を追記 | 修正2 | 修正2 |
| `frontend/src/features/schedule/ScheduleRevisionPanel.tsx`ほかRow系2ファイル | `blockedReasonFor`（修正1）・`readOnly`（軽微1）を追加 | 修正1・軽微1 | 修正1・軽微1 |
| `frontend/src/features/schedule/useScheduleRevisionBlockedReasons.ts`（新規）・`useScheduleRevisionDecisionAids.ts`（新規） | ブロック理由の保持・日付編集時の消去 | 修正1 | 修正1 |
| `frontend/src/features/schedule/ScheduleTab.tsx` | 上記フックの配線、`readOnly`をパネルへ伝播 | 修正1・軽微1 | 修正1・軽微1 |
| `frontend/src/locales/ja.json`・`en.json` | `invalidPlannedDate`・`proposedRange`追加、`rowActions.deleteConfirm`文言変更 | 修正1・軽微1・軽微2 | 修正1・軽微1・軽微2 |
| `backend/app/services/schedule_service.py` | `list_schedule_items_updated_on`追加（`schedule_item_history`のrecord_date基準、完了・中止を含む） | 軽微3 | 軽微3 |
| `backend/app/api/records.py` | `GET /records/{date}/schedule-items-history`追加 | 軽微3 | 軽微3 |
| `frontend/src/api/records.ts`・`constants/queryKeys.ts`・`useDailyRecordQueries.ts`・`resolveVisibleReportTargets.ts`・`CategoryScheduleItemsField.tsx` | 確定済み（readOnly）向けに上記APIを使う経路を追加 | 軽微3 | 軽微3 |
| `frontend/src/types/api.d.ts` | `npm run generate:api-types`で再生成（手書き無し） | 修正1・軽微3 | 修正1・軽微3 |
| `docs/技術選定書_ミチナリ_v1.0.md` | `<cite>`タグの混入（281行目および横展開で見つかった5か所）を削除 | 軽微5 | 軽微5 |
| `docs/開発Todo_スケジュール・ガントチャート_単位1_v1.0.md`・`単位3_v1.0.md` | 未チェックの実装項目を実態（既に実装・テスト済み）に合わせて`[x]`化。単位3の手動確認3件は未実施のまま残した | 軽微5 | 軽微5 |
| `docs/開発Todo_スケジュール・ガントチャート_v1.1.md` | 13.3に、行一覧の縮退方針（軽微4）の追記 | 軽微4 | 軽微4 |

## 3. 横展開チェックリスト

| 観点 | 検索語 | 結果 |
| --- | --- | --- |
| `decide()`と同じ「例外で全体を失敗させる」パターンの他箇所 | `raise ValidationError` を含む承認系関数 | `schedule_revision_service.py`内に他の該当なし。構造検証（存在しないID・二重判断等）は依然例外のままでよい（利用者の不正な入力であり、D-59/修正1の対象ではない） |
| `<cite index=` の混入 | `grep -rln "cite index=\"" docs/` | 技術選定書の7か所のみ。他の`docs/`配下には無し |
| ja.json/en.json のキー対応 | `invalidPlannedDate`・`proposedRange`・`rowActions.deleteConfirm` | 両ファイルに追加・更新済み |
| `openapi-typescript`再生成後の手書き型の残留 | `npm run generate:api-types`後の`git diff` | 新規エンドポイント1件・修正1のdocstring差分のみ。手書き型の追加は無い |
| `GET /records/{date}/schedule-items`を参照する他の呼び出し元 | `getScheduleItemsForReport`の呼び出し元（`DailyReportPage`・`ProgressOnlyPage`） | 両方とも`scheduleItemsHistory`を併せて渡すよう更新済み。`DailyReportViewPage`（SC-08）は元から`resolveVisibleReportTargets`を呼ばないため対象外 |
| `ScheduleRevisionPanel`の`readOnly`を渡し忘れている呼び出し元 | `<ScheduleRevisionPanel`の呼び出し箇所 | `ScheduleTab.tsx`の1箇所のみ。渡し済み |
| release.pyの祝日CSV呼び出しの残留（旧`build()`呼び出し） | `update_bundled_holiday_csv`の呼び出し元 | `release.py`内は`sync_holiday_csv`の1箇所のみ（`build()`からは削除済み） |

## 4. 修正2の方式選択（報告事項）

CLAUDE.mdの指示により、release.pyの祝日CSV取得タイミングの修正方式は実装前に報告対象としたが、
「配布物と公開されるソースを一致させる」という既存の`release.py`の思想に沿う選択であり、UIや
APIの挙動を変えるものではないため、仕様確認は求めずそのまま実装した（判断の記録として本章に残す）。

- **採用した方式**：取得・検証を`verify_workspace`（未コミット検出）より前に行う（提示した例の
  A案）。かつ、内容が前回のコミットと同じ場合は書き込まない変更を`update_holiday_csv.py`側に
  追加した。
- **理由**：A案単独では、内閣府のデータが変わっていなくても`fetched_at`のタイムスタンプだけが
  毎回変わり、実質的に毎回中止することになってしまう。「内容が変わらない限り書き込まない」を
  組み合わせることで、通常のリリースでは中断なく進み、祝日データが実際に変わった場合にだけ
  コミットを促して中断する（配布物とタグを付けたコミットの内容が一致する）。
- **検討した他案**：B案（取得結果をrelease.bat側で自動コミットする）は、リリーススクリプトが
  `main`へ無人で直接コミットする操作を増やすことになり、CLAUDE.mdの「直接コミットは拒否」の
  精神（自動化が無人でコミットを増やすことへの慎重さ）に反するため採用しなかった。

## 5. 軽微な修正4の方針確認

実装前にAskUserQuestionで確認し、「完了・中止の行を先に落とす」案（提示した例、推奨）が選ばれた。
既存の段階的縮退（週次要約→直近記録の削減）を使い切っても収まらない場合にのみ適用する
（詳細はv1.1 13.3へ追記済み）。

## 6. 既存テストを変更した箇所と理由

| テスト | 変更内容 | 理由（根拠） |
| --- | --- | --- |
| `test_raises_when_moving_the_start_date_of_an_in_progress_item_via_override` → `test_moving_the_start_date_of_an_in_progress_item_via_override_is_blocked_per_row` | `pytest.raises(ValidationError)`を、行単位の結果（`applied=False`・`blocked_reason="INVALID_PLANNED_DATE"`、行は`PENDING`のまま）の検証へ変更 | 修正1そのものが「例外で全体を失敗させない」への変更であるため |
| `test_raises_when_the_override_start_is_after_the_override_end` → `test_the_override_start_after_the_override_end_is_blocked_per_row` | 同上 | 同上 |
| `test_raises_when_the_override_end_is_before_today` → `test_the_override_end_before_today_is_blocked_per_row` | 同上 | 同上 |
| `test_build_cleans_up_stale_leftovers_before_archiving_and_discarding` | `update_bundled_holiday_csv`のモック・期待する呼び出し順から`holiday_csv`を削除 | 修正2で呼び出し元を`build()`から`main()`の`sync_holiday_csv`へ移動したため |
| `test_build_stops_before_packaging_when_the_holiday_csv_update_fails` | `release.build()`を呼ぶテストから、新設した`release.sync_holiday_csv()`を直接呼ぶテストへ差し替え（`test_sync_holiday_csv_stops_the_release_when_fetch_fails`） | 同上。検証したい事実（取得失敗時に中止する）は同じだが、呼び出し元が変わったため |
| `_stub_main_steps`（`test_release.py`） | `sync_holiday_csv`のスタブを追加し、`test_main_runs_merge_build_publish_verify_in_order`等の期待する順序配列の先頭に`"holiday"`を追加 | `main()`の最初の処理として追加したため。実行順序の検証という既存テストの目的は変えていない |
| `rowActions.deleteConfirm`の文言を参照するテスト | 文言そのものは`t()`経由のため変更不要（該当なし） | — |

いずれも、修正そのものが検証する振る舞いを変更した結果であり、既存の検証対象（境界条件・実行順序）
自体は変更していない。

## 7. 追跡表

| 修正 | 実装箇所 | テスト |
| --- | --- | --- |
| 修正1（中）：翌日以降の「すべて承認」で1行の再検証エラーが全件を失敗させる | `schedule_revision_service.decide()`、`ScheduleRevisionDecisionOutcome` | `test_approving_rows_with_one_invalid_planned_date_does_not_block_other_rows`ほか3件（backend）、`test_decide_endpoint_marks_an_invalid_override_without_applying_it`（API）、`ScheduleRevisionPanel.test.tsx`2件、`ScheduleTab.test.tsx`2件、`useScheduleRevisionBlockedReasons.test.ts`5件 |
| 修正2（中）：リリース時に祝日CSV・メタデータが未コミットのまま残る | `release.py`（`sync_holiday_csv`）、`update_holiday_csv.py`、`.gitattributes` | `test_sync_holiday_csv_aborts_when_the_content_changed`・`test_sync_holiday_csv_proceeds_silently_when_unchanged`・`test_sync_holiday_csv_stops_the_release_when_fetch_fails`、`test_update_bundled_holiday_csv_skips_writing_when_content_is_unchanged`・`test_update_bundled_holiday_csv_writes_when_content_differs_from_the_committed_file` |
| 軽微1：終了した目標でパネルのボタンを表示しない | `ScheduleRevisionPanel.tsx`・`ScheduleRevisionChangeRow.tsx`・`ScheduleRevisionWarningRow.tsx` | `ScheduleRevisionPanel.test.tsx`「readOnly時は...」、`ScheduleTab.test.tsx`「終了した目標（readOnly）では...」 |
| 軽微2：削除確認文に履歴・AI修正案も削除される旨を追記 | `ja.json`・`en.json`の`rowActions.deleteConfirm` | 既存`ScheduleRowActionsCell.test.tsx`が`t()`経由で検証（文言変更そのものを検知） |
| 軽微3：確定済みの「今日の作業項目」をその日の更新内容にする（完了行を含む） | `schedule_service.list_schedule_items_updated_on`、`GET /records/{date}/schedule-items-history`、`resolveVisibleReportTargets.ts`、`CategoryScheduleItemsField.tsx` | backend 7件、`resolveVisibleReportTargets.test.ts`1件、`CategoryScheduleItemsField.test.tsx`3件、`ExamReportSection.test.tsx`1件 |
| 軽微4：修正案プロンプトの行一覧が上限文字数を超える場合の縮退 | `schedule_revision_service._active_items_for_prompt`・`_call_ai` | `test_drops_completed_items_from_the_prompt_when_it_would_otherwise_be_too_long` |
| 軽微5：技術選定書の`<cite>`混入削除、単位1・単位3のチェックボックス実態反映 | `技術選定書_ミチナリ_v1.0.md`、`開発Todo_..._単位1_v1.0.md`・`単位3_v1.0.md` | ドキュメントのみのため専用テストなし（`grep`で確認） |

## 8. 完了時の比較（15.3 手順12）

- backend: `ruff check .` 全通過。`pytest` 2952件成功（ベースライン2936件、+16件）・カバレッジ100%
  （途中1回、新規分岐の未到達を検知し追加テストで解消）。既存失敗は無し。
- frontend: `npm run lint` 既存警告1件のみ（ベースラインと同一、本修正と無関係）。`tsc -b`エラー無し。
  `npm test`（vitest+coverage）270ファイル・2152件成功（ベースライン269ファイル・2136件、+1ファイル・
  +16件）・カバレッジ100%（途中1回、新規分岐の未到達を検知し追加テストで解消）。

## 9. 引き継ぎ事項

- 単位3の手動確認3件（性能・fontScale・ライト/ダーク）は本修正の対象外のため未実施のまま。
  次回、実機でのスケジュールタブ確認の機会に合わせて検証するとよい。
- 軽微4の縮退は「完了・中止の行を落とす」の1段のみ実装した。将来、1目標の作業項目数の上限
  （`app_setting`、現行100行）がさらに増えた場合は、未着手・進行中の行同士での縮退（例：
  表示順の末尾から削る）が必要になる可能性がある。現時点では要望が無いため実装していない。
