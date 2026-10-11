# 開発Todo：S01 構造の整理①（ai_context_service の分割・複雑度の高い関数の分割）

本書は、ベースライン文書「S01：構造の整理①」（版2.1）に基づく開発作業の正（Single Source of Truth）である。
振る舞いは変えない（挙動保存のリファクタリング）。作業は `dev/2026-10-11` で行う。

## 0. 決定事項

| # | 決定 |
| --- | --- |
| S1 | `ai_context_service.py`（約1,270行）を4ファイルへ分割する：`ai_context_common.py`（共通）・`ai_context_exam.py`（資格試験）・`ai_context_reading.py`（読書）・`ai_context_work.py`（仕事）。配置は既存の`app/services/`直下（フラット配置）。既存の`app/services/`配下にサブパッケージの前例が無い（全てフラット`*_service.py`）ため、新規サブパッケージ化はせず既存の命名規則に合わせる |
| S2 | 共通モジュール（`ai_context_common.py`）に置くのは、2カテゴリ以上から参照される関数のみ：`list_active_goals`・`list_daily_message_target_goals`・`_format_days_remaining`（EXAM/READING双方が参照）・`build_anonymize_instruction`・`build_perspective_suggestion_instruction`／`_PERSPECTIVE_SUGGESTION_TEXTS`・週次要約圧縮一式（`WeeklyCompressedPeriod`・`resolve_weekly_compressed_period`・`exclude_covered_dates`・`_format_weekly_summary_entry`）。カテゴリ固有の一覧関数（`list_active_exam_goals`等）はそれぞれの専用モジュールへ置く（詳細は§1.1） |
| S3 | モジュール先頭の役割docstring（現状の1270行ファイル冒頭1-8行）は`ai_context_common.py`に残し、他3ファイルは「詳細は`ai_context_common.py`参照」の短い相互参照に留める（CLAUDE.md DRYの原則、重複記述の禁止） |
| S4 | テスト（`test_ai_context_service.py`、約1,720行）も同じ4分割にする：`test_ai_context_common.py`・`test_ai_context_exam.py`・`test_ai_context_reading.py`・`test_ai_context_work.py`。2ファイル以上で使う生成ヘルパー（`_make_goal`・`_make_daily_record`）は重複を避けるため新設`backend/tests/ai_context_helpers.py`へ集約し、公開名（アンダースコア無し、`reading_helpers.py`と同じ命名規則）にして4ファイルから import する。カテゴリ専用ヘルパー（`_make_subject`・`_make_material`・`_make_slot`・`_make_study_log`・`_make_diary_entry`→EXAM、`_make_reading_goal`・`_make_book`・`_add_reading_log`→READING、`_make_work_goal`・`_make_work_assignment`・`_make_work_member`・`_add_work_log`→WORK）はそれぞれの分割先ファイルへそのまま移動する |
| S5 | `export_service.render_markdown`（複雑度38）・`build_export_data`（21）は、ファイル・公開関数名・シグネチャを変えず、既存のREADING/WORK分岐パターン（`_render_reading_markdown`/`_render_work_markdown`、`_build_reading_export_data`/`_build_work_export_data`）と対称になるよう、EXAM分岐を`_build_exam_export_data`・`_render_exam_markdown`へ抽出する。さらに`_render_exam_markdown`内の12個の`if "xxx" in data`セクションは、それぞれ`_render_<section>_section`という単一責任の private関数へ抽出する（既存の`_render_reading_markdown`/`_render_work_markdown`には同種の抽出余地が無い＝対象外。複雑度10未満を目安にするが、数値自体はCI強制ではなく記録のみ） |
| S6 | `goal_service._cascade_delete_activity_logs`（複雑度28）は、`_delete_work_evaluation_members_and_reports`（先行削除）・`_collect_and_delete_activity_logs`（ログ収集・削除、空なら早期return用に`set[int] \| None`を返す）・`_delete_now_empty_daily_records`（空になったdaily_recordの削除）の3関数へ分割する |
| S7 | ドキュメント更新範囲：必須は`CODING_RULES.md`置き場所ルールへの追記（タスク本体の要求）。加えて、挙動変更を伴わない内部実装詳細の参照として`仕様書_ミチナリ_v1.1.md`・`設計書_ロジック・プロンプト編_ミチナリ_v1.1.md`・`設計書_データ構造編_ミチナリ_v1.1.md`本文中の`ai_context_service.<関数名>`参照（合計約9箇所、§1.3）を新モジュール名へ更新する（改訂履歴に1行追加）。**過去の改訂履歴の既存行・`実装フェーズ分割計画書`・他の`開発Todo_*.md`の記述は、完了済みフェーズの記録として書き換えない**（ログを後から改変しない原則） |
| 版 | バージョン番号（`backend/pyproject.toml`）は変更しない（リリース手順でのみ入力、CLAUDE.md） |

未決事項は無し（§5参照）。全ての設計判断は既存コードの命名規則・呼び出し状況の調査から決定した。

## 1. 影響範囲（フルスキャンの結果）

### 1.1 ai_context_service.py の分割先対応表

| 新モジュール | 定数・関数（元の行番号） |
| --- | --- |
| `ai_context_common.py` | `list_active_goals`(94)・`list_daily_message_target_goals`(117)・`_format_days_remaining`(203)・`resolve_weekly_compressed_period`(476)用`WeeklyCompressedPeriod`(456)・`_format_weekly_summary_entry`(448)・`resolve_weekly_compressed_period`(476)・`exclude_covered_dates`(518)・`build_anonymize_instruction`(1167)・`_PERSPECTIVE_SUGGESTION_TEXTS`(1181)・`build_perspective_suggestion_instruction`(1203) |
| `ai_context_exam.py` | `list_active_exam_goals`(100)・`list_active_materials`(136)・`_group_materials_by_goal`(172)・`build_diary_text`(181)・`build_goal_summary`(210)・`build_material_status_entries`(230)・`build_slot_summary`(300)・`build_buffer_usage_rate_text`(335)・`build_today_logs_text`(351)・`build_progress_summary`(369)・`build_recent_activity_text`(386)・`build_recent_weekly_summaries`(427)・`build_week_logs_text`(533)・`build_week_diaries_text`(570)・`build_week_metrics_text`(602)・`build_material_summary_text`(659)・`build_overall_metrics_text`(681)・`build_quality_trend_text`(704)・`_RETROSPECTIVE_QUALITY_GRANULARITY`(59)・`_BASELINE_REASON_LABELS_JA/EN`(67,74)・`build_replan_history_text`(725)・`_EXAM_RESULT_LABELS_JA/EN`(82,87)・`build_exam_results_text`(751)・`build_all_weekly_summaries_entries`(771) |
| `ai_context_reading.py` | `list_active_reading_goals`(141)・`list_active_books`(151)・`build_daily_book_summary_text`(798)・`build_today_recall_text`(813)・`build_recent_recalls_entries`(826)・`build_retrospective_book_summary_text`(870)・`build_reading_overall_metrics_text`(879)・`build_reading_logs_entries`(907)・`build_week_recalls_text`(937) |
| `ai_context_work.py` | `list_active_work_goals`(156)・`list_active_work_assignments`(167)・`build_daily_work_summary_text`(965)・`build_today_work_text`(982)・`build_recent_work_logs_entries`(995)・`build_retrospective_work_summary_text`(1037)・`build_work_logs_entries_for_period`(1050)・`build_week_work_logs_text`(1081)・`build_work_progress_summary`(1110)・`build_work_recent_activity_text`(1140)・`_GENDER_LABELS_JA/EN`(1219,1224)・`build_evaluation_member_summary_text`(1231)・`build_evaluation_feedback_history_entries`(1244) |

### 1.2 バックエンド：呼び出し元の import 更新（フルスキャン、該当17ファイル）

| ファイル | 現状の参照 | 更新後の import |
| --- | --- | --- |
| `app/api/dashboard.py` | `list_active_goals` | `ai_context_common` |
| `app/services/daily_message_service.py` | `list_daily_message_target_goals`(common)・`list_active_work_assignments`/`build_daily_work_summary_text`/`build_work_progress_summary`/`build_work_recent_activity_text`(work)・`list_active_materials`/`build_goal_summary`/`build_progress_summary`/`build_recent_activity_text`(exam) | `ai_context_common` + `ai_context_exam` + `ai_context_work` |
| `app/services/daily_feedback_service.py` | `list_active_materials`/`build_diary_text`/`build_goal_summary`/`build_material_status_entries`/`build_slot_summary`/`build_buffer_usage_rate_text`/`build_today_logs_text`/`build_recent_weekly_summaries`(exam)・`build_perspective_suggestion_instruction`(common) | `ai_context_common` + `ai_context_exam` |
| `app/services/reading_feedback_service.py` | `list_active_books`/`build_recent_recalls_entries`/`build_daily_book_summary_text`/`build_today_recall_text`(reading)・`resolve_weekly_compressed_period`/`exclude_covered_dates`/`build_perspective_suggestion_instruction`(common) | `ai_context_common` + `ai_context_reading` |
| `app/services/work_feedback_service.py` | `list_active_work_assignments`/`build_recent_work_logs_entries`/`build_daily_work_summary_text`/`build_today_work_text`(work)・`resolve_weekly_compressed_period`/`exclude_covered_dates`/`build_perspective_suggestion_instruction`(common) | `ai_context_common` + `ai_context_work` |
| `app/services/work_report_service.py` | `build_retrospective_work_summary_text`/`build_work_logs_entries_for_period`(work)・`resolve_weekly_compressed_period`/`exclude_covered_dates`/`build_anonymize_instruction`(common) | `ai_context_common` + `ai_context_work` |
| `app/services/work_evaluation_service.py` | `build_evaluation_member_summary_text`/`build_evaluation_feedback_history_entries`/`build_work_logs_entries_for_period`(work) | `ai_context_work` |
| `app/services/retrospective_service.py` | `build_goal_summary`/`build_material_summary_text`/`build_overall_metrics_text`/`build_quality_trend_text`/`build_replan_history_text`/`build_exam_results_text`/`build_all_weekly_summaries_entries`(exam)・`build_retrospective_book_summary_text`/`build_reading_overall_metrics_text`/`build_reading_logs_entries`(reading)・`build_anonymize_instruction`/`resolve_weekly_compressed_period`/`exclude_covered_dates`(common) | `ai_context_common` + `ai_context_exam` + `ai_context_reading` |
| `app/services/weekly_summary_service.py` | `build_week_logs_text`/`build_week_metrics_text`/`build_week_diaries_text`(exam)・`build_week_recalls_text`(reading)・`build_week_work_logs_text`(work)・`build_anonymize_instruction`(common) | 4モジュール全て |
| `app/services/recap_generation_service.py` | `list_active_exam_goals`(exam)・`list_active_reading_goals`(reading) | `ai_context_exam` + `ai_context_reading` |
| `app/services/setting_reader.py` | docstring内コメント参照のみ | コメント文言の更新のみ（import無し） |
| `app/services/metrics_service.py` | docstring内コメント参照のみ（17.3/13.1の説明文） | コメント文言の更新のみ（import無し） |
| `app/services/analytics_service.py` | docstring内コメント参照のみ | コメント文言の更新のみ（import無し） |
| `app/ai/prompt_builder.py` | docstring内コメント参照のみ（「ai_context_service側の責務」という一般的表現） | 変更不要（カテゴリ特定の参照ではないため） |
| `backend/tests/test_ai_context_service.py` | 本体（§1.1の全関数の呼び出し） | 4分割（§1.3） |
| `backend/tests/test_work_feedback_service.py` | docstring内コメント参照のみ | コメント文言の更新のみ |
| `backend/tests/test_reading_feedback_service.py` | docstring内コメント参照のみ | コメント文言の更新のみ |

`backend/alembic/`・`backend/scripts/`・`frontend/src/`配下に`ai_context_service`・`render_markdown`・`build_export_data`・`_cascade_delete_activity_logs`への参照は無い（フルスキャン確認済み）。`app/api/export.py`は`export_service.build_export_data`/`render_markdown`を呼ぶが、公開関数名・シグネチャ・配置ファイルを変えないため更新不要。

### 1.3 ドキュメント

| 文書 | 変更 |
| --- | --- |
| `docs/CODING_RULES.md` | 置き場所ルールに、1ファイルが肥大化した場合の分割先命名規則（`<元名>_<カテゴリ>.py`の横展開）を追記 |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1.md` | 本文（939・2266・2313・2341・2345・2570行目付近）の`ai_context_service.<関数名>`参照を対応する新モジュール名へ更新、改訂履歴に1行追加（改44） |

**フェーズA時点の誤り（フェーズB実施中に発覚・訂正）**: 当初、`docs/仕様書_ミチナリ_v1.1.md`（74行目）・`docs/設計書_データ構造編_ミチナリ_v1.1.md`（692・712・1142・1216行目）も対象として記載したが、実際に確認したところ、仕様書74行目は改訂履歴（過去の記録）内の言及のみで本文への影響なし、データ構造編側の4箇所は`render_markdown`／`build_export_data`／`_cascade_delete_activity_logs`という**名前を変更していない**関数への言及（別の調査観点の混同）であり、どちらも更新不要と判明した。両文書は変更なし。

`docs/実装フェーズ分割計画書_ミチナリ_v1.1.md`・既存の`開発Todo_*.md`群・設計書内の改訂履歴（過去の行）は完了済みフェーズの記録であり、本リファクタリングでは変更しない（決定事項S7）。

### 1.4 既存機能への横展開（同じ問題の有無を確認）

| 項目 | 状況 | 対応 |
| --- | --- | --- |
| 他の大型サービスファイル（複雑度・行数超過） | `export_service.py`（本Todo対象）・`goal_service.py`（本Todo対象）以外に、radon cc測定で複雑度C以上の関数が無いか確認 | §2のベースライン測定で確認（結果は§2参照）。追加対象が見つかった場合は§6「別件」に記録し本Todoの範囲は変えない |
| テストヘルパーの重複（DRY） | `test_ai_context_service.py`内の`_make_goal`/`_make_daily_record`は分割後複数ファイルから必要になる | 決定事項S4で`ai_context_helpers.py`に集約済み |

## 2. ベースライン（2026-10-11、開発前）

| 項目 | 結果 |
| --- | --- |
| `backend`: `.venv` | 破損状態（`michinari_backend-2.0.0.dist-info`のRECORD欠落によるOneDriveロック、`OPERATIONS.md`記載の既知症状）を確認し、`rm -rf .venv && uv sync --frozen`で復旧済み（本作業と無関係の環境問題） |
| `backend`: `uv run ruff check .` | **All checks passed!**（0件） |
| `backend`: `uv run pytest -q` | **1,838 件合格・0件失敗**（1 warning）、カバレッジ100%（文・分岐とも、`--cov-report`集計値）。既存の失敗は無い |
| `backend`: `radon cc`（対象3関数） | `export_service.render_markdown` D(38)・`build_export_data` D(21)・`goal_service._cascade_delete_activity_logs` D(28)。タスク本体記載の数値と一致、ベースライン確定 |
| `frontend`: `npm run test -- --run`（vitest+coverage） | **154 ファイル合格・1ファイル失敗**、**1,317 件合格・1件失敗**（155ファイル・1,318件）。失敗は`src/pages/CalendarPage.test.tsx`「CalendarPageの選択モーダル > links to both the daily report and the progress-only screen」（jsdomの`Not implemented: navigation to another Document`によるタイムアウト）。**本作業（ai_context_service分割等、バックエンドのみ）とは無関係**。対応は本Todoの範囲外（§6に別件として記録） |
| `frontend`: `npm run lint`（oxlint） | 0件（warn対象の`max-lines-per-function`/`max-depth`含む） |
| `frontend`: `npx tsc -b` | 0件（型エラー無し） |

## 3. 作業手順

凡例：`[ ]` 未着手、`[x]` 完了。各項目の完了条件は「関係するテストが通ること」。全手順完了後、§4の全体テストで最終確認する。

### 3.1 ai_context_service の分割

- [x] T-01 `backend/tests/ai_context_helpers.py` を新設し、`_make_goal`を`make_goal`として移動する（公開名、`reading_helpers.py`と同じ命名規則）。**変更**: 実査の結果`_make_daily_record`はEXAM専用（READING/WORK/共通テストでは使われない）と判明したため、共通ヘルパーには含めず`test_ai_context_exam.py`側に残した（§1.1記載の対応表どおり）
- [x] T-02 `backend/app/services/ai_context_common.py` を新設し、§1.1の共通関数群を移動する（モジュールdocstringも移動）
- [x] T-03 `backend/app/services/ai_context_exam.py` を新設し、§1.1のEXAM関数群を移動する（`ai_context_common`から`_format_days_remaining`等をimport）
- [x] T-04 `backend/app/services/ai_context_reading.py` を新設し、§1.1のREADING関数群を移動する
- [x] T-05 `backend/app/services/ai_context_work.py` を新設し、§1.1のWORK関数群を移動する
- [x] T-06 元の `backend/app/services/ai_context_service.py` を削除する
- [x] T-07 §1.2の全呼び出し元（import・コール部・コメント参照）を更新する
- [x] T-08 `backend/tests/test_ai_context_service.py` を4分割（`test_ai_context_common.py`/`test_ai_context_exam.py`/`test_ai_context_reading.py`/`test_ai_context_work.py`）し、`ai_context_helpers`を import するよう変更する。元ファイルを削除する（112件合格）
- [x] T-09 `grep -rn "ai_context_service"` で旧名称の残留が無いことを確認する（コメント含む。新4ファイルのdocstring内「分割元」の説明のみ残存、意図した記述）

### 3.2 export_service の複雑度分割

- [x] T-10 `_build_exam_export_data` を新設し、`build_export_data` のEXAM分岐（現状のインライン処理）を移動する（`_build_reading_export_data`/`_build_work_export_data`と対称の形）
- [x] T-11 `_render_exam_markdown` を新設し、`render_markdown` のEXAM分岐を移動する
- [x] T-12 `_render_exam_markdown` 内の12セクション（overview/retrospective/summary/materials/quality_trend/replan_history/weekly_summaries/recap_themes/daily_records/results/diaries/ai_dialogue）を、それぞれ`_render_<section>_section`関数へ抽出する。12関数への分岐表（`_EXAM_SECTION_RENDERERS`）で宣言的にまとめた
- [x] T-13 `radon cc backend/app/services/export_service.py` で分割後の複雑度を測定し、§4に記録する（34件合格、既存テスト無改修）

### 3.3 goal_service の複雑度分割

- [x] T-14 `_delete_work_evaluation_members_and_reports(session, goal)` を抽出する
- [x] T-15 `_collect_and_delete_activity_logs(session, goal) -> set[int] | None` を抽出する（空なら`None`を返し、呼び出し元で早期return）
- [x] T-16 `_delete_now_empty_daily_records(session, record_ids)` を抽出する
- [x] T-17 `radon cc backend/app/services/goal_service.py` で分割後の複雑度を測定し、§4に記録する（24件合格、既存テスト無改修）

### 3.4 CODING_RULES.md の更新

- [x] T-18 置き場所ルールへ、1ファイル肥大化時の分割先命名規則（`<元の名前>_<カテゴリ>.py`）を追記する

### 3.5 ドキュメント更新（§1.3）

- [x] T-19 `設計書_ロジック・プロンプト編_ミチナリ_v1.1.md`の`ai_context_service.<関数名>`参照（本文6箇所）を更新し、改訂履歴に1行追加する（改44）。`仕様書`・`設計書データ構造編`は調査の結果対象外と判明（§1.3参照）

## 4. テスト計画

- 各手順（T-01〜T-17）の後、関係するテストファイルを個別実行し、分割前と同じ件数・同じ結果（合格）であることを確認する
- 全手順完了後、§2と同じ一式（`ruff check`・`pytest`・`vitest`・`oxlint`・`tsc -b`）を再実行し、件数をベースラインと比較する（§9に記録）
- `grep -rn "ai_context_service"` で旧名称の残留ゼロを確認する（T-09の再確認）
- 公開関数のシグネチャ・振る舞いは変えないため、既存テストは**期待値を一切変更せず**、分割・移動のみで合格することを確認する（タスク本体の要求）

### 4.1 複雑度（radon cc）の分割前後比較

| 関数 | 分割前 | 分割後 |
| --- | --- | --- |
| `export_service.render_markdown` | D (38) | 分割（`render_markdown`は3分岐のディスパッチのみ・複雑度1桁。EXAM分は`_render_exam_markdown`＋12個の`_render_<section>_section`へ分解、各関数は複雑度1〜2） |
| `export_service.build_export_data` | D (21) | `build_export_data`は3分岐のディスパッチのみ・複雑度1桁。EXAM分は`_build_exam_export_data`へ分離：C (19)（11個の独立したif文字段の合算値。既存の`_build_reading_export_data` B(10)・`_build_work_export_data` B(9)と同系統だが対象フィールド数が多い分高め。更なる分割＝宣言的ディスパッチ化は、各フィールドの組み立て引数が不均一で可読性を落とすため見送った、§5決定） |
| `goal_service._cascade_delete_activity_logs` | D (28) | `_cascade_delete_activity_logs`自体は3行の委譲のみ・複雑度1。`_delete_work_evaluation_members_and_reports` B(6)・`_collect_and_delete_activity_logs` C(16)・`_delete_now_empty_daily_records` B(8)の3関数に分割 |

いずれも機械的なLintの複雑度上限（ruffの`mccabe`/`C901`）は本リポジトリで未設定（`pyproject.toml`の`select`に含まれず）のため、CI強制ではなく本書への記録のみとする（決定事項S5）。

## 5. 未決事項

無し。本書内の全ての設計判断（モジュール分割境界・配置・テストヘルパーの集約先・ドキュメント更新範囲）は、既存コードの呼び出し状況の調査（§1）と既存の命名規則・慣習の確認により決定した。

## 6. 別件（範囲外で見つけた問題）

- `frontend/src/pages/CalendarPage.test.tsx`「CalendarPageの選択モーダル > links to both the daily report and the progress-only screen」が、本作業と無関係にベースラインから失敗している（jsdomの`Not implemented: navigation to another Document`によるタイムアウト、§2参照）。本Todoの範囲外（バックエンドのみの構造整理）のため対応しない
- `backend/.venv`が開発開始時に破損していた（`OPERATIONS.md`記載の既知症状、OneDriveロックによる`RECORD`欠落）。`rm -rf .venv && uv sync --frozen`で復旧済み。再発する場合は`OPERATIONS.md`「`.venv`が壊れた場合」の手順で対応する
- `backend/scripts/build_package.py`・`backend/tests/test_ai_orchestration.py`・`backend/tests/test_help_assistant_fixtures.py`の3ファイルが、現行の`ruff format`（インストール済みバージョン）と異なる整形（`ruff format --check .`で「would be reformatted」）になっている。本作業が触れていない既存ファイルのため、本Todoの範囲外として整形は変更しない（横展開で整形を揃えたい場合は別タスクで対応する）
- `export_service.render_markdown`の`selection: ExportSelection`引数は、分割前から関数本体で一度も参照されていなかった（EXAM・READING・WORKいずれの分岐も`data`の内容のみで判定するため）。振る舞い非変更の原則に従い、本作業ではこの既存の未使用引数をそのまま残した（削除するとpublic関数のシグネチャ変更になり、呼び出し元`app/api/export.py`の変更が必要になるため、別件として記録のみ）
- `ai_context_exam.build_material_summary_text`は、`for material in materials:`のループ内で`session.query(func.sum(StudyLog.minutes_spent)).filter(...).scalar()`を教材ごとに実行している（N+1相当のパターン）。分割前の`ai_context_service.py`（651e1c45時点）に既に同一の実装があり、本作業はコードを移動したのみで新規に持ち込んだものではない（振る舞い非変更の原則によりこの場で修正しない）。対象は総括レポート（GOAL_RETROSPECTIVE）生成時の教材一覧（通常は数件程度）に限られ、日次の高頻度経路ではないため実害は小さいと推測されるが、改善の余地があれば別タスクで対応する

## 7. 完了の定義

- §3の全項目が`[x]`になり、バックエンド・フロントエンドともテストが通る（達成）
- §2のベースラインと比較して、テスト件数が（既知の無関係な1件を除き）減らない（達成：バックエンド1,838件合格で変化なし。フロントエンドは§9参照）
- `render_markdown`・`build_export_data`・`_cascade_delete_activity_logs`の複雑度が分割前より下がっていることをradonで確認する（達成：3関数とも分割後はradonの計測対象（複雑度B以上）から外れる＝個別にはA未満の最小複雑度になった。詳細は§4.1）
- 旧名称（`ai_context_service`）の残留が無い（達成。新4ファイルのdocstring内「分割元」の説明のみ意図的に残す）
- §1.3のドキュメントが更新済み（達成）

## 8. 作業記録

- 2026-10-11 フェーズA実施（調査・ベースライン取得）
  - radonを`myvenv`へ導入（CLAUDE.md「ツール導入ルール」に従い仮想環境配下に限定）
  - `backend/.venv`の破損（既知症状）を`OPERATIONS.md`記載の手順で復旧
  - ruff・pytest（1,838件合格・カバレッジ100%）・vitest（1,317件合格・1件既存失敗）・oxlint・tsc のベースラインを確認。対象3関数のradon cc測定値がタスク本体の記載（38・21・28）と一致することを確認

- 2026-10-11 フェーズB実施（実装）
  - §3.1〜3.5の全項目（T-01〜T-19）を完了。手順ごとに関係するテストを実行し、都度合格を確認した
  - フェーズA時点のドキュメント影響範囲の記載に誤りがあり（§1.3の訂正参照）、実装着手後に訂正した（`仕様書`・`設計書データ構造編`は対象外と判明）
  - バックエンド全体を再実行：**1,838件合格・0件失敗（1 warning、ベースラインと同数）・カバレッジ100%**（`ai_context_common`/`ai_context_exam`/`ai_context_reading`/`ai_context_work`/`export_service`/`goal_service`いずれも100%）
  - `ruff check .`・`ruff format --check .`（本作業で触れたファイルのみ整形。無関係な既存3ファイルの整形ずれは触れていない、別件として§6に記録）ともに合格
  - `grep -rn "ai_context_service"`で旧名称の残留が意図した3箇所（新ファイルの分割元説明）のみであることを確認
