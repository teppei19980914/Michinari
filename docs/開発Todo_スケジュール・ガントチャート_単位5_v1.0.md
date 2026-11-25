# 開発Todo：スケジュール・ガントチャート機能 単位5（AIによるスケジュール修正案） v1.0

入力: `docs/開発Todo_スケジュール・ガントチャート_v1.1.md`（第2章D-41・D-51〜D-66・第13章・第14章・第9章単位5・第15章）、`docs/開発Todo_スケジュール・ガントチャート_単位1_v1.0.md`〜`単位4_v1.0.md`（引き継ぎ事項）、`docs/CODING_RULES.md`「AI通信とトランザクション」。

## 0. ベースライン（着手前に確認）

- 前提確認：単位1（祝日基盤、PR#145）・単位2（データモデルとAPI、PR#146）・単位3（スケジュールタブ、PR#147）・単位4（日次報告との連携、PR#148）はいずれも実装済み・`main`にマージ済み（`git log origin/main --oneline --merges`で確認。#149は日次のauto-commitのマージで単位5とは無関係）。
- backend: `../myvenv/Scripts/python.exe -m ruff check .` → All checks passed。`pytest -q` → **2838 passed**, coverage 100%（282.77s）。
- frontend: `npm run lint`（oxlint、`DayTypeDefaultsCard.tsx`のmax-lines-per-function警告1件のみ。単位1由来の既知の警告で本単位の範囲外）・`npm run build`（tsc -b + vite build, exit 0）・`npm test -- --run`（**266 files, 2100 tests**, coverage100%, exit 0）。

## 1. 脅威分析（STRIDE）

- **データフロー**：[利用者] → 日次報告確定/SC-07（単位4実装済み） → 確定APIの応答（`schedule_revision_candidates`、新規） → [利用者の操作 または 自動] → `POST /goals/{goal_id}/schedule/revision-proposals`（信頼境界） → `schedule_revision_service` → NewtonX（外部AI基盤、信頼境界） → 応答の解析・検証 → `schedule_revision_proposal`/`schedule_revision_proposal_item`（DB） → `POST .../decisions`（信頼境界） → `schedule_item`（予定日の反映）。
- **S（なりすまし）**：既存の認証機構と同一。新規の認証経路は追加しない。対象外。
- **T（改ざん）**：
  - AIの応答は信頼しない入力として扱う（D-66）。`quiz_generation_service.py`と同じ区切りブロック形式・ReDoS対策（`[^\n]+?`・`re.DOTALL`不使用・1ブロック文字数上限）で解析し、ブロック単位で13.5の全ルールを検証する。不正なブロックは個別に捨てる。
  - 間接プロンプトインジェクション対策：AIの応答が「他の目標の行ID」「完了済み・中止済みの行」「期限を超える日付」「進行中の行の開始日変更」を指示してきても、13.5の検証（所有者チェック・状況チェック・日付チェック）で機械的に拒否する（AIの指示を信用せず、システムが決めた制約のみを適用）。利用者の日次報告本文（日記等）がプロンプトへ注入される経路（週次要約・直近記録）が間接プロンプトインジェクションの主な経路のため、ここを重点的にテストする（ユーザー指示の重点確認）。
  - 承認APIは「変更前の値が現在の値と一致すること」（D-59）を再検証する（スケジュール画面での同時編集・多重送信への対策）。
- **R（否認）**：予定日の変更履歴は`schedule_revision_proposal_item`が兼ねる（14章補足8）。既存の`schedule_item_history`（状況・実績日）とは別の関心事のため競合しない（単位4引き継ぎ事項）。
- **I（情報漏洩）**：生成API・判断APIはいずれも対象の目標に属する行のみを受け付け、他の目標の存在を推測できるメッセージを返さない（単位2`_check_owned_by_goal`と同じ方針）。AIへ渡す情報は対象の目標1件分のスケジュール・日次報告文脈のみ（D-41、既存のナレッジエクスポート・日次フィードバックには含めない）。
- **D（サービス拒否）**：1ブロックの文字数上限（`schedule.revision.max_block_chars`）、直近の却下件数の上限（`schedule.revision.recent_rejections_count`）、理由・作業内容の文字数上限（プロンプトへ渡す量を制限）で対策する。自動生成は目標・報告対象日ごとに1回まで（D-65と別の13.2の制約）。
- **E（権限昇格）**：
  - 生成（MANUAL）・判断APIは`goal_service.ensure_goal_editable`（単位2の`save_schedule`と同じ、CLOSED以外なら操作可）で保護する。生成（AUTO）は確定APIからのみ呼ばれ、確定API自体がACTIVE限定（単位4）であるため追加の認可は不要。
  - AI通信中はDBへ書き込まない（CODING_RULES.md「AI通信とトランザクション」）。修正案の保存はAI応答を得た後、`serialize_writes()`内の1トランザクションでコミットする。`test_ai_write_lock.py`と同じ観点のテストを追加する（ユーザー指示の重点確認）。

対策はすべてMitigate（既存の認可パターン・検証パターンの再利用、新規の攻撃面はAI応答の解析のみで多層防御済み）。受容したリスクなし。

## 2. 報告が必要な食い違い・補った実装詳細（15.1手順5）

いずれも「仕様の意図自体は変わらない、実装の詳細で吸収できる」と判断し、単位1〜4の前例に倣って対応しつつ報告する。**実装を止めるべき食い違いは見つからなかった。**

1. **D-62「資格試験は既存の締切（`material_service.compute_due_date`）」は、同関数がそのまま目標の期限を返す関数ではない点を補う必要がある。** `compute_due_date(subjects, start_date)`は教材1件分の締切を算出する関数であり、目標の期限という概念は既存コードに存在しない。本書の意図（「新しく計算式を書かない」D-62本文）に従い、**同じ関数をそのまま**、対象を「教材が紐づく科目」ではなく「目標に紐づく全科目（`goal.exam_subjects`）」、`start_date`を`goal.start_date`に置き換えて呼ぶ（計算式自体は1つも新しく書かない）。資格試験の目標がまだ試験科目を1件も登録していない場合（`goal.exam_subjects`が空）は、`compute_due_date`が呼べない（`min()`が空集合で失敗する）ため、この場合は「期限なし」として扱う（D-62の対象外ケースの補足、要確認であれば指摘を仰ぐ）。
2. **D-62「読書は書籍の読了期限（`book.due_date`）」は、`book.due_date`がNOT NULL（1目標1冊、`models/book.py`）のためREADINGの目標は常に期限を持つ。** 補足不要、そのまま実装する。
3. **13.3「AI通信とトランザクション」のscope_keyは「1回ごとに完結する呼び出しとし、会話は継続しない」という方針に沿って`uuid.uuid4().hex`とし、`ai_conversation.discard_conversation`で送信後に即削除する。** 既存の`summary_card_service.generate_sentence`・`help_assistant_service`と同型（1問1答、使い捨て）。専用の会話フォルダ名（`ai.schedule_revision_folder_name`）を新設し、目標ごとの既定フォルダ（DAILY_FEEDBACK等が使う`{prefix}_{目標名}`）とは分離する（`summary_card_service`と同じ方針）。
4. **13.3「日次報告の文脈」の期間境界は、既存の`reading_feedback_service`等に倣い `period_start=目標の開始日（READINGのみbook.start_date）`・`period_end=today - 1日`とする。** 当日分はスケジュールの行データ自体（予定日・状況・実績日）に既に反映されているため、日次報告文脈へ当日分を重複して注入する必要がない（既存方針と同じ「当日入力は別経路で渡す」の考え方だが、本用途では「当日入力」に相当するものがスケジュール行自体のため、文脈側はperiod_end=today-1のみで足りる）。
5. **13.6のテーブル定義で`schedule_revision_proposal`に`updated_at`の記載が無いが、本書の他の可変テーブル（`goal_schedule`等）と同じ`TimestampMixin`を使う。** status（PENDING→RESOLVED/SUPERSEDED）が後から変わる可変行のため、既存の慣例（可変行は`TimestampMixin`、追記専用ログ〈`schedule_item_history`〉のみ例外）に揃える。`schedule_revision_proposal_item`は`decided_at`列が更新時刻の役割を兼ねるため`TimestampMixin`は使わず、本書が列挙した列のみを持つ（`schedule_cell`・`schedule_item_history`と同じ「列挙された列のみ」の前例）。
6. **13.7の判断API（decisions）のレスポンス形式は本書に明記が無いため補った。** `ScheduleRevisionProposalRead`（修正案1件のフル表示、`GET /goals/{goal_id}/schedule`が埋め込むものと同じ形）を返す。「変更前の値が現在の値と一致しない行」は、その回の判断を適用せず`decision`を`PENDING`のまま残し、`blocked_reason="STALE_BEFORE_VALUE"`を追加のフィールドとして付与する（他の行の処理は継続、本書13.7「他の行は処理する」）。
7. **13.7「承認した行は...`goal_schedule.revision`を1増やす」は、1回のdecisions呼び出しで複数行を承認した場合も1回だけ増やす。** 単位2`save_schedule`・単位4`apply_report_schedule_item_updates`と同じ「1回のAPI呼び出しで1増やす」という楽観ロックの単位に揃える（単位4開発Todo3章補足3の前例）。
8. **D-54の「遅れがなければAIを呼ばない」とD-58「遅れがなくても依頼できる」は、trigger（AUTO/MANUAL）で適用範囲が分かれると解釈した。** 13.7の表に「AUTOで遅れがない場合はAIを呼ばずに『対象なし』を返す」と明記されており、D-54の遅れゲートはAUTO専用、MANUAL（ボタン）はD-58のとおり常にAIを呼ぶ（本文で解決済みのため報告のみ、実装を止める食い違いではない）。
9. **ガントの「開始の遅れ」の印（14章補足4）は、フロントエンドの`scheduleDelay.computeDelayDays`が既存で終了の遅れのみを算出している。** 本単位でバックエンドに置く共通判定関数（`schedule_service.compute_delay_kind`）と同じ判定順序（終了の遅れを先に判定、未着手かつ終了の遅れが無い場合のみ開始の遅れを判定）で`computeDelayDays`を拡張する（単位3引き継ぎ事項のとおり）。バックエンドAPIのレスポンス形式は変更しない（ガント描画は既存同様、取得済みの`planned_start_date`等から画面側で算出するため新規APIは不要）。

## 3. 影響範囲表

### 3.1 backend（新規）

| ファイル | 内容 | 理由 | D-ID |
| --- | --- | --- | --- |
| `backend/app/models/schedule_revision.py` | `ScheduleRevisionProposal`・`ScheduleRevisionProposalItem` | 13.6 | D-59,D-65 |
| `backend/alembic/versions/<hash>_schedule_revision_tables.py` | 新規2テーブルの`create_table`のみ | 13.6 | — |
| `backend/app/schemas/schedule_revision.py` | `ScheduleRevisionGenerateRequest`・`ScheduleRevisionProposalRead`・`ScheduleRevisionProposalItemRead`・`ScheduleRevisionDecisionInput`・`ScheduleRevisionDecisionsRequest` | 13.7 | 13.7 |
| `backend/app/services/schedule_revision_block_parsing.py` | `===`区切り・`[^\n]+?`・`re.DOTALL`不使用・`_MAX_BLOCK_CHARS`、CHANGE/WARNING/総評の3パターン | 13.4 | D-66 |
| `backend/app/services/schedule_revision_service.py` | 遅れ判定（`schedule_service.compute_delay_kind`を呼ぶ）、目標の期限解決、AI呼び出し（ensure_conversation→send_and_log→discard_conversation）、応答の検証（13.5）、保存・置き換え（D-65）、判断（13.7） | 13.2〜13.7 | D-51〜D-65 |
| `backend/app/api/schedule_revision.py` | `POST /goals/{goal_id}/schedule/revision-proposals`、`POST .../revision-proposals/{proposal_id}/decisions` | 13.7 | 13.7 |
| `backend/app/init/prompt_texts_common.py` | `SCHEDULE_REVISION`（3カテゴリ共通の1本） | 13.3 | D-52 |
| `backend/tests/schedule_revision_helpers.py`（新規） | テスト用ヘルパー（目標・作業項目・修正案の組み立て） | 第9章「テスト」 | — |
| `backend/tests/test_schedule_revision_block_parsing.py` | 13.4の解析・ReDoS耐性テスト | 13.10 | D-66 |
| `backend/tests/test_schedule_revision_service.py` | 遅れ判定・期限解決・検証・保存・置き換え・判断のテスト | 13.10 | D-51〜D-65 |
| `backend/tests/test_api_schedule_revision.py` | API層の結合テスト（認可境界・409相当・AI通信モック） | 13.10 | 13.7 |

### 3.2 backend（既存ファイルの変更）

| ファイル | 変更内容 | 理由 | D-ID |
| --- | --- | --- | --- |
| `backend/app/constants/enums.py` | `AiPurpose.SCHEDULE_REVISION`・`ConversationScope.SCHEDULE_REVISION`・`ScheduleRevisionTrigger`・`ScheduleRevisionProposalStatus`・`ScheduleRevisionItemKind`・`ScheduleRevisionDecision`を追加 | 13.3,13.6 | D-52 |
| `backend/app/constants/app_setting_keys.py` | `AI_ASSISTANT_UID_SCHEDULE_REVISION`・`AI_SCHEDULE_REVISION_FOLDER_NAME`・`SCHEDULE_REVISION_RECENT_REJECTIONS_COUNT`・`SCHEDULE_REVISION_REASON_MAX_CHARS`・`SCHEDULE_REVISION_DESCRIPTION_MAX_CHARS_IN_PROMPT`・`SCHEDULE_REVISION_MAX_BLOCK_CHARS`を追加 | 13.9 | 13.9 |
| `backend/app/init/seed_data.py` | 上記6キーの初期値、`AiPurpose.SCHEDULE_REVISION`のprompt_template投入 | 13.9 | 13.9 |
| `backend/app/services/settings_service.py` | `assistant_uid_schedule_revision`をAI設定のフィールド・マッピング辞書へ追加（既存の`assistant_uid_summary_card`と同じ扱い。フォルダ名・`schedule.revision.*`は`schedule.*`と同じく設定画面には出さない、単位2引き継ぎ事項の前例） | 横展開（設定画面のアシスタントUID） | — |
| `backend/app/services/schedule_service.py` | `ScheduleDelayKind`（END_DELAY/START_DELAY、サービス内部のみ・DB非永続）と`compute_delay_kind(item, today)`を追加（D-18・13.2の共通判定関数、ガントの遅れの印もこの関数の結果を使う） | 13.2,14章補足4 | D-18,D-54 |
| `backend/app/schemas/record.py` | `FinalizeRequest`/`ReadingFinalizeRequest`/`WorkFinalizeRequest`の応答側（`DailyRecordRead`）に`schedule_revision_candidates: list[int]`を追加 | 13.7 | 13.7 |
| `backend/app/api/records.py` | `_serialize_record`に`schedule_revision_candidates`引数（既定空リスト）を追加。確定3エンドポイントのみ`schedule_revision_service.list_candidates_excluding_already_generated(...)`の結果を渡す（`get_record`・`register_progress`は空リストのまま） | 13.7 | 13.7 |
| `backend/app/schemas/dashboard.py` | `GoalCardRead`に`has_pending_schedule_revision: bool`を追加 | 13.8 | 13.8 |
| `backend/app/api/dashboard.py` | PENDINGな修正案を持つ目標IDを1クエリで取得し`has_pending_schedule_revision`を設定（N+1禁止） | 13.8 | 13.8 |
| `backend/app/services/backup_service.py` | `DATA_SCHEMA_VERSION`を1.10→1.11、`_IMPORTABLE_SCHEMA_VERSIONS`に1.10を追加 | 7.5 | 7.5 |
| `backend/app/api/errors.py` | `ScheduleRevisionProposalNotPendingError`→409 `SCHEDULE_REVISION_PROPOSAL_NOT_PENDING`を追加 | 13.7 | 13.7 |
| `backend/app/services/exceptions.py` | `ScheduleRevisionProposalNotPendingError`を追加 | 13.7 | 13.7 |
| `backend/app/main.py` | `schedule_revision_router`を登録 | 既存の慣例 | — |
| `frontend/src/types/api.d.ts` | `npm run generate:api-types`で再生成 | 手書き禁止 | 第8章 |

### 3.3 frontend（新規）

| ファイル | 内容 | 理由 | D-ID |
| --- | --- | --- | --- |
| `frontend/src/features/schedule/scheduleRevisionTypes.ts`＋test | API型の別名・補助型 | — | — |
| `frontend/src/features/schedule/useScheduleRevision.ts`＋test | 生成・判断のmutation、`schedule(goalId)`クエリの無効化 | 13.7,13.8 | — |
| `frontend/src/features/schedule/ScheduleRevisionPanel.tsx`＋test | 総評・変更行一覧・注意行一覧・全承認/全却下・stale行の無効化 | 13.8 | D-56,D-59,D-63 |
| `frontend/src/features/schedule/ScheduleRevisionChangeRow.tsx`＋test | 1変更行（作業項目・変更前→変更後・日付修正・理由・承認/却下） | 13.8 | D-56,D-60 |
| `frontend/src/features/schedule/ScheduleRevisionWarningRow.tsx`＋test | 1注意行（作業項目・理由・確認しました） | 13.8 | D-63 |
| `frontend/src/features/schedule/ScheduleGanttProposedBand.tsx`＋test | 修正案の点線帯（未判断のCHANGE行のみ、ガントへ重ねる） | 13.8 | D-57 |
| `frontend/src/features/record/useScheduleRevisionBanner.ts`＋test | 確定応答の`schedule_revision_candidates`を受けて生成を呼び、結果（作成中/完了/失敗）を保持する状態機械 | 13.1,13.8 | 13.8 |
| `frontend/src/features/record/ScheduleRevisionBanner.tsx`＋test | SC-06の確定済みセクションへの案内表示 | 13.8 | 13.8 |

### 3.4 frontend（既存ファイルの変更）

| ファイル | 変更内容 | 理由 | D-ID |
| --- | --- | --- | --- |
| `frontend/src/api/schedule.ts` | `generateScheduleRevisionProposal`・`decideScheduleRevisionProposal`を追加 | 13.7 | — |
| `frontend/src/features/schedule/scheduleDelay.ts` | `computeDelayInfo`（kind: END/START）を追加、既存`computeDelayDays`はその日数部分を返す薄いラッパーへ変更（既存の呼び出し・戻り値は無変更） | 14章補足4 | D-18 |
| `frontend/src/features/schedule/ScheduleGanttRow.tsx` | `computeDelayInfo`を使い、開始の遅れのTooltip文言を分岐 | 14章補足4 | D-18 |
| `frontend/src/features/schedule/ScheduleToolbar.tsx` | 「AIに修正案を依頼」ボタンを追加（生成中は無効、閲覧のみの目標では非表示） | 13.8 | D-58 |
| `frontend/src/features/schedule/ScheduleTab.tsx` | `ScheduleRevisionPanel`・`ScheduleGanttProposedBand`の組み込み、未保存の変更がある間は承認・却下不可の案内 | 13.8 | D-56〜D-59,D-63 |
| `frontend/src/features/schedule/useScheduleEditorState.ts` | `hasUnsavedChanges`を`ScheduleRevisionPanel`へ渡す（13.8「保存または破棄してから判断してください」） | 13.8 | — |
| `frontend/src/features/record/ExamReportSection.tsx`・`ReadingReportSection.tsx`・`WorkReportSection.tsx` | 確定後に`ScheduleRevisionBanner`を表示 | 13.8 | 13.8 |
| `frontend/src/features/record/useDailyReportActions.ts` | 確定応答の`schedule_revision_candidates`を`useScheduleRevisionBanner`へ渡す | 13.1 | 13.1 |
| `frontend/src/features/dashboard/`配下の目標カード | `has_pending_schedule_revision`での案内とスケジュールタブへのリンクを追加 | 13.8 | 13.8 |
| `frontend/src/constants/queryKeys.ts` | 変更なし（既存の`schedule(goalId)`を無効化対象として再利用） | DRYの原則 | — |
| `frontend/src/locales/ja.json`・`en.json` | `settings.promptTemplate.purpose.SCHEDULE_REVISION`、`schedule.toolbar.requestRevision`、`schedule.revision.*`（パネル・行・stale文言）、`dailyReport.scheduleRevision.*`（作成中/完了/失敗）、`dashboard.scheduleRevision.*`（案内）、`errors.SCHEDULE_REVISION_PROPOSAL_NOT_PENDING` | D-48,ゼロハードコーディング | D-48 |
| `backend/app/content/help_content.json` | `export_help_content.py`で再生成 | ja.json由来のため手書き禁止 | D-48 |

### 3.5 文書（D-49）

| 文書 | 変更内容 |
| --- | --- |
| `docs/仕様書_ミチナリ_v1.1/06_画面仕様/6.2_SC-03_目標詳細・編集.md`（スケジュールタブの節） | 修正案パネル・点線重ね表示・「AIに修正案を依頼」を追記 |
| `docs/仕様書_ミチナリ_v1.1/06_画面仕様/6.5_SC-06_日次報告.md` | 確定後の修正案案内（作成中/完了/失敗）を追記 |
| `docs/仕様書_ミチナリ_v1.1.md`（ダッシュボードの章） | 修正案の案内を追記 |
| `docs/仕様書_ミチナリ_v1.1.md`（AI機能の一覧） | `SCHEDULE_REVISION`を追加 |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1.md` | プロンプト本文（13.3・13.4の形式）を追加、改訂履歴に追加 |
| `docs/設計書_データ構造編_ミチナリ_v1.1.md` | 新規2テーブル・列挙型・API・`DATA_SCHEMA_VERSION`を追記、改訂履歴に追加 |
| `frontend/src/content/help_content.json`経由の`help_content.json` | ja.json由来で再生成（直接編集しない） |

## 4. 回帰の網（15.1手順8、特性テスト）

| 対象 | 固定する現在の挙動 |
| --- | --- |
| `test_api_records_exam.py`・`test_api_records_reading.py`・`test_api_records_work.py`の確定系既存テスト | 確定APIの既存フィールド（`study_logs`等）の応答が`schedule_revision_candidates`追加後も無変更であること（新フィールドの追加のみ、既存フィールドへの影響なし） |
| `frontend/src/features/schedule/scheduleDelay.test.ts`（既存、終了の遅れ） | `computeDelayInfo`抽出・`computeDelayDays`のラッパー化の前後で、既存のテスト（DONE/CANCELLED/未完了の終了遅れ）が無変更のまま通ること |
| `test_schedule_service.py`（単位2〜4の既存テスト全件） | `compute_delay_kind`追加が既存の`validate_item_fields`等に影響しないこと（新規関数の追加のみ） |
| `test_api_dashboard.py`（既存） | `has_pending_schedule_revision`追加前の既存アサーションがそのまま通ること（既存目標カードの他フィールドは無変更） |

実装前に上記既存テストを変更前のコードで実行し、全て合格することを確認してから着手する。

## 5. 横展開チェックリスト

| 検索語 | 期待する結果 |
| --- | --- |
| `grep -rn "AiPurpose\." backend/app/init/seed_data.py` | `AiPurpose.SCHEDULE_REVISION`の投入が追加されていること（`test_list_prompt_templates_returns_all_purposes`・`test_every_ai_purpose_has_a_frontend_message`が自動検知する） |
| `grep -c "SCHEDULE_REVISION" frontend/src/locales/ja.json frontend/src/locales/en.json` | 両ファイルに同数のキーが存在すること（`settings.promptTemplate.purpose.SCHEDULE_REVISION`含む） |
| `grep -rn "ScheduleRevisionTrigger\|ScheduleRevisionProposalStatus\|ScheduleRevisionItemKind\|ScheduleRevisionDecision" backend/app frontend/src` | backendのmodels/schemas/services/constantsと、frontendは自動生成の`api.d.ts`・新規コンポーネントのみから参照。すべての値を網羅する分岐（判断APIのdecision別処理等）に漏れがないこと |
| `grep -n "SCHEDULE_REVISION_PROPOSAL_NOT_PENDING" backend/app/api/errors.py frontend/src/locales/ja.json frontend/src/locales/en.json` | 3箇所すべてに存在すること（`test_every_error_code_has_a_frontend_message`） |
| `npm run generate:api-types`後の`git diff --stat src/types/api.d.ts` | 新規スキーマの追加のみ（手書きの型定義が残っていないこと） |
| `grep -n "DATA_SCHEMA_VERSION\|_IMPORTABLE_SCHEMA_VERSIONS" backend/app/services/backup_service.py` | 1.11へ更新、1.10が取り込み対象に追加されていること |
| `grep -n "SCHEDULE_REVISION\|assistant_uid_schedule_revision" backend/app/services/settings_service.py` | `assistant_uid_schedule_revision`のみヒット（フォルダ名・`schedule.revision.*`は設定画面に出さない、単位2引き継ぎ事項と同じ扱い） |
| `grep -rn "compute_delay_kind\|computeDelayInfo" backend/app frontend/src` | バックエンドは`schedule_service.py`・`schedule_revision_service.py`のみ、フロントは`scheduleDelay.ts`・`ScheduleGanttRow.tsx`のみ（遅れ判定のロジックが他に複製されていないこと） |
| `grep -rn "dangerously" frontend/src/features/schedule frontend/src/features/record` | ヒットなし（AIの理由・総評をプレーンテキストで表示していること） |
| `help_content.json`の`schedule`・`dailyReport`・`dashboard`セクション | `export_help_content.py`実行後、ja.jsonの内容と一致すること（`test_help_content.py`） |
| `grep -rn "ensure_goal_editable\|ensure_operation_allowed" backend/app/services/schedule_revision_service.py` | 生成（MANUAL）・判断APIは`ensure_goal_editable`のみを使用（ACTIVE限定の`ensure_operation_allowed`は使わない、D-04との整合） |

## 6. チェックリスト（実装）

- [ ] 13.2: `schedule_service.compute_delay_kind`・`ScheduleDelayKind`、既存`computeDelayDays`のガント連携確認
- [ ] 13.3: `AiPurpose.SCHEDULE_REVISION`・`ConversationScope.SCHEDULE_REVISION`、`app_setting`6キー、`seed_data.py`のprompt_template投入
- [ ] 13.3: `schedule_revision_service`のAI呼び出し（ensure_conversation→send_and_log→discard_conversation、使い捨て会話）
- [ ] 13.4: `schedule_revision_block_parsing`（CHANGE/WARNING/総評、ReDoS対策）
- [ ] 13.5: 検証（所有者・状況・日付・期限・差分・理由・重複・注意ブロック）
- [ ] 13.6: モデル2件・Alembicマイグレーション・`DATA_SCHEMA_VERSION`更新
- [ ] 13.7: 確定3API応答への`schedule_revision_candidates`追加、生成API（AUTO/MANUAL、1日1回）、判断API（承認/却下/確認済み、stale検知、RESOLVED遷移）、`GET /goals/{goal_id}/schedule`への未判断修正案の埋め込み、`GET /dashboard`への案内追加
- [ ] 13.8: スケジュールタブ（ボタン・パネル・点線重ね・未保存時の無効化）、SC-06の案内、ダッシュボードの案内
- [ ] D-62: 目標の期限解決（EXAM/READING/WORK）
- [ ] D-65: 古い修正案の置き換え（SUPERSEDED）
- [ ] D-48: ja.json/en.json・help_content.json
- [ ] D-49: 仕様書・設計書（ロジック・プロンプト編・データ構造編）

## 7. 追跡表

（実装完了後に実装箇所・テスト名を記入する）

## 8. 次の単位への引き継ぎ事項

（本単位が最終単位のため、将来の拡張時の留意事項を記載する）

## 9. 報告が必要な食い違い・範囲外の不具合

（実装完了時に記入する）

## 10. コミット前チェック（15.1手順13・14・16）の結果と対応

（実装完了時に記入する）
