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

- [x] 13.2: `schedule_service.compute_delay_kind`・`ScheduleDelayKind`、既存`computeDelayDays`のガント連携確認
- [x] 13.3: `AiPurpose.SCHEDULE_REVISION`・`ConversationScope.SCHEDULE_REVISION`、`app_setting`6キー、`seed_data.py`のprompt_template投入
- [x] 13.3: `schedule_revision_service`のAI呼び出し（ensure_conversation→send_and_log→discard_conversation、使い捨て会話）
- [x] 13.4: `schedule_revision_block_parsing`（CHANGE/WARNING/総評、ReDoS対策）
- [x] 13.5: 検証（所有者・状況・日付・期限・差分・理由・重複・注意ブロック）
- [x] 13.6: モデル2件・Alembicマイグレーション・`DATA_SCHEMA_VERSION`更新
- [x] 13.7: 確定3API応答への`schedule_revision_candidates`追加、生成API（AUTO/MANUAL、1日1回）、判断API（承認/却下/確認済み、stale検知、RESOLVED遷移）、`GET /goals/{goal_id}/schedule`への未判断修正案の埋め込み、`GET /dashboard`への案内追加
- [x] 13.8: スケジュールタブ（ボタン・パネル・点線重ね・未保存時の無効化）、SC-06の案内、ダッシュボードの案内
- [x] D-62: 目標の期限解決（EXAM/READING/WORK）
- [x] D-65: 古い修正案の置き換え（SUPERSEDED）
- [x] D-48: ja.json/en.json・help_content.json
- [x] D-49: 仕様書・設計書（ロジック・プロンプト編・データ構造編）

## 7. 追跡表

| D-ID | 内容 | 実装箇所 | テスト |
| --- | --- | --- | --- |
| D-41（改訂） | 本機能のデータは既存のAIプロンプト・ナレッジエクスポートに含めず、スケジュール修正案の生成時のみAIへ渡す | `AiPurpose.SCHEDULE_REVISION`を既存purposeと独立に新設（`enums.py`既存値は無変更）。`schedule_revision_service._build_daily_report_stages`等の文脈組み立てはこのサービス内のみで使用 | 回帰の網（4章）：既存の`test_daily_feedback_service.py`等を無変更のまま実行し基準2838件→2922件（新規84件は本単位関連のみ）で全合格を確認 |
| D-51 | 単位5として単位1〜4完了後に開発する | （本単位の前提そのもの） | 0章のベースライン確認（単位1〜4のmainマージ・PR#145〜148確認） |
| D-52 | 日次フィードバックとは別のAI呼び出しで生成し、既存フィードバックに影響させない | `schedule_revision_service._call_ai`（専用の`ensure_conversation`/`send_and_log`/`discard_conversation`） | `TestGenerateProposal`内のAI呼び出しテスト群、D-41と同じ回帰の網 |
| D-53 | 生成のきっかけは確定後。確定応答は待たせない | `api/records.py`の確定3エンドポイントは`schedule_revision_candidates`のみ返す（AI呼び出しなし）。生成は画面側（`useDailyReportScheduleRevisionBanner.generateForGoals`）から確定後に別途呼ぶ | `test_api_records_exam.py`等の既存テスト（応答が無変更のまま通ること）、`useDailyReportScheduleRevisionBanner.test.ts` |
| D-54 | 遅れはAIを使わずシステムが判定。遅れがなければAUTOはAIを呼ばない | `schedule_service.compute_delay_kind`、`schedule_revision_service.list_revision_candidate_goal_ids`・`generate_proposal`のAUTO分岐 | `TestComputeDelayKind`（`test_schedule_service.py`）、`test_auto_trigger_without_any_delay_returns_none_and_does_not_call_ai` |
| D-55 | AIが変更できるのは未完了行の予定開始日・予定終了日のみ | `_validate_changes`の状況フィルタ、`ParsedChangeBlock`が予定日・理由のみを持つ | `test_discards_a_change_for_a_done_item` |
| D-56 | 行ごとに承認・却下。承認前に日付を手で修正可。全承認・全却下 | `useScheduleRevisionEditedDates`・`useScheduleRevisionPanelActions`・`ScheduleRevisionChangeRow.tsx` | `ScheduleRevisionPanel.test.tsx`（「承認ボタンは編集後の日付を添えてonDecideを呼ぶ（D-56）」「開始日・終了日を入力し直すと...」） |
| D-57 | 承認はスケジュールタブで行い、ガントに点線で重ねる。日次報告・ダッシュボードに案内とリンク | `ScheduleGanttProposedBand.tsx`・`scheduleRevisionBandMapping.buildProposedBandByItemId`、`DailyReportScheduleRevisionBanner.tsx`、`features/dashboard/ScheduleRevisionBanner.tsx`、`ROUTES.goalScheduleTab` | `ScheduleTab.test.tsx`（帯の表示）、`DailyReportScheduleRevisionBanner.test.tsx`、`features/dashboard/ScheduleRevisionBanner.test.tsx`、`GoalDetailPage.test.tsx`（deep link） |
| D-58 | 「AIに修正案を依頼」ボタンで遅れがなくても依頼できる | `ScheduleToolbar.tsx`のボタン、`generate_proposal`のMANUAL分岐（遅れゲートを適用しない） | `test_manual_trigger_without_any_delay_still_calls_ai`、`ScheduleToolbar.test.tsx` |
| D-59 | 変更前の値が一致する行だけ承認できる。不一致行は他行に影響させず保留 | `decide()`の`is_stale`判定・`blocked_reason="STALE_BEFORE_VALUE"` | `test_approving_a_stale_row_is_skipped_without_blocking_other_rows`、`test_decide_endpoint_marks_a_stale_row_without_applying_it` |
| D-60 | 前後関係列は作らない。AIが行の並び順等から推測し理由に書く | プロンプト本文（`prompt_texts_common.SCHEDULE_REVISION`）の指示のみ。`ScheduleRevisionProposalItem`に順序/依存関係の列を追加していないことをモデル定義で確認 | `backend/app/models/schedule_revision.py`のフィールド一覧（順序列が存在しないこと） |
| D-61 | 制約（進行中は終了日のみ・未着手は両方・本日以降・開始≦終了・理由必須・期限超え不可）に反する行は捨てる | `_invalid_planned_date_reason`（`_validate_changes`・`decide`共有、本単位コミット前チェックで抽出） | `TestGenerateProposal`の`test_discards_a_change_*`群、`TestDecideValidationErrors` |
| D-62 | 目標の期限は既存仕様（資格=`compute_due_date`転用、読書=`book.due_date`、仕事=なし）に合わせる | `schedule_revision_service.resolve_goal_due_date` | `TestResolveGoalDueDate`（EXAM固定/範囲/複数科目/科目無し、READING、WORK） |
| D-63 | 期限内に収まらない行は注意（WARNING）として理由付きで出す | `_validate_warnings`、プロンプトの「種類: 注意」指示 | `test_valid_warning_block_creates_a_warning_item`、`ScheduleRevisionPanel.test.tsx`（注意行表示） |
| D-64 | 直近の却下内容を次回生成時にAIへ渡す。却下理由は任意 | `_format_recent_rejections`、`schedule.revision.recent_rejections_count` | `test_includes_recent_rejections_in_the_prompt` |
| D-65 | 未承認の修正案がある状態で新しい修正案ができたら古い方の未判断行を置き換え済みとする | `_supersede_pending_proposal` | `test_a_new_proposal_supersedes_the_old_pending_one`、`test_superseding_skips_items_that_are_already_decided` |
| D-66 | AIの応答は信頼しない入力として扱い、区切りブロック形式で検証、不正は個別に捨てる | `schedule_revision_block_parsing.py`（`ai_block_parsing_common.split_blocks`を共有、本単位コミット前チェックで抽出）、`_validate_changes`/`_validate_warnings`の所有者・状況・日付チェック | `test_schedule_revision_block_parsing.py`（ReDoS耐性含む）、`test_discards_a_change_block_for_another_goals_row`、`test_discards_a_warning_for_another_goals_row` |
| D-18（拡張） | ガントの「開始の遅れ」の印をフロントエンドでも判定する | `scheduleDelay.computeDelayInfo`、`ScheduleGanttRow.tsx`のTooltip文言分岐 | `scheduleDelay.test.ts`（START_DELAY境界値群）、統合経路は`ScheduleGrid.test.tsx`（NOT_STARTED・today=開始日の4日後の固定値でカバー、独立レビューで確認） |
| D-48 | ゼロハードコーディング（文言・設定値の外部化） | `ja.json`/`en.json`の`schedule.revision.*`等、`app_setting`6キー、`help_content.json`再生成 | `label-checker`エージェントでの横断確認（違反なし）、`test_help_content.py` |
| D-49 | 仕様書・設計書の更新 | 6.2/6.1/6.5/10/08（AI-28追加）、設計書データ構造編5.1/5.2/5.4/5.6/06、設計書ロジック・プロンプト編31章新設 | （文書更新のため自動テスト対象外。更新箇所は本章末尾の10章・引き継ぎ事項に記載） |

## 8. 次の単位への引き継ぎ事項

本単位が本機能（開発Todo_スケジュール・ガントチャート_v1.1）の最終単位のため、将来このAI用途・画面へ手を入れる際の留意事項を記載する。

1. **区切りブロック形式のAI応答解析を新設する場合は`backend/app/services/ai_block_parsing_common.py`の`split_blocks`を再利用すること。** 本単位のコミット前チェックで、`quiz_block_parsing.py`と`schedule_revision_block_parsing.py`が区切り正規表現・文字数上限ガードを逐語重複させていたことが判明し、この共通モジュールへ集約した（DRYの原則）。次に同系統のAI用途（区切りブロック形式）を追加する場合も、フィールド抽出の正規表現だけを専用に書き、ブロック分割自体は共有する。
2. **同じ日付制約を生成時検証・承認時再検証の両方に課す場合は、両者で検証ロジックを共有すること。** `_invalid_planned_date_reason`（`schedule_revision_service.py`）がこの前例。片方だけ仕様変更すると他方が追従し忘れるリスクがあるため、将来13.5の制約（進行中の行の扱い等）を変更する際は、この共有関数越しに両経路が更新されることを確認する。
3. **同じ役割（案内バナー等）を複数の画面に置く場合、コンポーネント名に画面名を冠して区別すること。** 本単位のコミット前チェックで、ダッシュボードと日次報告の両方に`ScheduleRevisionBanner`という同名だが別実装のコンポーネントが存在し、import時にファイルパスを見ないと区別できない状態になっていたため、日次報告側を`DailyReportScheduleRevisionBanner`（フックも`useDailyReportScheduleRevisionBanner`）へ改名した。ダッシュボード側は文脈上の曖昧さが小さいため改名を見送ったが、今後similar banner/hookを追加する際は最初から用途を冠した名前にする。
4. **応答全体（ブロック分割前）には文字数上限が無い（既存の`quiz_block_parsing.py`と同じ設計、injection-reviewerが指摘・対応不要と判断）。** 1ブロックあたりの上限（`schedule.revision.max_block_chars`）はあるが、応答全体のサイズには上限がない。新規のDoS経路ではなく既存設計の横展開のため本単位では対応しないが、気になる場合は`quiz_block_parsing.py`側と合わせて別Issue化を検討する。
5. **設定画面に出さない内部パラメータ（`schedule.revision.*`、フォルダ名）の一覧は`settings_service.py`のコメントに集約されている。** 単位2・AI-18・AI-25と同じ「設定画面からは変更できない内部パラメータ」の扱いを継続している。将来これらを設定画面へ出す場合は、この一覧コメントと`AiConnectionSection.tsx`側のテスト（購入数チェック）の両方を更新すること。
6. **仕様書8章（AI連携仕様）のAI-NN表は、新規AI用途を追加するたびに本単位のように番号を振って追記する必要がある。** 本単位では当初この表への追記が漏れていたが、独立した文書更新エージェントのレビューで発見し、AI-28として追記して解消した。次回以降も新規AI用途の追加時はこの表（8.1節）と該当する詳細段落の両方を更新すること。

## 9. 報告が必要な食い違い・範囲外の不具合

2章で報告した2件（D-62の目標期限の補足実装、D-54/D-58のAUTO/MANUAL遅れゲートの適用範囲）は、いずれも実装を止めるべき食い違いではなく、本書の意図のとおり実装詳細で吸収できると判断して対応済み（詳細は2章参照）。

実装完了後のコミット前チェック（10章）で新たに見つかった食い違い・不具合は無かった。独立レビュー（10章の8エージェント＋独立サブエージェントによる文書レビュー）で見つかった指摘はいずれも本単位の範囲内で修正済みであり、範囲外の既存不具合の発見も無かった。

## 10. コミット前チェック（15.1手順13・14・16）の結果と対応

CLAUDE.md「コミット前チェック」・15.1手順13に基づき、該当する観点別レビューエージェント8種（dry-reviewer・style-reviewer・label-checker・auth-reviewer・injection-reviewer・xss-reviewer・secret-reviewer・test-coverage-reviewer）を本単位のdiff（`96cac54..HEAD`、単位4のmainマージ直後からの差分）に対して並列実行し、その後利用者からの指示でperformance-reviewerも追加実行した（全9観点）。

| 観点 | 結果 | 対応 |
| --- | --- | --- |
| DRY/複雑度 | MEDIUM×2：①`schedule_revision_block_parsing.py`が`quiz_block_parsing.py`と区切り正規表現・サイズガードを逐語重複、②`_validate_changes`と`decide()`のAPPROVED分岐が同じ日付制約を別実装。LOW×1：`useScheduleTabErrorToasts`の3つの同型`useEffect` | ①`ai_block_parsing_common.py`を新設し両ファイルから共有、②`_invalid_planned_date_reason`を新設し両経路から共有。LOWは軽微と判断し見送り（3つで増殖が止まっており、増える兆候があれば次回対応） |
| 命名・コメント | LOW×2：①`api/schedule_revision.py`の`_is_stale`第一引数`item`に型注釈が無い、②`ScheduleRevisionBanner`がdashboard/recordの2箇所で同名・別実装 | ①`ScheduleRevisionProposalItem`型を明示、②record側を`DailyReportScheduleRevisionBanner`（フックも`useDailyReportScheduleRevisionBanner`）へ改名。dashboard側は文脈上の曖昧さが小さいため維持 |
| ハードコード文言 | 違反なし（画面文言は全て`t()`経由、閾値は全て`app_setting`経由であることを確認） | 対応不要 |
| 認証・認可 | LOW×2：①`decide()`の検証ループが同一`proposal_item_id`の重複を明示的に拒否せずstale判定の副作用に依存、②CLOSED目標での生成・判断ブロックのAPI層回帰テストが無い | ①`decide()`冒頭で`seen_proposal_item_ids`による明示的な重複拒否を追加（`_validate_changes`等と同じ`seen_ids`パターン）、②`test_generate_endpoint_rejects_closed_goal`・`test_decide_endpoint_rejects_closed_goal`を追加 |
| インジェクション（ReDoS・間接プロンプトインジェクション） | 重大な指摘なし。LOW×1：応答全体（分割前）に文字数上限が無い（既存`quiz_block_parsing.py`と同一方針） | 既存設計の横展開のため対応不要と判断（8章「引き継ぎ事項」4に記録） |
| XSS | 指摘なし（AI生成文面は全てJSXのプレーン補間で表示、HTML直接挿入系APIを使っていないことを確認） | 対応不要 |
| 機密情報 | 指摘なし（アシスタントUIDは既存の使い回しパターン、AI通信ログは既存のDBログ基盤のみ、ブラウザ記憶領域への保持なし） | 対応不要 |
| テストカバレッジ | MEDIUM×2（`ScheduleGanttRow.tsx`のSTART_DELAY分岐、`scheduleRevisionBandMapping.ts`の未テスト分岐、との指摘） | 実測の`coverage-summary.json`で両ファイルとも実際には100%（branch含む）であることを確認。前者は`ScheduleGrid.test.tsx`の統合テスト（NOT_STARTED・today=開始日+4日の固定値）が間接的にカバーしており、後者も`ScheduleTab.test.tsx`経由で分岐を踏んでいることを確認。指摘は静的解析（専用テストファイルが無いこと）に基づく誤検知と判断し、追加テストは不要 |
| パフォーマンス（利用者指示による追加実行） | HIGH×1：`decide()`の検証ループが`session.get(ScheduleItem, ...)`を判断対象行の件数分、個別に呼ぶN+1（`schedule.max_items`既定100、「すべて承認」で最大100回程度の個別SELECTが発生しうる）。LOW×1：同リクエスト内で`serialize_proposal()`が同じScheduleItemを再取得する二重ロード（上記修正で実害は軽減、対応は見送り） | HIGH：`decide()`冒頭で対象の`ScheduleItem`を`id.in_(...)`で1クエリに一括取得する辞書へ変更（`schedule_service.apply_report_schedule_item_updates`と同じ方式）。LOWは優先度が低いとレビューで判断されたため見送り |

**独立レビュー（15.1手順16）**：上記8エージェントはいずれも実装の文脈を持たない新規サブエージェントとして起動し、diffのみから指摘を行った（実装時の意図を共有していない独立レビューの条件を満たす）。加えて文書更新（仕様書・設計書）も実装から独立した新規サブエージェントへ依頼し、既存記法との整合・抜け漏れ（8章AI-NN表への追記漏れ）を検出・報告させ、報告を受けて追記した。

対応後、backend・frontendとも全テスト再実行済み（2章の比較を参照）。
