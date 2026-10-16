### Phase 20：仕事データモデル拡張

| 項目 | 内容 |
| --- | --- |
| 目的 | 仕事目標のためのDBスキーマを追加する |
| 投入文書 | CLAUDE.md、運用設計ルール、設計書 データ構造編（Phase19で反映した仕事関連節） |

**実装対象**

- [x] `GoalCategory` enum への `WORK` 追加（backend/app/constants/enums.py）。あわせて`AiPurpose`／`ConversationScope`に`DAILY_FEEDBACK_WORK`／`GOAL_RETROSPECTIVE_WORK_MONTHLY`／`GOAL_RETROSPECTIVE_WORK_SEMIANNUAL`、`RetrospectivePeriodType`（MONTHLY/SEMI_ANNUAL）を追加
- [x] `work_assignment` テーブルの新設（`goal_id` にUNIQUE制約）→ `backend/app/models/work.py`
- [x] `work_log` テーブルの新設（`work_assignment_id` と `daily_record_id` の組み合わせにUNIQUE制約）→ `backend/app/models/record.py`
- [x] `goal_retrospective` への `period_type`／`period_key`／`target_goal_text`／`business_summary`／`achievement_score`／`achievement_reflection`／`next_goal_text`／`report_notes`／`edited_at` 列追加のマイグレーション（2026-09-04の設計改訂、データ構造編1.1（改12））。既存行は全てNULLのまま遡及設定不要。デフォルト値なし・NULL許容で追加するのみ
- [x] 全SQLAlchemyモデルへの反映（`models/__init__.py`にWorkAssignment/WorkLog登録）
- [x] `prompt_template` への初期データ追加（`DAILY_FEEDBACK_WORK`、`GOAL_RETROSPECTIVE_WORK_MONTHLY`、`GOAL_RETROSPECTIVE_WORK_SEMIANNUAL`）→ `backend/app/init/prompt_texts.py`（ロジック・プロンプト編17.8〜17.10から一字一句転記）、`backend/app/init/seed_data.py`
- [x] `app_setting` への初期データ追加（`ai.assistant_uid.daily_feedback_work`、`ai.assistant_uid.goal_retrospective_work_monthly`、`ai.assistant_uid.goal_retrospective_work_semiannual`、`ai.work_recent_log_days`）→ 未選定のアシスタントUIDは空文字で初期投入（Phase22で疎通確認のうえ補う）

**完了条件**

- [x] `alembic upgrade head` でスキーマが構築される
- [x] `work_assignment.goal_id` のUNIQUE制約により1目標1案件が保証される
- [x] `work_log`が`(work_assignment_id, daily_record_id)`単位で一意登録される
- [x] `goal_retrospective`に`period_type`／`period_key`を指定した複数レコード（同一goal・異なるperiod_key）が保存できる。ただし同一goal・同一period_type・同一period_keyでは常に1行のみ（サービス層でupsertとして扱う。データ構造編5.4「WORKでは常に一意」）
- [x] 初期データ投入が重複しない（再起動時も同様）
- [x] `material`／`exam_subject`／`book`／`reading_log`等の既存テーブルに変更がない

**注意点**

- マイグレーションSQLを目視レビューすること（Phase14と同じ注意点）
- プロンプトテンプレートの初期文面はPhase19で確定した文面から転記し、要約・改変をしないこと
- `goal_retrospective`の一意制約変更（`(goal_id, period_type, period_key, is_anonymized)`）が既存のEXAM/READING運用（period_type・period_key共にNULL）と両立することをテストで確認すること

**Phase20完了（2026-09-04）。バックエンド全739テスト・カバレッジ100%・ruff検査通過を確認済み。`alembic upgrade head`→`downgrade -1`→`upgrade head`のサイクルも確認済み。新設マイグレーション`e1f4a9c3b6d8`（`work_assignment`／`work_log`テーブル作成、`goal_retrospective`への9列追加とUNIQUE制約`(goal_id, period_type, period_key, is_anonymized)`追加）はSQL目視レビュー済み、既存データがある状態での列追加も`test_goal_retrospective_migration_preserves_existing_exam_rows_with_data`で検証済み。既存のEXAM/READING関連モデル・マイグレーション・テストは無改修。次はPhase 21（仕事目標・記録API）から着手する。**

---

