### Phase 14：読書データモデル拡張

| 項目 | 内容 |
| --- | --- |
| 目的 | 読書目標のためのDBスキーマを追加する |
| 投入文書 | CLAUDE.md、運用設計ルール、設計書 データ構造編（Phase13で反映した読書関連節） |

**実装対象**

- [x] `GoalCategory` enum の定義（backend/app/constants/enums.py）。あわせて`AiPurpose`／`ConversationScope`に`DAILY_FEEDBACK_READING`／`GOAL_RETROSPECTIVE_READING`を追加
- [x] `goal.category` 列のマイグレーション追加（既定値 `EXAM`。既存レコードは全件 `EXAM` として遡及設定する）→ `alembic/versions/b7a1021fff73_reading_goal_category.py`。server_defaultを残す方式（2b8b04b91e47と同じ理由）で実装し、legacy DB migration test（test_bootstrap.py）で遡及設定を実地検証済み
- [x] `book` テーブルの新設（`goal_id` にUNIQUE制約）→ `backend/app/models/book.py`
- [x] `reading_log` テーブルの新設（`daily_record_id` と `book_id` の組み合わせにUNIQUE制約）→ `backend/app/models/record.py`
- [x] 全SQLAlchemyモデルへの反映（`goal.py`にcategory列・book関係、`models/__init__.py`にBook/ReadingLog登録）
- [x] `prompt_template` への初期データ追加（`DAILY_FEEDBACK_READING`、`GOAL_RETROSPECTIVE_READING`）→ `backend/app/init/prompt_texts.py`（ロジック・プロンプト編17.6/17.7から一字一句転記）、`backend/app/init/seed_data.py`
- [x] `app_setting` への初期データ追加（`ai.assistant_uid.daily_feedback_reading`、`ai.assistant_uid.goal_retrospective_reading`、`ai.reading_recall_recent_days`）→ 未選定のアシスタントUIDは空文字で初期投入（Phase16で疎通確認のうえ設定画面から補う）

**完了条件**

- [x] `alembic upgrade head` でスキーマが構築される
- [x] 既存の `goal` レコードが `category='EXAM'` として問題なく引き継がれる（test_migration.py、test_bootstrap.pyのlegacy DB移行テストで確認）
- [x] `book.goal_id` のUNIQUE制約により1目標1冊が保証される（test_models_crud.py::test_book_goal_id_unique_constraint）
- [x] 初期データ投入が重複しない（再起動時も同様）（test_seed_data.pyが件数をlen()で動的検証するため新規キー追加後も無改修で通過）
- [x] `material`／`exam_subject`／既存テーブルに変更がない

**Phase 14完了（2026-08-31）。バックエンド全602テスト・カバレッジ100%・ruff検査通過を確認済み。次はPhase 15（読書目標・記録API）から着手する。**

**注意点**

- マイグレーションSQLを目視レビューすること（Phase1と同じ注意点）
- プロンプトテンプレートの初期文面はPhase13で確定した文面から転記し、要約・改変をしないこと

---

