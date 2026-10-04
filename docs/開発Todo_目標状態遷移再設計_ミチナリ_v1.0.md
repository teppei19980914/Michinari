# 開発Todo：目標の状態遷移再設計（ミチナリ）v1.0

作成日: 2026-10-04
対象: 目標（資格・読書・仕事）の状態遷移、削除、一覧・本棚の表示、記録の状態制限、既存不具合
適用範囲: backend / frontend / DB（Alembic） / テスト / ドキュメント一式
ステータス: **Todo確定版（未着手）**。開発はこのTodoの承認後に開始する

---

## 0. 前提と着手条件

- [ ] **0-1 未コミット変更の扱いを決める（着手前に必須）**
  作業ツリーに、本Todoの作業ではない未コミット変更が6ファイルある。
  - `backend/app/services/recap_generation_service.py`
  - `backend/app/services/weekly_summary_service.py`
  - `backend/tests/test_recap_generation_service.py`
  - `backend/tests/test_weekly_summary_service.py`
  - `frontend/src/pages/ExamResultPage.tsx`（useToast の位置の変更）
  - `frontend/src/pages/ExamResultPage.test.tsx`
  
  `ExamResultPage` は完了（結果登録）の入口に関わるため、本Todoの着手前に内容を確認し、コミットまたは退避を決める。
  Stop Hook の自動コミット（`auto-commit.sh`）は作業ツリー全体を対象にするため、本Todoと無関係の変更が混ざらないように注意する。
- [ ] **0-2 ブランチ運用**: 日次ブランチ（`dev/YYYY-MM-DD`）の規約に従う。前日ブランチが未マージなら、そのブランチ上で継続する（[CLAUDE.md](../CLAUDE.md) の運用フロー）。
- [ ] **0-3 Alembic の head を確認する**: 新規マイグレーションの `down_revision` に使う。本Todoの調査では、手作業の grep では確定できなかった。`backend/` で `alembic heads` を実行して確定する（実行は仮想環境 `myvenv` 内で行う）。
- [ ] **0-4 フェーズ番号**: 実装フェーズ分割計画書の最終は Phase 41（読書の本棚UI）。本件は **Phase 42** として登録する。

---

## 1. 確定した開発内容（要約）

### 1-1 状態と遷移（全目標種別で共通の骨格）

| 遷移 | 操作の名称（画面） | 備考 |
| --- | --- | --- |
| 下書き → 実行中 | 開始 | 既存 `activate` |
| 実行中 → 一時停止 | 一時停止 | 既存 `pause`。配分は解放 |
| 一時停止 → 実行中 | 再開 | 既存 `resume`。配分の空き検証 |
| 実行中 → 中断 | 中断 | 新設 API（後述 1-3） |
| 実行中 → 完了 | 完了 | 新設 API。資格は全科目の合否登録が前提 |
| 一時停止 → 中断 | 中断 | 新設 |
| 中断 → 実行中 | 再開 | 新設。配分の空き検証、再開日を記録 |
| 完了 → 実行中 | 再開 | 新設。同上 |
| 中断・完了 → アーカイブ | アーカイブ | 既存（論理削除、フラグ） |
| アーカイブ → 元の状態 | 復元 | 既存。状態は変えない |
| 下書き・一時停止・中断・完了 → 物理削除 | 削除 | 統合（1-4） |

**禁止される遷移**（テストで全組み合わせを固定する）:
実行中 → アーカイブ、一時停止 → 完了、完了 ⇄ 中断、中断 → 完了、実行中 → 削除、アーカイブ中の状態変更。

- 「アーカイブ」は状態列ではなくフラグ（`archived_at`）として扱う（既存の R-97 の方針に従う）。
- 下書きからもアーカイブできる（既存の R-61 どおり）。

### 1-2 完了と読了の表示名（種類ごと）

| 種類 | 完了 | 中断 |
| --- | --- | --- |
| 読書 | 読了 | 中断 |
| 資格試験 | 完了 | 中断 |
| 仕事 | 完了 | 中止・打ち切り |

内部の状態は共通（`CLOSED_WITH_RESULT` = 完了／読了、`CLOSED_WITHOUT_RESULT` = 中断／中止）。表示名のみ種類ごとに分ける。

### 1-3 完了・中断の操作（API）

- 完了と中断を別のAPIにする。読書の「読了として記録する」（`POST /books/{id}/complete`）は、完了 API に一本化する。
- 確定時の確認は1回。
- 完了の条件:
  - 資格: 全科目の合否が登録済みであること（未登録の場合は完了ボタンを無効化し、API でも拒否する）。
  - 読書: 書籍が登録済みであること（既存）。
  - 仕事: 案件情報が登録済みであること。`with_result` の指定は廃止し、完了／中止は API 名で区別する。
- 完了時に、読了（完了）レポートを自動生成する（資格の総括レポート・読書の読了レポート）。生成失敗は完了の成否に影響させない（既存方針）。
- 再完了時は新規にレポートを生成し、旧レポートは残す。

### 1-4 削除（統合）

- 対象: 実行中以外のすべての状態（下書き・一時停止・中断・完了）。アーカイブ済みも対象。
- アーカイブ経由の制約と `cascade_study_logs` の選択肢は廃止する。カスケードは常に行う。
- 関連データのうち、評価レポート（仕事）・AI会話ログ・想起記録（読書）・学習実績（資格）・作業ログ（仕事）・日記・コメント・週次まとめ・振り返り関連を含む。
- 同日に他目標のデータが残る日次報告は削除しない（R-63 を維持）。
- 削除前にエクスポートを案内する（強制はしない）。
- 二段階の確認（削除対象の一覧を示す → 目標名の入力、または同等の確認）。
- 物理削除の API は1つにする（既存の `DELETE /goals/{id}` に統合し、`DELETE /goals/{id}/archived` は廃止する）。

### 1-5 再開

- 中断・完了からの再開では、データを引き継ぐ。
- 開始日は変更しない。再開日を別の項目として記録する。
- 資格: 再開日から学習計画（日次ノルマ・締切・基準値）を再計算する。残り期間に対して学習量が多すぎる場合は、警告を表示したうえで再開を許可する。
- 配分の空き検証は、現行の一時停止からの再開と同じ。
- 完了後の合否は読み取り専用。誤りは「完了 → 再開 → 修正 → 完了」で直す。

### 1-6 報告率・連続報告日数（停止期間の除外）

- 一時停止・中断の期間（報告を求めない日）は、報告率の分母から除外する。
- 停止期間は**状態遷移履歴テーブル**（新設）から計算する。
- 履歴の列（既定）: 目標ID、変更前の状態、変更後の状態、変更日時。
- 既存データの移行: 既存の目標には、現在の状態に応じた初期履歴（作成時点の1件）を作成するか、履歴なしとして扱うかを移行テストで確定する（Todo 3-3）。

### 1-7 記録の制限

- 学習・読書・仕事の実績、日記、コメントの登録・修正・削除は、**実行中の目標のみ**可能とする。
- 画面とサーバの両方で制限する（既存の不整合 A の対策）。

### 1-8 レポート

- 仕事の月次報告・半期評価（AI生成）は、完了・中断後も生成可能とする。
- 週次まとめ（自動生成）は、現行どおり（完了・中断後も対象。既存の挙動を維持する）。
- 読了レポート（読書の完了時の生成）は、完了の状態でのみ生成できるようにする（既存の不整合 B）。

### 1-9 一覧・本棚の表示

- 目標一覧の既定表示: 下書き・実行中・一時停止。
- 「すべて表示」: 中断・完了・アーカイブ済みを含むすべて。物理削除済みは表示されない。
- 一覧では、状態バッジ（完了／中断／アーカイブ）で区別する。
- 本棚: 読書の完了・中断のみ（既存の仕様を維持）。資格・仕事は表示しない。
- 本棚の「中断」の見た目と文言は現行のまま（R-97）。

### 1-10 操作の配置

- 完了・中断・一時停止・再開のボタンは、目標詳細の操作欄に集約する。
- 書籍タブの「読了として記録する」は廃止する（完了に一本化）。

### 1-11 その他の確定事項

- 確認は1回（完了・中断）。削除は二段階。
- 週次まとめは現行どおり。
- 既存の中断読書は変更しない。再開機能により利用者が直す。

---

## 2. 既存不具合（本Todoに取り込む。先に直す）

| ID | 内容 | 根拠 | 対応 |
| --- | --- | --- | --- |
| **A** | 日次の実績・読書・仕事の実績、日記、コメントの登録が、目標の状態を検査していない（API経由で中断・完了・一時停止の目標に登録できる） | [record_service.py:580-625](../backend/app/services/record_service.py#L580-L625)、[records.py:196-260](../backend/app/api/records.py#L196-L260)、[records.py:394-420](../backend/app/api/records.py#L394-L420) | サービス層で実行中のみに制限。画面の出し分けと一致させる |
| **B** | 読了レポート（総括レポート）の生成に状態チェックがない（中断の読書でも生成可） | [retrospective_service.py:139-166](../backend/app/services/retrospective_service.py#L139-L166)、[closure.py:78-88](../backend/app/api/closure.py#L78-L88) | 完了の状態でのみ生成可に制限（読書）。資格の総括も同じ方針で確認 |
| **C** | 仕事の完全削除は、評価レポートがあると失敗する（RESTRICT）。カスケード処理が評価レポートを扱っていない | [work.py:89-91](../backend/app/models/work.py#L89-L91)、[goal_service.py:241-328](../backend/app/services/goal_service.py#L241-L328) | カスケードに評価レポートを含める（1-4） |
| **D** | 一時停止の期間が報告率の分母に入る（停止中の日が未報告として計上される） | [metrics_service.py:75-163](../backend/app/services/metrics_service.py#L75-L163)、[dashboard.py:57](../backend/app/schemas/dashboard.py#L57) | 停止期間を分母から除外（1-6） |
| **E** | 読書目標の「読了」は、資格・仕事と異なる入口（`POST /books/{id}/complete`）を持つ | [book_service.py:116-129](../backend/app/services/book_service.py#L116-L129) | 完了APIに統合（1-3） |

**開発中に見つけた不具合は、このTodoに追記して取り込む**（追記欄は 8 章）。

---

## 3. 影響範囲（確定）

### 3-1 backend（ロジック）

| 対象 | 箇所 | 変更の種類 |
| --- | --- | --- |
| 状態・遷移 | [goal_service.py](../backend/app/services/goal_service.py)（`close_goal` 447-497、`pause_goal` 417、`resume_goal` 426-444、`activate_goal` 371-414、`archive_goal` 218、`unarchive_goal` 232、`delete_goal` 207、`delete_archived_goal` 331-368、`_cascade_delete_activity_logs` 241-328、`ensure_goal_editable` 109、`ensure_goal_active` 115） | 改修・統合 |
| 読了 | [book_service.py](../backend/app/services/book_service.py) `complete_book` 116-129 | 完了APIに統合 |
| 状態値 | [enums.py:6-11](../backend/app/constants/enums.py#L6-L11)（値は増やさない。`Enum(native_enum=False)`） | 変更なし（確認のみ） |
| モデル | [models/goal.py:41-47](../backend/app/models/goal.py#L41-L47)（再開日の列を追加） | 追加 |
| 履歴 | 状態遷移履歴テーブル（新設） | 新規 |
| 報告率 | [metrics_service.py](../backend/app/services/metrics_service.py) `compute_report_rate` 93-112、`compute_recent_report_rate` 114-140、`compute_consecutive_report_days` 142-182 | 停止期間の除外 |
| 起点の参照（確認のみ） | `goal.start_date` を参照する箇所: [reading_feedback_service.py:104](../backend/app/services/reading_feedback_service.py#L104)、[work_feedback_service.py:101](../backend/app/services/work_feedback_service.py#L101)、[recap_generation_service.py:56](../backend/app/services/recap_generation_service.py#L56)、[retrospective_service.py:111-129](../backend/app/services/retrospective_service.py#L111-L129)、[ai_context_service.py:952](../backend/app/services/ai_context_service.py#L952) | 再開日の扱いを確認 |
| 記録の制限 | [record_service.py](../backend/app/services/record_service.py) `register_progress` 580-625、`finalize_*` 628-690、`add_comment` 701、`update_comment` 712、`delete_comment` 718、`_upsert_diary_entry` 389-412 | 実行中のみに制限（不具合A） |
| 完了レポート | [retrospective_service.py](../backend/app/services/retrospective_service.py) `generate_retrospective` 139-166 | 状態の制限（不具合B） |
| 仕事の評価 | [work_member_service.py](../backend/app/services/work_member_service.py) 107、[work.py:89-91](../backend/app/models/work.py#L89-L91) | カスケード対応（不具合C） |
| 資格の計画 | [quota_service.py](../backend/app/services/quota_service.py)、[goal_service.py:76-89](../backend/app/services/goal_service.py#L76-L89)（`quota_base_date`）、[baseline](../backend/app/services/goal_service.py#L64-L107)（`record_baseline_for_material`） | 再開時の再計算 |
| 表示・集計の対象（確認のみ） | [ai_context_service.py:80-144](../backend/app/services/ai_context_service.py#L80-L144)、[resource_service.py:230](../backend/app/services/resource_service.py#L230)、[record_service.py:769](../backend/app/services/record_service.py#L769)、[allocation_service.py:23](../backend/app/services/allocation_service.py#L23)、[dashboard.py:236](../backend/app/api/dashboard.py#L236) | 変更なし（ACTIVE判定は正しい） |
| 週次まとめ・月次報告（確認のみ） | [weekly_summary_service.py:177-206](../backend/app/services/weekly_summary_service.py#L177-L206)、[work_report_service.py:226](../backend/app/services/work_report_service.py#L226) | 変更なし（1-8） |
| 書き出し | [export_service.py:166-167, 773-777](../backend/app/services/export_service.py#L166-L777)（`closed_at` の期間表示）、[backup_service.py](../backend/app/services/backup_service.py) | 再開日の表示・バックアップの互換 |

### 3-2 backend（API・スキーマ）

| 対象 | 箇所 | 変更の種類 |
| --- | --- | --- |
| 目標の操作 | [api/goals.py](../backend/app/api/goals.py)：`DELETE /goals/{id}` 179、`DELETE /goals/{id}/archived` 202、`POST activate` 211、`POST pause` 219、`POST resume` 227、`POST close` 235 | 削除の統合、`close` の分割（完了・中断）、`archived` の削除 |
| 読了 | [api/books.py:49](../backend/app/api/books.py#L49)：`POST /books/{id}/complete` | 完了APIに統合 |
| 応答 | `GoalRead`（[api/goals.py:67-69](../backend/app/api/goals.py#L67-L69)）、[api/books.py:64-66](../backend/app/api/books.py#L64-L66) | 再開日・履歴の項目を追加 |
| スキーマ | [schemas/goal.py:32-43](../backend/app/schemas/goal.py#L32-L43)（`GoalCloseRequest` の `with_result`、`GoalDeleteArchivedRequest` の `cascade_study_logs`）、`GoalRead` 53-57 | 廃止・追加 |
| 例外 | [services/exceptions.py](../backend/app/services/exceptions.py)（`CloseConfirmationRequiredError` 97-113） | 資格の完了条件に合わせて見直す |
| エラーコード | `ERROR_CODES` の対応（[api_errors](../backend/tests/test_api_errors.py) 41、69） | 新しいエラーの追加と、旧コードの見直し |

### 3-3 DB（Alembic）

- [ ] 新規マイグレーション: 再開日の列、状態遷移履歴テーブル。`down_revision` は 0-3 で確定した head。
- [ ] 既存データの移行テスト（[CODING_RULES.md](CODING_RULES.md) の「DBマイグレーションのテスト」に従う）。
  - 既存の中断・完了の目標が、状態を保ったまま読める
  - 既存の目標の履歴の初期値（1-6）
- [ ] `status` 列は値を増やさないため、制約の変更は不要の見込み（マイグレーションの実装時に SQLAlchemy の出力で確認する）。

### 3-4 frontend

| 対象 | 箇所 | 変更の種類 |
| --- | --- | --- |
| 状態判定 | [goalStatus.ts:6-30](../frontend/src/features/goal/goalStatus.ts#L6-L30) | 再定義（既定表示・すべて表示・種類ごとの表示名） |
| 目標一覧 | [GoalsListPage.tsx:74-109](../frontend/src/pages/GoalsListPage.tsx#L74-L109)（カード）、[158-159](../frontend/src/pages/GoalsListPage.tsx#L158-L159)（既定の絞り込み）、`GoalCard` の「結果登録」「総括・エクスポート」「アーカイブ」「完全削除」 | 表示・操作の再設計 |
| 目標詳細 | [GoalDetailPage.tsx:116-212](../frontend/src/pages/GoalDetailPage.tsx#L116-L212)（`GoalStatusActions`）、[231-232](../frontend/src/pages/GoalDetailPage.tsx#L231-L232) | 完了・中断・一時停止・再開のボタン集約 |
| クローズ確認 | [closeGoalConfirm.ts:40-67](../frontend/src/features/goal/closeGoalConfirm.ts#L40-L67)、[CloseGoalModal.tsx](../frontend/src/features/goal/CloseGoalModal.tsx) | 完了・中断の確認に分割。確認1回 |
| 書籍タブ | [BookTab.tsx:233-242](../frontend/src/features/goal/BookTab.tsx#L233-L242)（`CompleteBookModal` を含む） | 読了ボタンの廃止（完了に一本化） |
| 資格の結果登録 | [ExamResultPage.tsx:128](../frontend/src/pages/ExamResultPage.tsx#L128)（クローズ済みの判定）、**未コミット変更を含む（0-1）** | 完了ボタンの出し分けの参照先 |
| 削除 | `DeleteArchivedGoalModal`、[api/goals.ts:58-74](../frontend/src/api/goals.ts#L58-L74)（`deleteGoal`・`deleteArchivedGoal`） | 二段階確認、統合 |
| 再開時の警告 | 資格の再開（新規の警告表示） | 新規 |
| 本棚 | [BookshelfPage.tsx](../frontend/src/pages/BookshelfPage.tsx)、[bookStatusVariant.ts](../frontend/src/features/bookshelf/bookStatusVariant.ts)、[groupCompletedBooks.ts](../frontend/src/features/bookshelf/groupCompletedBooks.ts)、[BookInfoTab.tsx:39-40](../frontend/src/features/bookshelf/BookInfoTab.tsx#L39-L40) | 表示名の対応（読書のみ。現行を維持） |
| 記録の対象（確認のみ） | [resolveVisibleReportTargets.ts:73](../frontend/src/features/record/resolveVisibleReportTargets.ts#L73)、[useDailyReportActions.ts:196](../frontend/src/features/record/useDailyReportActions.ts#L196)、[useDailyReportDraft.ts:53](../frontend/src/features/record/useDailyReportDraft.ts#L53)、[useGoalReportTabs.ts:27](../frontend/src/features/record/useGoalReportTabs.ts#L27) | 変更なし（ACTIVE判定は正しい） |
| 分析 | [selectableAnalyticsGoals.ts:23-33](../frontend/src/features/analytics/selectableAnalyticsGoals.ts#L23-L33) | 既定の表示ルールを一覧と揃えるか確認 |
| API クライアント | [api/goals.ts](../frontend/src/api/goals.ts) 58-90、170-172、185、202、230 | 関数の追加・削除 |
| 型 | `frontend/src/types/api.d.ts` | **`openapi-typescript` で再生成**（手書きしない） |

### 3-5 文言（ロケール）

[ja.json](../frontend/src/locales/ja.json) の対象（行番号は現時点）:
- 156-158: 状態ラベル → 種類ごとの表示名（1-2）
- 163-168: アーカイブ・「すべて表示」の文言
- 269-284: 読み取り専用の注記、確認文（`readingBody` など）、操作の名称
- 474-486: 書籍タブの読了ボタン（廃止）
- 492-502、522: 本棚の見出し・バッジ・注記（読書のみ、現行を維持）
- 1126、1139-1147、1169、1175-1177: 操作ヘルプ（削除の説明、クローズの説明を書き換える）
- 新規: 再開時の警告、削除の二段階確認、再開日の表示

### 3-6 テスト（影響）

**backend**（旧挙動を固定しているため、期待値を書き換える）
- [test_goal_service.py](../backend/tests/test_goal_service.py): 289-306（アーカイブ経由の削除、cascade選択）、319、370、403、443
- [test_api_goals.py](../backend/tests/test_api_goals.py): 86（非下書きの削除）、203-283（クローズの確認）、719-779（アーカイブ）、790-940（削除）、481-495（一時停止）
- [test_api_books.py](../backend/tests/test_api_books.py): 246-306（読了・中断）、391（一時停止・再開）
- [test_api_work.py](../backend/tests/test_api_work.py): 201-260（仕事のクローズ）、332
- [test_api_closure.py](../backend/tests/test_api_closure.py): 96、152
- [test_phase3_service_guards.py](../backend/tests/test_phase3_service_guards.py): 77
- [test_api_errors.py](../backend/tests/test_api_errors.py): 41、69（確認要求のエラーコード）
- [test_work_member_service.py](../backend/tests/test_work_member_service.py)、[test_api_work_members.py](../backend/tests/test_api_work_members.py): 評価レポートのカスケード（C）
- [test_api_records.py](../backend/tests/test_api_records.py)、[test_record_service.py](../backend/tests/test_record_service.py): 不具合A の対策
- [test_metrics_service.py](../backend/tests/test_metrics_service.py): 報告率（D）
- 状態遷移の全組み合わせ: 新規（5章）

**frontend**
- [closeGoalConfirm.test.ts](../frontend/src/features/goal/closeGoalConfirm.test.ts)、[CloseGoalModal.test.tsx](../frontend/src/features/goal/CloseGoalModal.test.tsx)、[goalStatus.test.ts](../frontend/src/features/goal/goalStatus.test.ts)、[DeleteArchivedGoalModal.test.tsx](../frontend/src/features/goal/DeleteArchivedGoalModal.test.tsx)
- [GoalsListPage.test.tsx](../frontend/src/pages/GoalsListPage.test.tsx)、[GoalDetailPage.test.tsx](../frontend/src/pages/GoalDetailPage.test.tsx)、[ExamResultPage.test.tsx](../frontend/src/pages/ExamResultPage.test.tsx)、[BookDetailPage.test.tsx](../frontend/src/pages/BookDetailPage.test.tsx)
- [BookshelfPage.test.tsx](../frontend/src/pages/BookshelfPage.test.tsx)、[BookInfoTab.test.tsx](../frontend/src/features/bookshelf/BookInfoTab.test.tsx)、[BookSpineCard.test.tsx](../frontend/src/features/bookshelf/BookSpineCard.test.tsx)、[groupCompletedBooks.test.ts](../frontend/src/features/bookshelf/groupCompletedBooks.test.ts)
- [test/fixtures.ts](../frontend/src/test/fixtures.ts)（共通データ）

### 3-7 ドキュメント

| 文書 | 更新箇所 |
| --- | --- |
| 要件定義書 | R-44・R-45・R-46、R-61〜R-63、R-71、R-97（改訂記録の行を追加） |
| 仕様書 | 4章（画面）、5.1・5.2（導線）、6.2（操作）、6.15（SC-02の既定表示）、7.1（遷移表）、7.1.1（アーカイブ・削除）、SC-18（本棚の記述） |
| データ構造編 | 4.2（カスケード削除）、5.3（状態の意味）、6.2（API一覧）、再開日・履歴テーブル |
| ロジック・プロンプト編 | 報告率・連続報告日数（停止期間の除外）、資格の再計画（再開時） |
| 実装フェーズ分割計画書 | Phase 42 を追加 |
| CODING_RULES.md | 変更は原則なし（新しい規約が必要になった場合のみ） |
| ヘルプ文言（ja.json） | 1139-1147、1169、1175-1177 |
| リリースノート | `docs/release-notes/` に新規作成（利用者に見える変更） |
| README.md | 操作の概要に記述がある場合のみ |

---

## 4. 実装フェーズ（Todo）

### P0 準備（デグレ防止の土台）
- [ ] 0-1〜0-4 を完了する
- [ ] **ベースライン記録**: backend の `pytest` 全件の結果（件数・失敗0）、カバレッジの現状値、frontend の `vitest` 全件の結果を記録する（後で比べるため。記録先: 本Todo末尾の「8. 作業ログ」）
- [ ] 既存の本番データ相当のDBを用意し、移行前後で読めることを確認するための手順を準備する（[OPERATIONS.md](OPERATIONS.md) の既存手順に従う）

### P1 既存不具合 A〜E（先に直す）
- [ ] A: 記録系（実績・読書・仕事・日記・コメント）の状態制限を、サービス層に追加する
  - テスト: 中断・完了・一時停止の目標への登録・修正・削除が `InvalidStateTransitionError` になる（記録の種類ごとに全パターン）
  - テスト: 実行中の目標は従来どおり登録できる
  - 横展開: `record_service.py` の全ての書き込み関数、`records.py` の全ての書き込みエンドポイント
- [ ] B: 読了レポートの状態制限（完了の状態でのみ生成可）
  - テスト: 中断・実行中の読書で生成が拒否される
  - 資格の総括レポートも同じ方針で確認し、必要なら揃える
- [ ] C: 仕事の評価レポートを含むカスケード削除（P3 の削除統合と同時に行う）
  - テスト: 評価レポートがある仕事目標を削除できる（子データもすべて消える）
- [ ] D: 報告率の分母の停止期間除外（履歴テーブルは P2 で作るため、D は P2 の後に行う）
- [ ] E: 読書の完了を完了APIに統合（P3 で行う）

### P2 DB・履歴（マイグレーション）
- [ ] 状態遷移履歴テーブルの新設（モデル・マイグレーション・`Base.metadata` への登録）
- [ ] 目標の再開日の列の追加（nullable）
- [ ] 既存データの移行テスト（3-3）
- [ ] 目標の作成・状態変更のたびに履歴を記録する仕組み（サービス層の共通関数に集約し、各遷移関数から呼ぶ。DRY の原則）
- [ ] テスト: 履歴の記録が、遷移の失敗時には残らないこと（トランザクションの一貫性）

### P3 backend 状態遷移・削除・計画
- [ ] 遷移表の実装（1-1）。遷移は1つのテーブル（許可された遷移の一覧）で定義し、各関数はそれを参照する（ハードコードを避ける）
- [ ] 完了・中断のAPI（1-3）。`close_goal` の分割、`complete_book` の統合
- [ ] 資格の完了条件（全科目の合否登録）
- [ ] 仕事の完了・中止（`with_result` の廃止）
- [ ] 中断・完了からの再開（1-5）。配分の空き検証、再開日の記録、資格の計画の再計算
- [ ] 資格の再開時の警告（学習量が多すぎる場合の判定値は `app_setting` に外部化する。ソースに閾値を直接書かない）
- [ ] 削除の統合（1-4）。`delete_goal` を実行中以外すべてに対応させ、アーカイブ経由の制約と cascade 選択を廃止する
- [ ] カスケードの対象の網羅（評価レポート・AI会話ログを含む。[goal.py](../backend/app/models/goal.py)・各モデルの `ondelete` を確認して漏れを防ぐ）
- [ ] 報告率の停止期間除外（D）
- [ ] テスト: 状態遷移の全組み合わせ（5章）

### P4 API・スキーマ・型
- [ ] エンドポイントの変更（3-2）
- [ ] スキーマ（`GoalRead` の再開日、履歴の応答）
- [ ] エラーコードの見直し（`CLOSE_CONFIRMATION_REQUIRED` の扱い。[exceptions.py](../backend/app/services/exceptions.py)）
- [ ] テスト: API の契約（レスポンスの項目・ステータスコード）
- [ ] `openapi-typescript` で `frontend/src/types/api.d.ts` を再生成する（手書きしない）

### P5 frontend
- [ ] `goalStatus.ts` の再定義（表示名・既定表示・すべて表示）
- [ ] 目標一覧（既定の絞り込み、「すべて表示」、状態バッジ）
- [ ] 目標詳細の操作欄（完了・中断・一時停止・再開）
- [ ] 完了・中断の確認モーダル（確認1回）
- [ ] 書籍タブの読了ボタンの廃止
- [ ] 削除の二段階確認
- [ ] 再開時の警告表示（資格）
- [ ] 本棚（読書のみ。表示名の対応を確認）
- [ ] 分析の対象（既定の表示ルールを揃える）
- [ ] 文言の追加・変更（ja.json のみ。コンポーネントに直接書かない）
- [ ] **ExamResultPage の未コミット変更（0-1）を反映したうえで着手**
- [ ] テスト: 3-6 の旧テストを新仕様に合わせて更新し、新しい分岐を追加する

### P6 テストの整合性
- [ ] 3-6 のテストの旧文言・旧挙動をすべて新仕様に置き換える（`grep` で旧文言の残留を確認）
- [ ] 新しい分岐のテストを追加し、例外処理を除きカバレッジ100%を目指す（[CODING_RULES.md](CODING_RULES.md) のテストカバレッジ）
- [ ] ロケールの検証（バックエンドのエラーコードに対応する画面文言があること。既存のテストを拡張）

### P7 横展開・デグレ確認（チェックリスト）
- [ ] `grep` で旧状態の参照が残っていないことを確認する: `CLOSED_WITH_RESULT`、`CLOSED_WITHOUT_RESULT`、`with_result`、`cascade_study_logs`、`archived_at`、`deleteArchivedGoal`、`completeBook`、`closeGoal`、`読了として記録する`、`クローズ`、`完全削除`
- [ ] `goal.start_date` と `closed_at` の参照箇所（3-1 の一覧）を一つずつ確認し、再開日の扱いが正しいことを確認する
- [ ] ACTIVE 判定の箇所（3-1・3-4 の「確認のみ」）が変わらず正しいことを確認する
- [ ] DRY: 状態判定・遷移判定は1か所に集約されているか（重複した判定がないか）
- [ ] ゼロハードコーディング: 画面文言は ja.json、閾値は `app_setting` に入っているか
- [ ] 命名規則・コメント規約（[CODING_RULES.md](CODING_RULES.md)）
- [ ] N+1: 一覧の取得（`list_goals` の `selectinload`）に、履歴・再開日の追加で N+1 が入っていないか
- [ ] フロント: 目標一覧・詳細の再描画が増えていないか、不要な Provider の watch がないか

### P8 ドキュメント（3-7）
- [ ] 要件定義書・仕様書・データ構造編・ロジック・プロンプト編の更新（改訂記録の行を必ず追加）
- [ ] 実装フェーズ分割計画書に Phase 42 を追加（完了条件を明記）
- [ ] ヘルプ文言の更新
- [ ] リリースノートの作成
- [ ] 各文書の相互参照（[CLAUDE.md](../CLAUDE.md) の「ドキュメント最新化」の一覧）が古いままでないか確認

### P9 最終検証
- [ ] `ruff check .` → `pytest`（全件）→ `docker build .`（[CLAUDE.md](../CLAUDE.md) の「デプロイチェック」）
- [ ] frontend の型チェック・テスト・カバレッジ
- [ ] 旧DBのバックアップから移行し、既存の中断・完了の目標が読めること（P0 の手順）
- [ ] 実環境スモーク（`run` スキル。資格・読書・仕事それぞれで「開始→一時停止→再開→完了→削除」の一連を確認）
- [ ] `backend/release.bat` の手順に従い、リリース前スモークを通す（[OPERATIONS.md](OPERATIONS.md) 7.4）

---

## 5. デグレ防止の施策

1. **状態遷移の全組み合わせテスト（必須）**: 状態（下書き・実行中・一時停止・中断・完了）× 操作（開始・一時停止・再開・中断・完了・アーカイブ・復元・削除）× 種類（資格・読書・仕事）の表形式テストを作る。許可された遷移だけが成功し、それ以外はすべて拒否されることを固定する。
2. **遷移表の単一の定義**: 許可された遷移を1つの定義に集約し、サービス・API・画面の判定は同じ定義から引く（不整合を防ぐ）。
3. **特性テスト（characterization）**: 変更前に、報告率・連続報告日数・配分の空き検証の現行の値を固定するテストを書いてから変更する（D の修正で意図しない変化が出ないようにする）。
4. **移行テスト**: 既存データに対して、新しいマイグレーションで読めることを確認する（[CODING_RULES.md](CODING_RULES.md)）。
5. **API契約の確認**: 変更前後の OpenAPI の差分を確認し、意図しない項目の削除・型の変更がないことを見る。
6. **横展開の確認を1つのチェックリストにする**（P7）。
7. **段階的に出す**: 不具合 A〜E を先に出荷可能な単位で直し、新機能はその後に出す（先行修正を独立してリリースできる形にする）。
8. **旧テストの書き換えは理由を残す**: 期待値を変える場合は、テストのコメントに「仕様変更（改訂記録の番号）」を書く。

---

## 6. 受け入れ条件（完了の定義）

- [ ] 1章の遷移がすべて動作し、禁止された遷移はすべて拒否される（5-1 のテストが通る）
- [ ] 既存不具合 A〜E が再現しない（テストで固定）
- [ ] 目標一覧の既定表示と「すべて表示」が仕様どおり（種類ごとの表示名を含む）
- [ ] 本棚は読書の完了・中断のみを表示し、現行の見た目を維持する
- [ ] 削除は実行中以外から直接できて、二段階の確認があり、カスケードで関連データがすべて消える（同日の他目標のデータは残る）
- [ ] 再開時にデータが引き継がれ、資格の計画が再計算され、必要な場合は警告が出る
- [ ] 報告率が停止期間を除外して計算される
- [ ] backend・frontend のテストがすべて通り、カバレッジの目標（100%）に対する未達の箇所が説明できる
- [ ] 要件定義書・仕様書・データ構造編・ロジック・プロンプト編・実装フェーズ分割計画書・ヘルプ・リリースノートが更新されている
- [ ] 既存DBから移行しても既存データが読める

---

## 7. 未決事項（既定値で進める。異論があれば変更する）

| 項目 | 既定値 |
| --- | --- |
| 履歴の初期値（既存の目標） | 作成時点の1件のみを作る（移行テストで確認） |
| 再開日の複数回の扱い | 再開のたびに更新し、停止期間は履歴から計算する |
| 資格の警告の判定値 | `app_setting` に外部化し、初期値は既存の設定に合わせる |
| 削除の二段階確認の方式 | 削除対象の一覧を示し、目標名の入力で確定する |
| 完了の無効化の表示 | 結果が揃っていないことを理由文で示す |

---

## 8. 作業ログ（開発中に記録する）

| 日付 | 内容 | 結果 |
| --- | --- | --- |
| 2026-10-04 | 本Todo作成（調査・確定のみ。開発なし） | — |
| | ベースライン（backend / frontend のテスト件数・カバレッジ） | 未記録 |
| | 開発中に見つけた不具合（ここに追記して取り込む） | — |

---

## 付録: 調査の根拠（主な箇所）

- 状態値の定義: [backend/app/constants/enums.py](../backend/app/constants/enums.py)
- 遷移の実装: [backend/app/services/goal_service.py](../backend/app/services/goal_service.py)、[backend/app/services/book_service.py](../backend/app/services/book_service.py)
- 削除・カスケード: [backend/app/services/goal_service.py](../backend/app/services/goal_service.py) 207-368
- 記録の登録（不具合A）: [backend/app/services/record_service.py](../backend/app/services/record_service.py) 580-625
- 読了レポート（不具合B）: [backend/app/services/retrospective_service.py](../backend/app/services/retrospective_service.py) 139-166
- 評価レポート（不具合C）: [backend/app/models/work.py](../backend/app/models/work.py) 89-91
- 報告率（不具合D）: [backend/app/services/metrics_service.py](../backend/app/services/metrics_service.py) 93-182
- 現行の要件・仕様: [要件定義書](要件定義書_ミチナリ_v1.1.md)、[仕様書](仕様書_ミチナリ_v1.1.md)、[データ構造編](設計書_データ構造編_ミチナリ_v1.1.md)
