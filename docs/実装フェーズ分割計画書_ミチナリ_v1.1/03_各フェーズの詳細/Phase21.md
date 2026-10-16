### Phase 21：仕事目標・記録API

| 項目 | 内容 |
| --- | --- |
| 目的 | 仕事目標のCRUDと日次記録APIの種別分岐を実装する（AI連携を除く） |
| 投入文書 | CLAUDE.md、運用設計ルール、仕様書・設計書 データ構造編（Phase19で反映した仕事関連節） |

**実装対象**

- [x] 目標作成・更新APIの `category=WORK` 対応（`exam_subject`／`material`／`load_profile`関連の入力・バリデーションを要求しない。読書と同じ分岐パターンを踏襲）
- [x] `work_assignment` のCRUD → `work_service.py`（新設）。作成・更新ともに目標配下のネストパス`POST`／`PATCH /goals/{id}/work-assignment`（`api/goals.py`。書籍と異なり独立した`/work-assignments/{id}`は設けない）
- [x] 日次記録APIの分岐：`category=WORK`の目標に対しては`study_log`ではなく`work_log`を受け付ける（`daily_record`本体・確定ロジックは無改変で共用）→ `record_service.py`に`WorkLogItem`・`_apply_work_logs`を追加、`register_progress`/`finalize_record`に`work_items`引数を追加（デフォルトNoneで後方互換）
- [x] 経過日数・直近記録日・連続記録日数・直近の月次報告有無の実装 → `work_service.get_work_assignment_progress`。書籍と同じく`GET /goals/{id}/plan`は実装せず`WorkAssignmentRead`への埋め込み方式とする
- [x] 目標クローズ処理：`POST /goals/{id}/close`にbody `with_result`（真偽値、既定false）を追加し、WORKに限り`true`指定で`CLOSED_WITH_RESULT`へ遷移できるようにする（EXAM/READINGでは`with_result`指定自体を拒否）
- [x] バリデーション：`work_log.body` 必須（数値項目を持たないため他の数値バリデーションなし）
- [x] `resource_ratio` バリデーションから仕事目標を除外する（読書と同じ分岐パターン）

**完了条件**

- [x] `category=EXAM`／`category=READING`の既存エンドポイントの挙動に変化がない（既存テストが無改修で全て通過）
- [x] `category=WORK`の目標で科目・教材関連APIを呼んでも不整合が起きない（対象外として扱われる）
- [x] 1目標に2件目の`work_assignment`を追加しようとすると拒否される（`WORK_ASSIGNMENT_ALREADY_EXISTS`）
- [x] `work_log`が`daily_record`×`work_assignment`単位で一意登録される
- [x] 仕事目標が`resource_ratio`の合計計算に算入されない
- [x] `POST /goals/{id}/close`に`with_result=true`を指定するとWORK目標が`CLOSED_WITH_RESULT`へ遷移し、EXAM/READINGでは同指定がVALIDATION_ERRORで拒否される

**Phase15で追加対応した既存機能への回帰防止（読書のケース）と同様の観点を確認すること**：仕事目標の作成・進行が可能になったことで、既存の資格試験用・読書用AI機能が仕事目標のデータを誤って取り込まないか確認する（本フェーズはAI連携を含まないため実害は生じないはずだが、`list_active_exam_goals`がWORKを含めていないことをテストで確認する）。

**注意点**

- サービス層でHTTP例外を出さない（ドメイン例外→API層変換の既存原則を踏襲）
- AI連携は本フェーズに含めない。報告確定は`chat_message`が空の状態で成立させる

**Phase21完了（2026-09-05）。**`work_service.py`（新設）・`api/work.py`（新設、`serialize_work_assignment`）・`schemas/work.py`（新設）を追加し、`goal_service.py`（`update_goal`・`activate_goal`・`close_goal`への`with_result`追加・`_cascade_delete_activity_logs`・`delete_archived_goal`）・`record_service.py`（`WorkLogItem`・`_apply_work_logs`・`register_progress`/`finalize_record`への`work_items`引数）・`api/goals.py`（`POST`/`PATCH /goals/{id}/work-assignment`、`close_goal`エンドポイント）・`api/records.py`・`schemas/goal.py`・`schemas/record.py`・`api/errors.py`・`exceptions.py`を拡張した。設計どおり、案件情報の作成・更新は書籍と異なり目標配下のネストパスに統一し、独立した`/work-assignments/{id}`は設けていない。バックエンド全789テスト・カバレッジ100%・ruff検査通過を確認済み（既存の資格試験・読書関連コードは新しいカテゴリ分岐の追加以外無改修）。次はPhase 22（仕事AI連携）から着手する。

---

