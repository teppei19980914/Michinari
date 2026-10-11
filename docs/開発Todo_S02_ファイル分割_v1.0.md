# 開発Todo：S02 構造の整理②（行数の多いバックエンドのファイル・テストの分割）

本書は、ベースライン文書「S02：構造の整理②」（版2.1）に基づく開発作業の正（Single Source of Truth）である。
振る舞いは変えない（挙動保存のリファクタリング）。作業は `dev/2026-10-11` で行う。前提の S01（`開発Todo_S01_構造整理_v1.0.md`）は
2026-10-11に完了・main へマージ済みであることを確認した（§1.0参照）。

## 0. 決定事項

| # | 決定 |
| --- | --- |
| S1 | `record_service.py`（966行）を4ファイルへ分割する：`record_service_common.py`（共通）・`record_service_exam.py`（資格試験）・`record_service_reading.py`（読書）・`record_service_work.py`（仕事）。接頭語は元のファイル名をそのまま使う（利用者確認済み。`record`単独だと`app/models/record.py`と混同するため） |
| S2 | `export_service.py`（1034行）を同様に4ファイルへ分割する：`export_service_common.py`・`export_service_exam.py`・`export_service_reading.py`・`export_service_work.py` |
| S3 | `prompt_texts.py`（918行）を同様に4ファイルへ分割する：`prompt_texts_common.py`・`prompt_texts_exam.py`・`prompt_texts_reading.py`・`prompt_texts_work.py`。カテゴリ判定は`AiPurpose`列挙（`app/constants/enums.py`87行目）の命名規則（無印=EXAM、`_READING`接尾=READING、`_WORK`接尾=WORK、接尾無しでカテゴリに依存しないもの=common）に従う |
| S4 | `goal_service.py`（713行）は資格試験・読書・仕事の3カテゴリの分岐がほとんどの関数内（`activate_goal`・`resume_goal`・`complete_goal`等）に混在しており、他の3ファイルと同じ「カテゴリ別ファイル」に馴染まない（利用者確認済み）。**処理の段階別**に分割する：`goal_service.py`（共通ガード・CRUD・カスケード削除、そのまま残す）・`goal_service_lifecycle.py`（状態遷移: `activate_goal`/`pause_goal`/`resume_goal`/`abandon_goal`/`complete_goal`/`compute_is_achieved`等）・`goal_service_load_profile.py`（負荷プロファイルCRUD） |
| S5 | S4の新しい命名規則（`<元の名前>_<処理の段階>.py`）をCODING_RULES.mdの置き場所ルールへ、既存のカテゴリ別規則と併記する形で追記する |
| S6 | `test_migration.py`（1277行、Alembicマイグレーション1本につき概ね1テスト）は対応する本体ファイルの分割が無いため、テスト名から読み取れる3系統（スキーマ変更系／`prompt_template`移行系／データ移行・バックフィル系）のテーマ別に分割する（利用者確認済み） |
| S7 | `test_build_package.py`（1238行）は対応する`backend/scripts/build_package.py`自体は本Todoの分割対象外だが、テストの責務は同ファイルの関数群に沿って明確に分かれているため、その単位で分割する（利用者確認済み）：`test_build_package_version.py`（バージョン入力・`uv.lock`同期）・`test_build_package_archive.py`（退避・破棄・再試行）・`test_build_package_package.py`（zip化・同梱・ランチャー）・`test_build_package_misc.py`（スモーク・PyInstaller引数・ビルドコミット記録・ライセンス） |
| S8 | `_serialize_record`（`api/records.py`、複雑度19）は、`record is None`の分岐を関数先頭で早期確定し、以降の各フィールド構築から`if record else ...`の三項演算子を除去する（振る舞い不変・複雑度のみ低下）。ファイル分割（S1）とは独立した作業（`api/records.py`は421行で分割対象外） |
| S9 | `record_service.register_progress`（複雑度17）は、S1のカテゴリ分割後、「対象カテゴリへの適用＋未確定なら状態をPROGRESS_ONLYにする」ブロックを各カテゴリモジュールの`apply_progress(session, record, items)`（exam/reading/work、空リストなら早期return。アンダースコア無し＝S01の`_format_days_remaining`と同じく、モジュール境界を越えて呼ばれる関数として命名）へ抽出する。`register_progress`本体（`record_service_common.py`に残る）は、元の順序（3カテゴリ分の`_ensure_category_not_reported`確認→`_create_record`→3カテゴリ分の`apply_progress`呼び出し）をそのまま保ち、3件の確認を全て終えてから初めて記録を作成・適用する元の振る舞い（1カテゴリでも確定済みなら他カテゴリの適用も行わずに例外とする）を変えない。**実装上の注意**: `record_service_exam.py`等は`finalize_*`関数が`record_service_common`の`_set_category_state`等をモジュール先頭でimportするため、`record_service_common.py`側で`record_service_exam`等を先頭（モジュール読込時）でimportすると循環importになる。`register_progress`関数の**本体内**（呼び出し時に遅延評価）で`from app.services import record_service_exam, record_service_reading, record_service_work`する（Pythonの循環import回避の標準手法。両モジュールが先に完全に読み込み済みになった後で実際の呼び出しが発生するため安全）。同じ理由で、`register_progress`の引数型ヒント（`StudyLogItem`/`ReadingLogItem`/`WorkLogItem`）は`app/models/goal.py`等の既存の型チェック専用import（`if TYPE_CHECKING:`）と同じ手法で、文字列の前方参照として書く |
| S10 | `prompt_template`の初期投入内容（`seed_data.py`の`_PROMPT_TEXT_BY_PURPOSE`相当の辞書）が分割前後で一字一句変わらないことをテストで示す（既存の`test_bootstrap.py`等に1件追加、または既存テストの対象拡大で対応する。詳細はPhase B着手時に既存テストの構成を確認して決定） |
| S11 | `backend/alembic/versions/`の6ファイルに残る「`app/init/prompt_texts.py`の内容を転記した」というコメントは、**マイグレーション作成時点の事実の記録**（S01決定事項S7と同じ「過去の記録は書き換えない」原則）として変更しない。`app/constants/help_assistant.py`のコメント（`prompt_texts.HELP_ASSISTANT`参照）は現在の構造を指す現役の記述のため、`prompt_texts_common.HELP_ASSISTANT`へ更新する |
| S12 | ドキュメント更新範囲：`CODING_RULES.md`（S5、必須）。`docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1.md`の`prompt_texts.HELP_ASSISTANT`参照（2箇所、2526・2538行目）を`prompt_texts_common.HELP_ASSISTANT`へ更新し、改訂履歴に1行追加する。`docs/設計書_データ構造編_ミチナリ_v1.1.md`の8章ディレクトリ構成図（`goal_service.py`・`record_service.py`・`export_service.py`の記載、1633・1650・1655行目付近）は、**既に現行の38ファイル中20ファイル程度しか列挙していない長年の陳腐化状態**（S01でも同種の箇所を対象外と判断）であり、本リファクタリング単独での全面更新は別タスクとする。本Todoでは触れない（§6別件に記録） |
| 版 | バージョン番号（`backend/pyproject.toml`）は変更しない |

未決事項は無し（利用者への3件の確認が完了。§5参照）。

## 1. 影響範囲（フルスキャンの結果）

### 1.0 前提（S01の完了確認）

- `docs/開発Todo_S01_構造整理_v1.0.md`は全19手順（T-01〜T-19）が完了済み（`[x]`）
- `backend/app/services/ai_context_service.py`は存在せず、`ai_context_common.py`/`ai_context_exam.py`/`ai_context_reading.py`/`ai_context_work.py`の4ファイルが存在することを確認した
- 現在のブランチ`dev/2026-10-11`は`main`と差分無し（`git log main..HEAD`が空）、作業ツリーはclean。S01の成果は`main`マージ済み（コミット`bdd41ae`、PR #104）

### 1.1 record_service.py の分割先対応表（966行）

| 新モジュール | 定数・関数 |
| --- | --- |
| `record_service_common.py` | `get_daily_record`・`ensure_daily_record`・`next_chat_sequence`・`SlotMinutes`・`_validate_slot_minutes`・`_total_minutes`・`_replace_slot_times`（study_log・reading_logの2カテゴリから参照されるため共通）・`_create_record`・`_CATEGORY_STATE_ATTR`・`_CATEGORY_REPORTED_AT_ATTR`・`category_state_column`・`_get_category_state`・`_set_category_state`・`aggregate_record_state`・`resolve_record_state`・`count_reported_records_before`・`has_any_reported_record`・`_ensure_category_not_reported`・`_ensure_finalizable_date`・`register_progress`（S9でディスパッチャ化）・`get_comment`・`add_comment`・`update_comment`・`delete_comment`・`PreviousEntry`・`_get_previous_entry`・`CalendarDayView`・`get_calendar_days` |
| `record_service_exam.py` | `_SUBJECTIVE_QUALITY_MAP`・`_normalize_quality`・`load_materials_by_id`・`_load_materials`・`_load_goals`・`StudyLogItem`・`_upsert_study_log`・`_apply_study_logs`・`DiaryEntryItem`・`DiaryEntry`・`_upsert_diary_entry`・`_apply_diary_entries`・`get_diary_entries`・`finalize_record`・`SlotDefaultMinutes`・`QuotaItem`・`compute_daily_quota`・`_compute_slot_defaults`・`get_previous_diary_entry`・`_register_exam_progress`（新設、S9）。**訂正（フェーズB着手時に発覚）**: `_normalize_quality`/`_SUBJECTIVE_QUALITY_MAP`（品質指標の正規化）は`_upsert_study_log`からのみ呼ばれ、`_load_materials`（material一括取得）は`load_materials_by_id`・`_apply_study_logs`からのみ呼ばれ、`_load_goals`（goal一括取得）は`_apply_diary_entries`からのみ呼ばれる、いずれもEXAM専用のためcommonからexamへ訂正した |
| `record_service_reading.py` | `load_books_by_id`・`ReadingLogItem`・`_load_books`・`_ensure_current_page_within_total_pages`・`_upsert_reading_log`・`_apply_reading_logs`・`finalize_reading_record`・`get_previous_reading_log`・`_register_reading_progress`（新設、S9） |
| `record_service_work.py` | `load_work_assignments_by_id`・`WorkLogItem`・`_load_work_assignments`・`_upsert_work_log`・`_apply_work_logs`・`finalize_work_record`・`get_previous_work_log`・`_register_work_progress`（新設、S9） |

**呼び出し元（フルスキャン、実際にimportしている17ファイル。コメントのみの参照は対象外）**：

| ファイル | 現状の参照 | 更新後のimport |
| --- | --- | --- |
| `app/api/calendar.py` | `get_calendar_days`/`get_daily_record`/`resolve_record_state` | `record_service_common` |
| `app/api/records.py` | common多数＋`DiaryEntryItem`/`StudyLogItem`(exam)＋`ReadingLogItem`(reading)＋`WorkLogItem`(work)＋`compute_daily_quota`/`finalize_record`/`get_previous_diary_entry`(exam)＋`finalize_reading_record`/`get_previous_reading_log`(reading)＋`finalize_work_record`/`get_previous_work_log`(work) | 4モジュール全て |
| `app/services/ai_context_exam.py` | `DiaryEntryItem`/`StudyLogItem` | `record_service_exam` |
| `app/services/ai_context_reading.py` | `ReadingLogItem` | `record_service_reading` |
| `app/services/ai_context_work.py` | `WorkLogItem` | `record_service_work` |
| `app/services/daily_feedback_service.py` | `DiaryEntryItem`/`StudyLogItem`(exam)＋`count_reported_records_before`/`ensure_daily_record`/`next_chat_sequence`(common)＋`load_materials_by_id`(exam) | `record_service_common` + `record_service_exam` |
| `app/services/metrics_service.py` | `category_state_column` | `record_service_common` |
| `app/services/notification_service.py` | `get_daily_record`/`resolve_record_state` | `record_service_common` |
| `app/services/reading_feedback_service.py` | `ReadingLogItem`(reading)＋common3関数＋`load_books_by_id`(reading) | `record_service_common` + `record_service_reading` |
| `app/services/work_feedback_service.py` | `WorkLogItem`(work)＋common3関数＋`load_work_assignments_by_id`(work) | `record_service_common` + `record_service_work` |
| `backend/tests/diary_helpers.py` | `DiaryEntryItem`/`finalize_record`（いずれもexam） | `record_service_exam` |
| `backend/tests/reading_helpers.py` | `ReadingLogItem` | `record_service_reading` |
| `backend/tests/test_ai_context_exam.py` | `DiaryEntryItem`/`StudyLogItem` | `record_service_exam` |
| `backend/tests/test_ai_context_reading.py` | `ReadingLogItem` | `record_service_reading` |
| `backend/tests/test_ai_context_work.py` | `WorkLogItem` | `record_service_work` |
| `backend/tests/test_daily_feedback_service.py` | `DiaryEntryItem`/`StudyLogItem`/`get_diary_entries`(exam)＋`ensure_daily_record`/`get_daily_record`(common) | `record_service_common` + `record_service_exam` |
| `backend/tests/test_goal_state_transitions.py` | `add_comment`/`register_progress`(common)＋`finalize_record`(exam) | `record_service_common` + `record_service_exam` |
| `backend/tests/test_notification_service.py` | `ensure_daily_record` | `record_service_common` |
| `backend/tests/test_reading_feedback_service.py` | `DiaryEntryItem`/`StudyLogItem`(exam、要Phase B時点で実使用の有無を再確認)＋`get_daily_record`(common) | `record_service_common`（＋必要なら`record_service_exam`） |
| `backend/tests/test_recap_generation_service.py` | `finalize_reading_record` | `record_service_reading` |
| `backend/tests/test_recap_service.py` | `finalize_reading_record` | `record_service_reading` |
| `backend/tests/test_work_feedback_service.py` | `StudyLogItem`(exam、要再確認)/`WorkLogItem`(work)＋`get_daily_record`(common) | `record_service_common` + `record_service_work`（＋必要なら`record_service_exam`） |
| `backend/tests/test_record_service.py` | 本体（§1.5参照、4分割） | 4分割 |

`backend/alembic/`・`backend/scripts/`・`frontend/src/`配下に`record_service`モジュールへの実importは無い（フルスキャン確認済み。`frontend/src`の`register_progress`等の一致はTypeScript側の同名識別子であり、Python側へのimportではない）。

**訂正（フェーズB実施中に発覚）**: `app/api/dashboard.py`が初回スキャンの正規表現（複数行の`from app.services import (...)`内で`record_service,`が単独行のため不一致）で漏れていた。`compute_daily_quota`(exam)・`get_daily_record`/`resolve_record_state`/`has_any_reported_record`(common)を使用しており、`record_service_common`+`record_service_exam`へ更新した。この反省から、以降の確認は`grep -rln "\brecord_service\b"`（単語境界、複数行import内の単独行も確実に捕捉）で再実施し、他の漏れが無いことを確認した（`backend/app/models/record.py`・`backend/app/schemas/record.py`のコメント4箇所も実装と不整合にならないよう更新、`backend/alembic/versions/7c2e5a1d9f4b_...py`はマイグレーション作成時点の設計根拠説明のため変更しない、S11と同じ原則）。

### 1.2 export_service.py の分割先対応表（1034行）

| 新モジュール | 定数・関数 |
| --- | --- |
| `export_service_common.py` | `_UNSAFE_FILENAME_CHARS`・`SCHEMA_VERSION`・`ExportSelection`・`ExportContent`・`build_export_data`（ディスパッチャ）・`render_markdown`（ディスパッチャ）・`_safe_filename_fragment`・`write_export_files`・`execute_export` |
| `export_service_exam.py` | `_RESULT_LABELS`・`_REASON_LABELS`・`_build_goal_and_subjects`・`_format_passing_score`・`_build_materials`・`_build_summary`・`_build_daily_records`・`_build_slot_minutes_by_study_log`・`_build_quality_trend`・`_build_replan_history`・`_build_weekly_summaries`・`_build_results`・`_build_diaries`・`_build_ai_dialogue`・`build_exam_export_data`・`render_exam_markdown`＋12個の`_render_<section>_section`・`_EXAM_SECTION_RENDERERS` |
| `export_service_reading.py` | `_build_book`・`_reading_log_dates`・`_compute_max_streak_days`・`_build_reading_summary`・`_build_reading_daily_records`・`build_reading_export_data`・`render_reading_markdown` |
| `export_service_work.py` | `_build_work_assignment`・`_work_log_dates`・`_build_work_summary`・`_build_work_daily_records`・`build_work_retrospectives`・`build_work_export_data`・`render_work_markdown` |

**訂正（フェーズB着手時に発覚）**: `_build_exam_export_data`・`_render_exam_markdown`・`_build_reading_export_data`・`_render_reading_markdown`・`_build_work_export_data`・`_render_work_markdown`・`_build_work_retrospectives`の7関数は、分割前は`export_service.py`内の`build_export_data`/`render_markdown`（ディスパッチャ）・`execute_export`からのみ呼ばれる同一ファイル内のプライベート実装だったためアンダースコア付きだったが、分割後は`export_service_common.py`の3関数から**モジュールを越えて**呼ばれる、各カテゴリモジュールの実質的な公開エントリポイントになる。S01の`_format_days_remaining`（2カテゴリ参照でもアンダースコアを残した）とは異なり、この7関数は「他モジュールの処理を一括して委譲される唯一の窓口」という性質がai_context_exam等の`build_goal_summary`等（アンダースコア無し）に近いため、アンダースコアを外した（`_build_work_retrospectives`のみ、呼び出し元が増えた今回の変更）。

`_compute_max_streak_days`はreading由来だがwork側（`_build_work_summary`）からも呼ばれる（DRYの原則、既存コメントに明記）ため、`export_service_reading.py`に置き`export_service_work.py`からimportする（既存の呼び出し関係をそのまま維持）。

**呼び出し元（フルスキャン、実import4ファイルのみ。`system_info.py`・`backup_service.py`・`metrics_service.py`は`system_log_export_service`への参照またはコメントのみと判明したため対象外）**：

| ファイル | 現状の参照 | 更新後のimport |
| --- | --- | --- |
| `app/api/export.py` | `build_export_data`/`execute_export`/`ExportSelection`/`render_markdown` | `export_service_common` |
| `app/services/export_progress.py` | `execute_export` | `export_service_common` |
| `backend/tests/test_api_export.py` | `SCHEMA_VERSION` | `export_service_common` |
| `backend/tests/test_recap_service.py` | `build_export_data`/`ExportSelection`/`render_markdown` | `export_service_common` |
| `backend/tests/test_export_service.py` | 本体（§1.5参照、4分割） | 4分割 |

**誤検出の記録（調査時に判明）**：`app/api/system_info.py`・`backend/tests/test_api_system_info.py`の`export_service`一致は実際には`system_log_export_service.export_logs`の部分文字列一致（別モジュール）。`app/services/backup_service.py`・`app/services/metrics_service.py`の一致はコメント内の言及のみで実importではない。いずれも更新不要。

### 1.3 prompt_texts.py の分割先対応表（918行）

| 新モジュール | 定数（`AiPurpose`列挙との対応） |
| --- | --- |
| `prompt_texts_common.py` | `DAILY_MESSAGE`・`RECAP_CLASSIFY`・`RECAP_THEME_BODY`・`HELP_ASSISTANT` |
| `prompt_texts_exam.py` | `DAILY_FEEDBACK`・`WEEKLY_SUMMARY`・`GOAL_RETROSPECTIVE` |
| `prompt_texts_reading.py` | `DAILY_FEEDBACK_READING`・`GOAL_RETROSPECTIVE_READING`・`WEEKLY_SUMMARY_READING` |
| `prompt_texts_work.py` | `DAILY_FEEDBACK_WORK`・`GOAL_RETROSPECTIVE_WORK_MONTHLY`・`GOAL_RETROSPECTIVE_WORK_SEMIANNUAL`・`WEEKLY_SUMMARY_WORK`・`EVALUATION_REPORT_WORK` |

**呼び出し元**：

| ファイル | 現状の参照 | 更新後のimport |
| --- | --- | --- |
| `app/init/seed_data.py` | `AiPurpose`→定数の対応辞書で全15定数を参照 | 4モジュール全て |
| `app/constants/help_assistant.py` | コメントのみ（`prompt_texts.HELP_ASSISTANT`） | コメント文言を`prompt_texts_common.HELP_ASSISTANT`へ更新（import無し） |
| `backend/alembic/versions/`の6ファイル | コメントのみ（マイグレーション作成時点の転記元の記録） | 変更しない（決定事項S11） |

`frontend/src/`配下に参照は無い。

### 1.4 goal_service.py の分割先対応表（713行、処理の段階別）

| 新モジュール/残留 | 関数・クラス |
| --- | --- |
| `goal_service.py`（残留） | `_CLOSED_STATUSES`・`resolve_today`・`resolve_treat_holiday_as_buffer`・`record_baseline_for_material`・`ensure_goal_editable`・`ensure_goal_active`・`ensure_operation_allowed`・`available_operations`・`ensure_any_goal_active`・`_append_status_history`・`get_goal`・`list_goals`・`create_goal`・`update_goal`・`delete_goal`・`archive_goal`・`unarchive_goal`・`_delete_work_evaluation_members_and_reports`・`_collect_and_delete_activity_logs`・`_delete_now_empty_daily_records`・`_cascade_delete_activity_logs`・`get_baselines` |
| `goal_service_lifecycle.py`（新設） | `_change_status`・`_validate_allocation_capacity`・`activate_goal`・`pause_goal`・`ResumeResult`・`resume_goal`・`_replan_on_resume`・`abandon_goal`・`complete_goal`・`compute_is_achieved`（`goal_service`の`resolve_today`/`resolve_treat_holiday_as_buffer`/`record_baseline_for_material`/`ensure_operation_allowed`/`_append_status_history`/`_CLOSED_STATUSES`をimportして使う）。**訂正（フェーズB着手時に発覚）**: `_append_status_history`は`_change_status`からだけでなく`create_goal`（CRUD、236行目）からも直接呼ばれるため、`goal_service.py`側に残す |
| `goal_service_load_profile.py`（新設） | `get_load_profile`・`list_load_profiles`・`_validate_load_profile_period`・`create_load_profile`・`update_load_profile`・`delete_load_profile`（`goal_service.ensure_goal_editable`をimportして使う） |

**呼び出し元のうち、移動する関数（lifecycle・load_profile）を参照している箇所（フルスキャンの結果、実質2ファイルのみ）**：

| ファイル | 現状の参照 | 更新後のimport |
| --- | --- | --- |
| `app/api/goals.py` | CRUD（残留）＋lifecycle6関数＋load_profile5関数 | `goal_service`（残留分）＋`goal_service_lifecycle`＋`goal_service_load_profile` |
| `backend/tests/test_goal_service.py` | lifecycle関数を含む（本ファイルは分割対象外、importのみ更新） | 同上 |
| `backend/tests/test_goal_state_transitions.py` | lifecycle関数を含む（分割対象外） | 同上 |
| `backend/tests/test_phase3_service_guards.py` | lifecycle・load_profile関数を含む（分割対象外） | 同上 |

残留するCRUD関数（`get_goal`/`list_goals`/`create_goal`等）のみを使う他18ファイル（`app/api/ai.py`・`analytics.py`・`books.py`・`closure.py`・`dashboard.py`・`export.py`・`recap.py`・`records.py`・`work.py`、`app/main.py`、`app/services/ai_context_common.py`・`ai_context_exam.py`・`baseline_service.py`・`book_service.py`・`daily_feedback_service.py`・`daily_message_service.py`・`export_service.py`（分割後は`export_service_exam.py`等）・`material_service.py`・`notification_service.py`・`reading_feedback_service.py`・`record_service.py`（分割後は各モジュール）・`retrospective_service.py`・`subject_service.py`・`weekly_summary_service.py`・`work_feedback_service.py`・`work_member_service.py`・`work_service.py`、`backend/scripts/build_package.py`、及び`backend/tests/`の`test_book_service.py`・`test_bootstrap.py`・`test_desktop_scheduler.py`・`test_notification_service.py`・`test_record_service.py`・`test_work_service.py`）は、`goal_service.py`のファイル名・import先が変わらないため**変更不要**（Phase B着手時にdelete_goal等のカスケード削除関数を使っていないことを個別に再確認する）。

`app/schemas/goal.py`の`goal_service.compute_is_achieved`参照はコメントのみ（更新不要）。

### 1.5 テスト分割（§3.5・3.6・3.7関連、1,000行超の5ファイル）

| 元ファイル | 分割先 | 根拠 |
| --- | --- | --- |
| `test_record_service.py`（1351行） | `test_record_service_common.py`/`_exam.py`/`_reading.py`/`_work.py` | §1.1の本体分割に対応。既存の section banner（`register_progress`/`finalize_record`/`読書記録`/`業務記録`/`品質指標`/`コメント`/`日次ノルマ`/`前回の記録`/`カレンダー`/`aggregate_record_state`）が分割先と1対1で対応することを確認済み |
| `test_export_service.py`（1271行） | `test_export_service_common.py`/`_exam.py`/`_reading.py`/`_work.py` | §1.2の本体分割に対応。section banner（`build_export_data`→exam大半・読書個別・仕事個別、`render_markdown`→同様、`execute_export`→common）で確認済み |
| `test_api_records.py`（1002行） | `test_api_records_common.py`/`_exam.py`/`_reading.py`/`_work.py` | `api/records.py`自体は分割しないが、テストのsection banner（`今日`/`進捗`/`確定`/`読書記録`/`ノルマ`/`コメント`/`chat`/`reading-chat`/`work-chat`/`前回の記録`等）が§1.1の record_service 分割と同じ3カテゴリ＋共通の構造を持つため、同じ方針で分割する |
| `test_migration.py`（1277行） | `test_migration_schema.py`（スキーマ変更系）/`test_migration_prompt.py`（prompt_template移行系）/`test_migration_data.py`（データ移行・バックフィル系） | 決定事項S6。グルーピングの具体案はPhase B着手時に全テスト名を再確認して確定する（§3.6） |
| `test_build_package.py`（1238行） | `test_build_package_version.py`/`_archive.py`/`_package.py`/`_misc.py` | 決定事項S7 |

テスト分割後の共通フィクスチャ（`conftest.py`の`db_session`等）は既存のまま変更しない。複数分割先で使うヘルパー関数が見つかった場合はS01のT-01と同じ方針（専用`*_helpers.py`へ集約）で対応する（Phase Bで実査）。

## 2. ベースライン（2026-10-11、開発前）

| 項目 | 結果 |
| --- | --- |
| `backend`: `uv run ruff check .` | **All checks passed!**（0件） |
| `backend`: `uv run pytest -q --cov` | **1,838件合格・0件失敗**（1 warning）、カバレッジ**100%**（文・分岐とも） |
| `backend`: `radon cc`（対象2関数＋関連） | `api/records._serialize_record` C(19)・`record_service.register_progress` C(17)。タスク本体記載の数値と一致 |
| `frontend`: `npm run test -- --run`（vitest+coverage） | **155ファイル合格・1318件合格**、**0件失敗**（S01ベースライン時点の既知失敗`CalendarPage.test.tsx`は本セッションでは再現せず、再実行で解消。詳細§6） |
| `frontend`: `npm run lint`（oxlint） | 0件 |
| `frontend`: `npx tsc -b` | 0件（exit code 0） |

対象ファイルの行数・複雑度の実測値（分割前）：

| ファイル | 行数 |
| --- | --- |
| `backend/app/services/record_service.py` | 966 |
| `backend/app/services/export_service.py` | 1034 |
| `backend/app/init/prompt_texts.py` | 918 |
| `backend/app/services/goal_service.py` | 713 |
| `backend/app/api/records.py`（参考、分割対象外） | 421 |
| `backend/tests/test_record_service.py` | 1351 |
| `backend/tests/test_migration.py` | 1277 |
| `backend/tests/test_export_service.py` | 1271 |
| `backend/tests/test_build_package.py` | 1238 |
| `backend/tests/test_api_records.py` | 1002 |

radon cc（複雑度B以上のみ抽出）：

```
backend/app/api/records.py
    F 140:0 _serialize_record - C (19)
backend/app/services/record_service.py
    F 591:0 register_progress - C (17)
    F 103:0 _normalize_quality - B (7)
    F 814:0 _compute_slot_defaults - B (7)
    F 488:0 aggregate_record_state - B (6)
backend/app/services/export_service.py
    F 600:0 _build_exam_export_data - C (19)
    F 487:0 _build_reading_export_data - B (10)
    F 733:0 _render_work_markdown - B (10)
    F 578:0 _build_work_export_data - B (9)
    F 690:0 _render_reading_markdown - B (9)
    F 958:0 execute_export - B (8)
    F 238:0 _build_daily_records - B (6)
backend/app/services/goal_service.py
    F 325:0 _collect_and_delete_activity_logs - C (16)
    F 434:0 activate_goal - C (13)
    F 359:0 _delete_now_empty_daily_records - B (8)
    F 569:0 complete_goal - B (8)
    F 495:0 resume_goal - B (7)
    F 303:0 _delete_work_evaluation_members_and_reports - B (6)
    F 529:0 _replan_on_resume - B (6)
    F 596:0 compute_is_achieved - B (6)
```

`backend/app/init/prompt_texts.py`は定数のみのためradon計測対象（関数）が無い。

## 3. 作業手順

凡例：`[ ]` 未着手、`[x]` 完了。各項目の完了条件は「関係するテストが通ること」。全手順完了後、§4の全体テストで最終確認する。

### 3.1 record_service の分割

- [x] T-01 `backend/app/services/record_service_common.py`を新設し、§1.1の共通関数群を移動する（モジュールdocstringも移動）
- [x] T-02 `backend/app/services/record_service_exam.py`を新設し、§1.1のEXAM関数群を移動する
- [x] T-03 `backend/app/services/record_service_reading.py`を新設し、§1.1のREADING関数群を移動する
- [x] T-04 `backend/app/services/record_service_work.py`を新設し、§1.1のWORK関数群を移動する
- [x] T-05 `register_progress`をディスパッチャ化する（決定事項S9）：`_register_exam_progress`/`_register_reading_progress`/`_register_work_progress`をそれぞれexam/reading/workモジュールへ抽出する
- [x] T-06 元の`backend/app/services/record_service.py`を削除する
- [x] T-07 §1.1の全呼び出し元（17ファイル）のimportを更新する
- [x] T-08 `backend/tests/test_record_service.py`を4分割する（§1.5）。ヘルパーの重複が見つかれば集約する
- [x] T-09 `grep -rn "record_service"`で旧名称の残留が無いことを確認する（新モジュールのdocstring内「分割元」説明を除く）

### 3.2 export_service の分割

- [x] T-10 `backend/app/services/export_service_common.py`を新設し、§1.2の共通関数群を移動する
- [x] T-11 `backend/app/services/export_service_exam.py`を新設し、§1.2のEXAM関数群を移動する
- [x] T-12 `backend/app/services/export_service_reading.py`を新設し、§1.2のREADING関数群を移動する
- [x] T-13 `backend/app/services/export_service_work.py`を新設し、§1.2のWORK関数群を移動する（`_compute_max_streak_days`は`export_service_reading`からimportする）
- [x] T-14 元の`backend/app/services/export_service.py`を削除する
- [x] T-15 §1.2の全呼び出し元（4ファイル）のimportを更新する
- [ ] T-16 `backend/tests/test_export_service.py`を4分割する（§1.5）
- [x] T-17 `grep -rn "export_service"`で旧名称の残留が無いことを確認する

### 3.3 prompt_texts の分割

- [ ] T-18 `backend/app/init/prompt_texts_common.py`/`_exam.py`/`_reading.py`/`_work.py`を新設し、§1.3の定数群を移動する
- [ ] T-19 元の`backend/app/init/prompt_texts.py`を削除する
- [ ] T-20 `app/init/seed_data.py`のimportを更新する。`app/constants/help_assistant.py`のコメント文言を更新する（import無し）
- [ ] T-21 決定事項S10：`prompt_template`初期投入内容が分割前後で一字一句変わらないことを示すテストを追加・確認する
- [ ] T-22 `grep -rn "prompt_texts\."`で、alembicの6ファイル（意図的に残す、S11）以外に旧名称の残留が無いことを確認する

### 3.4 goal_service の分割

- [x] T-23 `backend/app/services/goal_service_lifecycle.py`を新設し、§1.4のlifecycle関数群を移動する
- [x] T-24 `backend/app/services/goal_service_load_profile.py`を新設し、§1.4のload_profile関数群を移動する
- [x] T-25 `backend/app/services/goal_service.py`から移動済み関数を削除し、残留関数のみにする（モジュールdocstringを実態に合わせて更新）
- [x] T-26 §1.4の呼び出し元（`app/api/goals.py`・`test_goal_service.py`・`test_goal_state_transitions.py`・`test_phase3_service_guards.py`）のimportを更新する。他18ファイルはimport不要であることを個別に再確認する
- [x] T-27 `grep -rn "goal_service\."`で、移動した関数の呼び出しが新モジュール経由に揃っていることを確認する

### 3.5 複雑度の分割（ファイル分割と独立）

- [ ] T-28 `api/records._serialize_record`を早期return方式へ書き換える（決定事項S8）。`radon cc`で分割前後を比較する
- [ ] T-29 `radon cc backend/app/services/record_service_common.py backend/app/services/record_service_exam.py backend/app/services/record_service_reading.py backend/app/services/record_service_work.py`で`register_progress`系の分割後の複雑度を測定する（T-05と合わせて実施済みのはず。ここで記録のみ行う）

### 3.6 test_migration の分割

- [ ] T-30 既存の全テスト名（56〜1277行目）を再確認し、§1.5のS6で示した3系統への割り当て表を確定する
- [ ] T-31 `test_migration_schema.py`/`test_migration_prompt.py`/`test_migration_data.py`へ分割する。`conftest.py`・`migration_helpers.py`等の共通フィクスチャは変更しない
- [ ] T-32 元の`backend/tests/test_migration.py`を削除する

### 3.7 test_build_package の分割

- [ ] T-33 `test_build_package_version.py`/`_archive.py`/`_package.py`/`_misc.py`へ分割する（決定事項S7）。`_FakeCompletedProcess`等の共通ヘルパーは重複を避けて集約先を決める
- [ ] T-34 元の`backend/tests/test_build_package.py`を削除する
- [ ] T-35 配布パッケージの同梱確認（PyInstallerが新モジュール群を取り込めるか）を実機相当のテストで確認する。既存の`pyinstaller_args`・隠しimport設定にファイル分割の影響が無いことを確認する

### 3.8 CODING_RULES.md の更新

- [ ] T-36 置き場所ルールへ、決定事項S5の処理段階別命名規則（`<元の名前>_<処理の段階>.py`）を、既存のカテゴリ別規則と対比できる形で追記する

### 3.9 ドキュメント更新（§1.3・決定事項S12）

- [ ] T-37 `設計書_ロジック・プロンプト編_ミチナリ_v1.1.md`の`prompt_texts.HELP_ASSISTANT`参照（2526・2538行目）を`prompt_texts_common.HELP_ASSISTANT`へ更新し、改訂履歴に1行追加する

## 4. テスト計画

- 各手順（T-01〜T-37）の後、関係するテストファイルを個別実行し、分割前と同じ件数・同じ結果（合格）であることを確認する
- 全手順完了後、§2と同じ一式（`ruff check`・`pytest --cov`・`vitest`・`oxlint`・`tsc -b`）を再実行し、件数をベースラインと比較する（§9に記録）
- `grep -rn "record_service\.\|export_service\.\|goal_service\.\|prompt_texts\."`で、移動した関数・定数が新モジュール経由に揃っていることを確認する（T-09・T-17・T-22・T-27の再確認）
- 公開関数のシグネチャ・振る舞いは変えないため、既存テストは**期待値を一切変更せず**、分割・移動のみで合格することを確認する
- `_serialize_record`・`register_progress`の複雑度がradonで低下していることを確認する（§4.1に記録）
- `tests/test_build_package.py`分割後も配布パッケージのビルド確認テストが通ることを確認する（T-35）

### 4.1 複雑度（radon cc）の分割前後比較（分割後に記入）

| 関数 | 分割前 | 分割後 |
| --- | --- | --- |
| `api/records._serialize_record` | C (19) | （T-28後に記入） |
| `record_service.register_progress` | C (17) | （T-05後に記入） |

## 5. 未決事項

無し。本書内の設計判断（ファイル分割境界・配置・テスト分割方針・命名規則）は、利用者への3件の確認（goal_service分割方針／test_migration分割方針／test_build_package分割方針／分割ファイルの命名接頭語）と、既存コードの呼び出し状況の調査（§1）により決定した。

## 6. 別件（範囲外で見つけた問題）

- `docs/仕様書_ミチナリ_v1.1.md`の13.6節（1788行目付近、資格試験の達成判定根拠の説明）が`goal_service.close_goal`という**現存しない関数名**を参照している（現在の実装は`complete_goal`）。S-12の解消済み注記（1717行目）は正しく`compute_is_achieved`を参照しているため、1788行目のみが取り残されている。本リファクタリング（ファイル分割）とは無関係に以前から存在する不整合のため、本Todoでは修正しない
- `docs/設計書_データ構造編_ミチナリ_v1.1.md`の8章ディレクトリ構成図（1590〜1669行目）は、現行の`app/services/`配下38ファイル中20ファイル程度しか列挙していない長年の陳腐化状態（`ai_context_*`・`daily_feedback_service`・`recap_service`等多数が未掲載）。S01でも同種の箇所を対象外と判断した前例に従い、本Todoでも範囲外とする（全面更新は別タスクで対応する）
- S01のベースラインで記録されていた`frontend/src/pages/CalendarPage.test.tsx`の既知失敗（jsdomの`Not implemented: navigation to another Document`）が、本セッションのベースライン取得時には再現しなかった（155ファイル・1318件全合格）。テストの不安定性（flaky）の可能性があるため、再発した場合はS01の記録を参照する

## 7. 完了の定義

- §3の全項目が`[x]`になり、バックエンド・フロントエンドともテストが通る
- §2のベースラインと比較して、テスト件数が減らない（減った場合は理由を説明する）
- `_serialize_record`・`register_progress`の複雑度が分割前より下がっていることをradonで確認する（§4.1）
- 旧名称（`record_service`・`export_service`の単一ファイル、`prompt_texts`の単一ファイル）の残留が無い（alembicの意図的な保持箇所を除く）
- `goal_service.py`の残留関数のみが同ファイルに残り、移動した関数が新2モジュールに揃っている
- §1.3・§3.9のドキュメントが更新済み
- 配布パッケージの同梱確認・PyInstaller設定にファイル分割の影響が無いことを確認する（T-35）

## 8. 作業記録

- 2026-10-11 フェーズA実施（調査・ベースライン取得）
  - S01（`ai_context_service`分割）が`main`へマージ済み（コミット`bdd41ae`）であることを確認し、前提を満たすことを確認した
  - ruff・pytest（1,838件合格・カバレッジ100%）・vitest（1,318件合格、既知失敗0件）・oxlint・tscのベースラインを確認。対象2関数のradon cc測定値がタスク本体の記載（19・17）と一致することを確認した
  - `record_service.py`・`export_service.py`・`goal_service.py`・`prompt_texts.py`の全関数・定数を読み、分割先（共通／資格試験／読書／仕事、またはgoal_serviceのみ処理段階別）を決定した
  - 4ファイルの呼び出し元をフルスキャンし、実importとコメントのみの参照（誤検出2件を含む）を区別した
  - 未決事項3件（goal_service分割方針・test_migration分割方針・test_build_package分割方針）と、分割ファイルの命名接頭語について利用者に確認し、全て回答を得た（§0・§5）
