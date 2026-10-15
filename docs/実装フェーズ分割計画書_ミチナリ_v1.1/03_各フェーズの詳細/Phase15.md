### Phase 15：読書目標・記録API

| 項目 | 内容 |
| --- | --- |
| 目的 | 読書目標のCRUDと日次記録APIの種別分岐を実装する（AI連携を除く） |
| 投入文書 | CLAUDE.md、運用設計ルール、仕様書・設計書 データ構造編（Phase13で反映した読書関連節） |

**実装対象**

- [x] 目標作成・更新APIの `category` 対応（`category=READING` のとき `exam_subject`／`material`／`load_profile` 関連の入力・バリデーションを要求しない）→ `GoalCreate.category`、`goal_service.create_goal`/`activate_goal`（EXAM/READINGで分岐）
- [x] `book` のCRUD → `book_service.py`（新設）、作成は試験科目・教材と同じネストパス`POST /goals/{id}/book`（`api/goals.py`）、更新・読了は`api/books.py`（新設）
- [x] 日次記録APIの分岐：`category=READING` の目標に対しては `study_log` ではなく `reading_log` を受け付ける（`daily_record` 本体・確定ロジックは無改変で共用）→ `record_service.py`に`ReadingLogItem`・`_apply_reading_logs`を追加、`register_progress`/`finalize_record`に`reading_items`引数を追加（デフォルトNoneで後方互換）
- [x] 残日数・直近記録日・連続記録日数（`total_pages`設定時のみページ進捗）の実装 → `book_service.get_book_progress`。**設計変更**：`GET /goals/{id}/plan`は実装せず、教材の派生値が`MaterialRead`に埋め込まれているのと同じ方式で`BookRead`へ埋め込んだ（データ構造編1.1（改5）に反映済み）
- [x] 目標クローズ処理の確認（読書目標のクローズ＝読了として成立すること）→ `book_service.complete_book`が`POST /books/{id}/complete`経由で`GoalStatus.CLOSED_WITH_RESULT`に遷移。中断は既存の`POST /goals/{id}/close`をそのまま流用（`exam_subjects`が常に空のため自動的に確認必須の「結果なし」経路になる）
- [x] バリデーション：`reading_log.recall_body` 必須、`pages_read`／`current_page` は0以上 → `schemas/record.py`の`ReadingLogInput`（**Phase 32で改訂**：`pages_read`を廃止し、`current_page`は0以上かつ`book.total_pages`以下とする）
- [x] `resource_ratio` バリデーションから読書目標を除外する → `goal_service.update_goal`がREADINGへの`resource_ratio`指定自体を拒否（常に0のまま）

**完了条件**

- [x] `category=EXAM` の既存エンドポイントの挙動に変化がない（既存テスト602件が無改修で全て通過）
- [x] `category=READING` の目標で科目・教材関連APIを呼んでも不整合が起きない（対象外として扱われる）
- [x] 1目標に2冊目の `book` を追加しようとすると拒否される（`BOOK_ALREADY_EXISTS`）
- [x] `reading_log` が `daily_record`×`book` 単位で一意登録される
- [x] 読書目標が `resource_ratio` の合計計算に算入されない

**Phase15完了（2026-08-31）。バックエンド全644テスト・カバレッジ100%・ruff検査通過を確認済み。次はPhase 16（読書AI連携）から着手する。**

**Phase15で追加対応した既存機能への回帰防止（未計画だったが実装中に必要と判明したもの）**

読書目標の作成・進行が可能になったことで、Phase5・Phase10で実装済みの資格試験用AI機能（本フェーズの対象外）が読書目標のデータを誤って取り込むリスクが顕在化したため、最小限のガードを追加した（詳細はロジック・プロンプト編21.1）。

- `ai_context_service.list_active_exam_goals`を新設し、`daily_feedback_service`・`daily_message_service`が参照する「進行中の目標」をEXAMに限定（読書目標が「試験科目未登録」という誤った文脈でプロンプトに混入するのを防止）
- `retrospective_service.generate_retrospective`が`category=READING`の目標に対してVALIDATION_ERRORを返すよう変更（EXAM専用プロンプトを読書目標に適用してしまうのを防止）。**Phase16でGOAL_RETROSPECTIVE_READINGを実装した時点でこの拒否は不要になるため、Phase16の実装対象に「このガードの解除」を含めること**

**注意点**

- サービス層でHTTP例外を出さない（ドメイン例外→API層変換の既存原則を踏襲）
- AI連携は本フェーズに含めない。報告確定は `chat_message` が空の状態で成立させる（Phase4と同じ方針）

---

