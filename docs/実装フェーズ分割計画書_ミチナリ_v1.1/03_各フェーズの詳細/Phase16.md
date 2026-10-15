### Phase 16：読書AI連携

| 項目 | 内容 |
| --- | --- |
| 目的 | 読書用の日次フィードバックと読了レポート生成を実装する |
| 投入文書 | CLAUDE.md、運用設計ルール、設計書 ロジック・プロンプト編（Phase13で反映した読書プロンプト節、第16章のAI連携基盤は流用） |

**実装対象**

- [x] `DAILY_FEEDBACK_READING` 呼び出しの実装 → `reading_feedback_service.py`（新設、`daily_feedback_service.py`と対）。既存の `ai/client.py`・`ai/conversation.py`・`ai/prompt_builder.py`・`ai/rate_limiter.py`・`ai/logger.py`・`ai/orchestration.py` は無改変で流用し、purpose分岐のみ追加
- [x] `GOAL_RETROSPECTIVE_READING` 呼び出しの実装 → `retrospective_service.generate_retrospective`をEXAM/READINGで分岐する構成に変更（`_build_exam_variables`/`_build_reading_variables`）。対象bookの `reading_log.recall_body` を時系列で連結した変数（`{{reading_logs}}`）を注入（`ai_context_service.build_reading_logs_text`）。Phase15で追加した「READING目標への呼び出しをVALIDATION_ERRORで拒否するガード」は、GOAL_RETROSPECTIVE_READINGへの分岐に置き換えて解消した（書籍未登録時のガードのみ残す）
- [x] 会話スコープ・フォルダ命名（目標名ベース）が読書目標でも成立することの確認 → `ensure_conversation`は無改変のため、GOAL_RETROSPECTIVE_READING（goal指定あり）は資格試験の総括レポートと同じ経路でフォルダ作成される。DAILY_FEEDBACK_READINGはDAILY_FEEDBACKと同じくgoal=NULL（フォルダ非対応、複数目標にまたがりうるため）
- [x] 週次要約の生成判定ロジックから読書目標を除外する → 変更不要（`weekly_summary_service`は`Material.goal_id`起点でgoal_idを求めるため読書目標は元から対象外）。回帰防止テストを追加して確認

**完了条件**

- [x] 読書目標の日次報告でREADING用プロンプトによるフィードバックが取得できる
- [x] 読了時に読了レポート（要約／感じたこと・考えたこと・気づいたこと構成）が生成・再生成できる
- [x] 資格試験用のプロンプト・呼び出し・アシスタント設定に影響がない（`test_reading_feedback_service.py`に相互の対話履歴が混入しないことを検証する回帰テストを追加）
- [x] 週次要約の遡及生成処理が読書目標を対象に含めず、エラーも起こさない
- [x] AI呼び出しが失敗しても実績（想起）入力が失われない（既存の16.7の保証を踏襲）

**Phase16完了（2026-08-31）。バックエンド全672テスト・カバレッジ100%・ruff検査通過を確認済み。次はPhase 17（読書フロントエンド）から着手する。**

**Phase16で追加対応した設計上の変更点**

- 同一`daily_record`に資格試験（DAILY_FEEDBACK）と読書（DAILY_FEEDBACK_READING）の対話が混在しうるようになったため、`chat_message`に`purpose`列を追加（マイグレーション`9723ab049ecd`、既存行は`DAILY_FEEDBACK`として遡及設定）。対話履歴（`{{conversation_history}}`）への注入はpurposeで絞り込み、`sequence`採番は表示順の一貫性のため日次記録全体で共有する
- AI対話は`POST /records/{date}/chat`（資格試験）と`POST /records/{date}/reading-chat`（読書）を別エンドポイントとした。1回のHTTP呼び出しで両カテゴリを多重化する設計は複雑さに見合わないと判断し、既存の「用途ごとに会話を分離する」方針（16.3）をエンドポイント単位でも踏襲した
- 読書用のアシスタントUID（`ai.assistant_uid.daily_feedback_reading`／`goal_retrospective_reading`）と想起注入日数（`ai.reading_recall_recent_days`）を設定API（`GET`/`PATCH /settings`）から変更可能にした（仕様書6.11「全ての設定項目を画面上から変更可能」）。実際のアシスタントUID値は未選定のまま（空文字）で、実環境での疎通確認（Phase11相当）を経て運用時に設定する

**注意点**

- Web検索・ナレッジ検索の明示的無効化など、既存のAI連携制約（16.1〜16.4）は読書用呼び出しにも同様に適用する（`ai/client.py`を無改変で流用しているため自動的に満たされる）
- ノルマ達成・合格圧力を前提とした文面にしないこと（Phase13で確定した初期文面から逸脱しない。17.6・17.7のプロンプトは転記のみで改変していない）

---

