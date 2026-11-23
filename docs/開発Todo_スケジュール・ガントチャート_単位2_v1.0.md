# 開発Todo：スケジュール・ガントチャート機能 単位2（データモデルとAPI） v1.0

入力: `docs/開発Todo_スケジュール・ガントチャート_v1.1.md`（第2章・第6章・第7章・第8章・第9章単位2・第15章）、`docs/開発Todo_スケジュール・ガントチャート_単位1_v1.0.md`（引き継ぎ事項）。

## 0. ベースライン（着手前に確認）

- 前提確認：単位1（祝日基盤）は実装済み・mainにマージ済み（PR#145、現HEADがmainの祖先であることを確認済み）であり、`GET /holidays`・`calendar_service.get_holiday_coverage`/`list_holidays`が利用可能。
- backend: `ruff check .` → All checks passed。`pytest` → 2741 passed, coverage 100%。
- frontend: `npm run lint`（oxlint、`DayTypeDefaultsCard.tsx`のmax-lines-per-function警告1件のみ。単位1由来の既知の警告で本単位の範囲外）・`npm run build`（tsc -b + vite build, exit 0）・`npm test -- --run`（231 files, 1839 tests, coverage100%, exit 0）。

## 1. 脅威分析（STRIDE、簡易）

`/threat-model`スキルが本セッションで利用不可のため、単位1と同様に手動でSTRIDE分析を実施。

- **データフロー**：[利用者（ローカル単独利用、認証機構は既存のgoal系APIと同一）] → `GET/PUT /goals/{goal_id}/schedule`・`PUT .../view-setting`（HTTP、信頼境界） → `schedule_service`（検証） → `goal_schedule`/`schedule_item`/`schedule_column`/`schedule_cell`/`schedule_item_history`（DB）
- **S（なりすまし）**：既存のgoal系APIと同じ依存注入（`get_db`）を使い、新たな認証機構は追加しない。本アプリは単独利用のローカルデスクトップアプリであり、ユーザー間の認可（他ユーザーからの保護）は対象外。目標間の認可境界（下記E参照）が本機能固有の論点。
- **T（改ざん）**：入力検証をサービス層の1か所（`schedule_service.validate_item_fields`等）に集約。SQLインジェクション対策はSQLAlchemyのパラメータ化クエリに委ね（生SQL文字列結合は使用しない）、XSS対策は表示側（単位3）の責務とし、保存層では無害化せずそのまま保存・返却する（SQLi/XSSペイロードを含む文字がそのまま保存・取得されることをテストで確認）。
- **R（否認）**：`schedule_item_history`に状況・実績日の更新履歴（更新元・変更後の値・変更時刻）を記録する。
- **I（情報漏洩）**：`GET /goals/{goal_id}/schedule`は対象目標のデータのみを返す。他の目標に属するID（存在しないIDとの区別をしない）を送った場合もエラーメッセージから他目標の存在を推測できないようにする。
- **D（サービス停止）**：行100件・列10列の上限を`app_setting`（`schedule.max_items`・`schedule.max_custom_columns`）で制御。
- **E（権限昇格）**：一括保存（PUT）で送信された行・列IDが対象の目標に属さない場合は拒否する（認可境界のテストを必須、8.1）。

対策はすべて「Mitigate」として実装済み（下記2章・6章参照）。受容したリスクなし。

## 2. 影響範囲表

| ファイル | 変更内容 | 理由 | D-ID |
| --- | --- | --- | --- |
| `backend/app/constants/enums.py` | `ScheduleItemStatus`・`ScheduleUpdateSource`・`ScheduleColumnType`を追加 | 第7.2章 | D-10,D-39,D-12 |
| `backend/app/models/schedule.py`（新規） | `GoalSchedule`・`ScheduleItem`・`ScheduleColumn`・`ScheduleCell`・`ScheduleItemHistory`を追加 | 第7.1章 | D-07,D-08,D-12,D-24,D-39 |
| `backend/app/models/goal.py` | `Goal`へ`schedule`（uselist=False）・`schedule_items`・`schedule_columns`のrelationship（cascade="all, delete-orphan"）を追加 | 第7.3章 | — |
| `backend/app/models/__init__.py` | 新規モデルをインポート（`Base.metadata`への登録） | 既存の慣例 | — |
| `backend/alembic/versions/b4bff554312c_schedule_tables.py`（新規） | 新規5テーブルの`create_table`のみ（既存テーブルの変更なし） | 第7章 | — |
| `backend/app/constants/app_setting_keys.py` | `SCHEDULE_MAX_CUSTOM_COLUMNS`・`SCHEDULE_MAX_ITEMS`・`SCHEDULE_GANTT_DAY_WIDTH_MIN_REM`・`SCHEDULE_GANTT_DAY_WIDTH_MAX_REM`を追加 | 7.4章 | D-14,D-20 |
| `backend/app/init/seed_data.py` | 上記4キーの初期値を追加（10・100・1.75・4.5） | 7.4章 | D-14,D-20 |
| `backend/app/services/exceptions.py` | `ScheduleRevisionConflictError`を追加 | D-07 | D-07 |
| `backend/app/api/errors.py` | `ScheduleRevisionConflictError`→409 `SCHEDULE_REVISION_CONFLICT`を`_STATUS_AND_CODE`に追加 | D-07 | D-07 |
| `frontend/src/locales/ja.json`・`en.json` | `errors.SCHEDULE_REVISION_CONFLICT`の文言を追加 | ゼロハードコーディング、`test_every_error_code_has_a_frontend_message`要求 | D-07 |
| `backend/app/schemas/schedule.py`（新規） | `Schedule*Input`/`Read`/`ScheduleSaveRequest`/`ScheduleViewSetting*` | 第8章 | 第8章全体 |
| `backend/app/services/schedule_service.py`（新規） | `validate_item_fields`（6.2、単位4再利用想定）、`get_schedule_view`、`save_schedule`（差分適用・revision・履歴）、`update_view_setting` | 第6章・第7章・第8.1章 | D-06,D-07,D-08〜D-11,D-24,D-25,D-39 |
| `backend/app/api/schedule.py`（新規） | `GET`/`PUT /goals/{goal_id}/schedule`、`PUT .../view-setting` | 第8章 | D-01相当（API） |
| `backend/app/main.py` | `schedule_router`を登録 | 既存の慣例 | — |
| `backend/app/services/backup_service.py` | `DATA_SCHEMA_VERSION`を1.9→1.10へ、`_IMPORTABLE_SCHEMA_VERSIONS`に1.9を追加 | 7.5章（15.1手順5、下記3章参照） | 7.5 |
| `backend/tests/schedule_helpers.py`（新規）、`test_schedule_service.py`（新規）、`test_api_schedule.py`（新規）、`test_schemas_schedule.py`（新規） | サービス層・API層・スキーマの単体/結合テスト | 第9章「テスト」項 | 全D-ID |
| `backend/tests/test_models_crud.py` | goal_schedule一意制約・スケジュール全テーブルのCASCADE削除テストを追加 | 第9章「CASCADE削除」 | — |
| `backend/tests/test_migration_data.py` | 新規マイグレーションのupgrade/downgradeテスト（既存目標行の保持を確認） | ユーザー指示（重点確認） | — |
| `frontend/src/types/api.d.ts` | `npm run generate:api-types`で再生成 | 手書き禁止 | 第8章 |
| `docs/設計書_データ構造編_ミチナリ_v1.1.md`・同5.1/5.2/5.4/5.6・06_API設計.md | 新規テーブル・列挙型・設定キー・インデックス・APIを追記、改訂履歴に改77を追加 | D-49 | — |
| `docs/仕様書_ミチナリ_v1.1.md`・同10_バリデーション方針.md | 検証ルール（6.2相当）を追記、改訂履歴に改78を追加。画面仕様は単位3で追記 | D-49 | — |

## 3. 重要な設計判断（仕様に影響しない実装詳細、理由を記録）

1. **`DATA_SCHEMA_VERSION`は1.3ではなく1.10へ上げた。** 本書（v1.1、2026-11-12時点）は「1.2から1.3に上げ」と記すが、単位2着手時点（2026-11-23）のコード上の実際の値はすでに**1.9**だった（単位1〜単位2着手までの間に単語帳機能〈6要件〉が完成し、1.3〜1.9まで version を進めていたため）。これは設計書の記述が書かれた時点からコードベースが並行開発で進んだことによる版数のズレであり、仕様（「版数を1つ上げ、直前の版の取り込みを受け付ける」という意図）自体には影響しない実装の詳細のため、15.1手順5に従い現在の実際の版数を起点に1.10へ上げ、1.9を`_IMPORTABLE_SCHEMA_VERSIONS`に追加した（推測ではなく`backend/app/services/backup_service.py`のコード実態を確認して判断）。
2. **ガントの1日分の幅（`schedule.gantt_day_width_min_rem`/`max_rem`）は暫定値（1.75/4.5）とした。** この設定は単位3（ガント描画）が使う値だが、7.4章の設定一覧に含まれるため単位2で初期値投入まで済ませる。数値根拠：2桁の日付数字が読める幅の下限として1.75rem（既存の`ganttGeometry.ts`にはrem単位の前例が無いため新規に決定）。単位3の影響範囲確定時に、実際のフォント・セル余白を見て見直すことを前提とする。
3. **一括保存（PUT）の所有者検証は、「存在しないID」と「他の目標に属するID」を区別しない。** `material_service._resolve_subjects`の設計（他の目標の存在を推測させる手掛かりを与えない）を踏襲し、いずれも`VALIDATION_ERROR`（400）とした。
4. **固定行数・列数（`PUT .../view-setting`）の範囲外の値は、エラーにせず現在の行数・列数の範囲内へクランプする。** 表示上の設定であり、範囲外の値を保存しても実害が無いため、新たなエラーコードを増やさずに安全側へ丸めた。
5. **検証の共通化（6.1）の範囲は「状況・実績日のルール」に限定した。** `validate_item_fields`は1行分の状況・実績日・必須項目・日付整合のみを検証する小さな関数とし、単位4（日次報告・SC-07の`schedule_item_updates`）から再利用できる形にした。一方、列・行の差分適用・revisionの楽観ロックは一括保存（PUT）専用のロジックであり、単位4では使わない（日次報告は行の追加・削除を行わないため）。

## 4. 回帰の網（15.1手順8、特性テスト）

新規テーブルのみの追加であり、既存の振る舞いを変更する箇所がないため（`Goal`モデルへのrelationship追加はCASCADE方向のみで既存のCRUDの挙動を変えない）、専用の特性テストは不要と判断した。既存の目標の削除・CRUDのテストがすべて無変更で通ることを4章末のベースライン比較で確認する。

## 5. 横展開チェックリスト

| 検索語 | 期待する結果 | 結果 |
| --- | --- | --- |
| `grep -rln "ScheduleItemStatus\|ScheduleColumnType\|ScheduleUpdateSource" backend/app frontend/src` | backendのmodels/schemas/services/constantsと、frontendは自動生成の`api.d.ts`のみ（手書きの分岐が無いこと） | ✅ 確認済み |
| `grep -c "SCHEDULE_REVISION_CONFLICT" frontend/src/locales/ja.json frontend/src/locales/en.json` | 両ファイルに1件ずつ存在 | ✅ 確認済み |
| `npm run generate:api-types` 後の `git diff --stat src/types/api.d.ts` | 追加のみ（手書きの型定義が残っていないこと） | ✅ 確認済み（+300行、追加のみ） |
| `grep -n "DATA_SCHEMA_VERSION\|_IMPORTABLE_SCHEMA_VERSIONS" backend/app/services/backup_service.py` | 1.10へ更新、1.9が取り込み対象に追加されていること | ✅ 確認済み |
| `grep -n "SCHEDULE_" backend/app/services/settings_service.py` | ヒットなし（`vocab.*`と同じ「内部パラメータ・設定画面非表示」の扱いのため、設定画面側の配線は不要） | ✅ 確認済み |
| `backend/app/content/help_content.json` への影響 | 本単位は画面を持たないため対象外（単位3で追記） | 対象外（test_help_content.pyは無変更で通過） |

## 6. チェックリスト（実装）

- [x] 第7.1章：`GoalSchedule`・`ScheduleItem`・`ScheduleColumn`・`ScheduleCell`・`ScheduleItemHistory`モデル
- [x] 第7.2章：`ScheduleItemStatus`・`ScheduleUpdateSource`・`ScheduleColumnType`列挙型
- [x] 第7.3章：`Goal`への3relationship追加
- [x] 第7.4章：`app_setting`初期値4件
- [x] 第7.5章：`DATA_SCHEMA_VERSION`更新・旧版の取り込み（1.9まで）
- [x] Alembicマイグレーション（新規create_tableのみ）、既存DBコピーへのupgrade成功・downgrade成功をテストで確認
- [x] 第6章：検証ルールをサービス層の1か所（`schedule_service.validate_item_fields`等）に集約
- [x] 第8章：`GET`/`PUT /goals/{goal_id}/schedule`、`PUT .../view-setting`
- [x] 第8.1章：差分ルール（行IDを維持、新規列は仮キーで対応付け、所有者検証、revisionの楽観ロック、履歴追加）
- [x] エラーコード化（`SCHEDULE_REVISION_CONFLICT`、`app/api/errors.py`・ja.json/en.json）
- [x] `npm run generate:api-types`
- [x] テスト：検証ルールの全分岐、差分更新（行ID維持）、409、認可境界、SQLi・XSSペイロードの保存/取得、CASCADE削除、マイグレーションupgrade/downgrade

## 7. 追跡表

| D-ID | 実装箇所 | テスト名 |
| --- | --- | --- |
| D-06（行IDを維持する差分更新） | `schedule_service._apply_items`/`_apply_columns` | `test_schedule_service.py::test_save_schedule_preserves_item_id_on_update_diff`、`::test_save_schedule_deletes_items_not_resent`、`::test_save_schedule_deletes_columns_not_resent` |
| D-07（revisionによる楽観ロック・409） | `schedule_service.save_schedule`、`ScheduleRevisionConflictError`、`app/api/errors.py` | `test_schedule_service.py::test_save_schedule_rejects_mismatched_revision`、`test_api_schedule.py::test_put_schedule_rejects_stale_revision` |
| D-08・D-09（既定7列・必須項目） | `models/schedule.py:ScheduleItem`、`schedule_service.validate_item_fields` | `test_schedule_service.py::test_validate_item_fields_rejects_blank_title`、`::test_validate_item_fields_rejects_planned_start_after_end` |
| D-10（状況・実績日の条件付き必須） | `schedule_service.validate_item_fields` | `test_schedule_service.py::test_validate_item_fields_*`（NOT_STARTED/IN_PROGRESS/DONE/CANCELLEDの各分岐、計12件） |
| D-11（実績日は本日以前） | `schedule_service.validate_item_fields` | `test_schedule_service.py::test_validate_item_fields_rejects_actual_start_date_in_future`、`::test_validate_item_fields_rejects_actual_end_date_in_future`、`::test_validate_item_fields_accepts_actual_date_equal_to_today` |
| D-12（追加列はテキスト型のみ、名前必須・重複不可） | `models/schedule.py:ScheduleColumn`、`schedule_service._validate_columns` | `test_schedule_service.py::test_save_schedule_rejects_blank_column_name`、`::test_save_schedule_rejects_duplicate_column_name`、`::test_save_schedule_rejects_duplicate_temp_key` |
| D-14（上限：追加列10・行100） | `app_setting_keys.SCHEDULE_MAX_CUSTOM_COLUMNS/MAX_ITEMS`、`schedule_service.save_schedule` | `test_schedule_service.py::test_save_schedule_rejects_too_many_custom_columns`、`::test_save_schedule_rejects_too_many_items` |
| D-20（ガントの日付幅設定の初期値投入） | `app_setting_keys.SCHEDULE_GANTT_DAY_WIDTH_MIN/MAX_REM`、`seed_data.py` | （値投入のみ、単位3で描画テスト予定） |
| D-24・D-25（固定行数・列数の保存） | `schedule_service.update_view_setting`、`api/schedule.py` | `test_schedule_service.py::test_update_view_setting_*`（3件）、`test_api_schedule.py::test_put_view_setting_updates_without_changing_revision` |
| D-39（更新履歴） | `models/schedule.py:ScheduleItemHistory`、`schedule_service._apply_items` | `test_schedule_service.py::test_save_schedule_only_adds_history_when_status_or_actual_dates_change` |
| D-41（本機能データをAIプロンプト・ナレッジエクスポートに含めない） | 本単位ではAI連携自体を実装しないため該当コードなし（単位5で確認） | — |
| 8.1「所有者の検証」（認可境界） | `schedule_service._validate_columns`/`_validate_items` | `test_schedule_service.py::test_save_schedule_rejects_item_id_from_another_goal`、`::test_save_schedule_rejects_column_id_from_another_goal`、`test_api_schedule.py::test_put_schedule_rejects_item_id_belonging_to_another_goal`、`::test_put_schedule_rejects_column_id_belonging_to_another_goal` |
| 8.1「新規列への値の紐付け」（仮キー） | `schedule_service._column_key`/`_apply_columns`/`_apply_cells` | `test_schedule_service.py::test_save_schedule_creates_items_and_columns_and_bumps_revision`、`test_api_schedule.py::test_put_schedule_creates_item_and_column_and_returns_assigned_ids` |
| 7.1「セルが空になったら行ごと削除する」 | `schedule_service._apply_cells` | `test_schedule_service.py::test_save_schedule_clears_cell_when_value_is_blank`、`::test_save_schedule_leaves_cell_absent_when_blank_from_the_start`、`::test_save_schedule_updates_existing_cell_value` |
| 6.2「目標の状態（終了した目標は拒否）」 | `goal_service.ensure_goal_editable`（既存、`schedule_service.save_schedule`/`update_view_setting`から呼ぶ） | `test_schedule_service.py::test_save_schedule_rejects_closed_goal`、`::test_update_view_setting_rejects_closed_goal`、`test_api_schedule.py::test_put_schedule_rejects_closed_goal`、`::test_put_view_setting_rejects_closed_goal` |
| CASCADE削除（目標削除でスケジュールデータも削除） | `models/goal.py`のrelationship、DB側のON DELETE CASCADE | `test_models_crud.py::test_schedule_tables_cascade_delete_with_goal`、`::test_goal_schedule_goal_id_unique_constraint` |
| 既存の目標削除テストの無変更 | — | 既存の`test_models_crud.py`・`test_api_goals.py`の削除系テストを無変更のまま実行し合格（全体テスト2797件に包含） |
| SQLi・XSSペイロードの保存・取得 | `schedule_service`（パラメータ化クエリ前提、無害化しない） | `test_api_schedule.py::test_put_schedule_stores_and_returns_sql_and_xss_payloads_verbatim` |
| マイグレーションのupgrade/downgrade | `alembic/versions/b4bff554312c_schedule_tables.py` | `test_migration_data.py::test_schedule_tables_migration_upgrade_preserves_existing_goal_rows`、`::test_schedule_tables_migration_downgrade_drops_new_tables_only` |
| APIの型再生成 | `frontend/src/types/api.d.ts` | `npm run generate:api-types`実行済み（手動確認、専用テストなし） |

## 8. 次の単位への引き継ぎ事項

- `GET/PUT /goals/{goal_id}/schedule`・`PUT .../view-setting`は単位2で用意済み。単位3（スケジュールタブ）はこのAPIをそのまま使い、`ScheduleRead`の`today`・`columns`・`items`（各`cells`を`column_id`キーのマップとして含む）をそのまま描画に使える。
- `schedule_service.validate_item_fields`は単位4（日次報告・SC-07）から直接呼べる形で用意済み（1行分の状況・実績日の検証のみを担う小さな関数）。列・行の差分適用（`save_schedule`）は一括保存専用であり単位4では使わない。
- `schedule.gantt_day_width_min_rem`/`max_rem`は暫定値（1.75/4.5rem）。単位3の影響範囲確定時に、実際のフォント・セル余白を見て妥当性を見直すこと（3章の重要な設計判断2参照）。
- `ScheduleUpdateSource`に`DAILY_REPORT`・`PROGRESS_ONLY`を既に定義済み（単位2では未使用）。単位4で`schedule_item_history`へ追加する際にそのまま使える。
- `DATA_SCHEMA_VERSION`は1.10。単位5（AI修正案）で`schedule_revision_proposal`等の新規テーブルを追加する際は、次の版（1.11）へ上げ、1.10の書き出しの取り込みも受け付けること（本単位と同じ運用）。
- 単位3の着手時、`docs/技術選定書_ミチナリ_v1.0.md`4.3の改訂（D-49）と`help_content.json`の更新が必要（本単位は画面を持たないため対象外とした）。

## 9. 報告が必要な食い違い・範囲外の不具合

- **食い違い（15.1手順5で解決済み、報告のみ）**：本書（v1.1）7.5章の「`DATA_SCHEMA_VERSION`を1.2から1.3に上げ」は、本書執筆時点（2026-11-12）のコードの実際の値を前提とした記述だが、単位2着手時点（2026-11-23）には他機能（単語帳）により実際の値は1.9まで進んでいた。版数を1つ上げ直前の版の取り込みを受け付けるという仕様の意図は変わらないため、現在の実際の値を起点に1.10へ上げて対応した（3章「重要な設計判断1」参照、判断を仰ぐために実装を止めるべき食い違いではないと判断）。
- **範囲外の不具合**：発見なし。
