### Phase 22：仕事AI連携

| 項目 | 内容 |
| --- | --- |
| 目的 | 仕事用の日次フィードバックと月次報告ドラフト・半期評価レポート生成を実装する |
| 投入文書 | CLAUDE.md、運用設計ルール、設計書 ロジック・プロンプト編（Phase19で反映した仕事プロンプト節、第16章のAI連携基盤は流用） |

**実装対象**

- [x] `DAILY_FEEDBACK_WORK` 呼び出しの実装 → `work_feedback_service.py`（新設、`reading_feedback_service.py`と対）。既存の`ai/client.py`・`ai/conversation.py`・`ai/prompt_builder.py`・`ai/rate_limiter.py`・`ai/logger.py`・`ai/orchestration.py`は無改変で流用し、purpose分岐のみ追加
- [x] `GOAL_RETROSPECTIVE_WORK_MONTHLY`／`GOAL_RETROSPECTIVE_WORK_SEMIANNUAL`呼び出しの実装 → `work_report_service.py`（新設）。対象work_assignmentの`work_log.body`を対象期間で時系列連結した変数を注入し、前期間の`goal_retrospective`（存在すれば）を注入する
- [x] `get_latest_retrospective`の拡張：`period_type`／`period_key`を指定した絞り込みに対応させる（データ構造編5.4「『最新の総括レポートを取得する』ロジックの拡張」）
- [x] 月次・半期の期間判定ロジックの実装（ロジック・プロンプト編22.5）。対象月・対象半期の算出、前月・前半期の算出
- [x] `POST /goals/{id}/monthly-report`・`GET /goals/{id}/monthly-report`・`PATCH /goals/{id}/monthly-report`・`POST /goals/{id}/semiannual-review`・`GET /goals/{id}/semiannual-review`・`PATCH /goals/{id}/semiannual-review`の実装（`api/closure.py`または新設ファイル）
- [x] AI応答のパース処理の実装（ロジック・プロンプト編22.6）：見出し文字列（17.9は5節、17.10は4節）で応答テキストを分割し、`business_summary`／`achievement_score`／`achievement_reflection`／`next_goal_text`／`report_notes`の各列へ格納する。「達成度」節が1〜5の数字以外（「対象外」を含む）の場合は`achievement_score`をNULLとする。見出しが検出できない項目があっても例外にせず空文字のまま保存する（AI応答全文は既存の`ai_log`に残るため情報は失われない）
- [x] `body`組み立てテンプレートの実装（ロジック・プロンプト編22.6のMarkdownテンプレート）。生成時・PATCH保存時のいずれも、構造化列から`body`を再組み立てする（`body`を直接受け取るAPIは設けない）
- [x] `PATCH`の挙動：対象行が存在すれば該当列を更新し`edited_at`を現在時刻に設定、存在しなければ新規作成する（前期の記録が無い初回利用者向けの手動シード、要件定義書R-83）。生成専用列（`business_summary`等）を指定せずに`target_goal_text`のみ更新するリクエストを許容する
- [x] `POST /records/{date}/work-chat`の実装（DAILY_FEEDBACK_WORK。`chat_message.purpose`で資格試験・読書との対話履歴混入を防止する既存の仕組みをそのまま適用）
- [x] 既存の`POST /goals/{id}/retrospective`がWORK目標に対して恒久的にVALIDATION_ERRORを返すことを確認・テストする（読書がPhase15〜16で経由した暫定ガードとは異なり、本フェーズの実装時点で最初から恒久仕様として実装する）
- [x] 「今日の一言」（DAILY_MESSAGE）の対象拡張：`list_active_exam_goals`とは別に、EXAM・WORKを対象とする関数（例：`list_daily_message_target_goals`）を新設し、`daily_message_service`が参照する対象をこの関数に切り替える。`{{goal_summary}}`・`{{progress_summary}}`・`{{recent_activity}}`のビルダーをgoal.categoryで分岐させ、WORK用の変数ビルダー（22.2の経過日数・直近記録日・連続記録日数・直近の月次報告有無を用いる）を新設する
- [x] 週次要約の生成判定ロジックから仕事目標を除外することの確認 → 変更不要（`weekly_summary_service`は`Material.goal_id`起点のため仕事目標は元から対象外）。回帰防止テストを追加して確認

**完了条件**

- [x] 仕事目標の日次報告でWORK用プロンプトによるフィードバックが取得できる
- [x] 月次報告ドラフト・半期評価レポートが生成・再生成できる（案件が進行中のまま生成できることを含む）
- [x] 前月・前半期の報告が存在する場合、その内容を踏まえたドラフトが生成される（前月・前半期の報告が無い場合もエラーにならない）
- [x] 今日の一言が仕事目標を対象に含み、読書目標は引き続き対象外であることをテストで確認する
- [x] 資格試験用・読書用のプロンプト・呼び出し・アシスタント設定に影響がない（相互の対話履歴が混入しないことを検証する回帰テストを追加）
- [x] 半期の期間判定（3月〜8月、9月〜翌2月、閏年の2月29日を含む）が正しく動作する
- [x] AI呼び出しが失敗しても実績（業務記録）入力が失われない

**Phase22で追加対応が必要な可能性がある事項**：Phase16（読書AI連携）では`chat_message.purpose`列の追加、AI対話エンドポイントの分離という設計変更が実装時に必要になった。仕事目標でも同様に、日次報告フィードバックとの同時進行時の対話履歴分離は`purpose`列の既存の仕組み（`DAILY_FEEDBACK_WORK`という値を追加するだけ）で対応可能な想定だが、実装時に想定外の分岐が必要になった場合は本ファイルの完了報告に追記すること。

**注意点**

- Web検索・ナレッジ検索の明示的無効化など、既存のAI連携制約は仕事用呼び出しにも同様に適用する（`ai/client.py`を無改変で流用しているため自動的に満たされる）
- ノルマ達成・生産性評価を前提とした文面にしないこと（Phase19で確定した初期文面から逸脱しない。17.8〜17.10のプロンプトは転記のみで改変しない）
- 月次報告・半期評価は「アプリ内でドラフトを生成するのみ」であり、Microsoft Forms等への自動送信機能を実装しないこと（要件定義書R-78背景）

**Phase22完了（2026-09-05）。**`work_feedback_service.py`（新設、DAILY_FEEDBACK_WORK）・`work_report_service.py`（新設、月次報告・半期評価の生成・PATCH編集・期間判定22.5・AI応答パース＋body組み立て22.6を集約）を追加。`retrospective_service.get_latest_retrospective`をperiod_type／period_key対応に拡張し（既存のEXAM/READING呼び出しは無改変で動作）、`generate_retrospective`にWORK目標への恒久的なVALIDATION_ERRORガードを追加。`ai_context_service.py`にWORK用の日次・月次・半期向け変数ビルダー（`build_daily_work_summary_text`等）と、今日の一言の対象をEXAM・WORKに拡張する`list_daily_message_target_goals`を追加（READINGは引き続き対象外）。API層は`api/closure.py`に`POST`/`GET`/`PATCH /goals/{id}/monthly-report`・`/semiannual-review`を、`api/records.py`に`POST /records/{date}/work-chat`を追加した。バックエンド全876テスト・カバレッジ100%・ruff検査通過（既存の資格試験・読書関連コードは新しいカテゴリ分岐の追加以外無改修）。次はPhase 23（仕事フロントエンド）から着手する。

**追記（2026-09-05）**：`ai.assistant_uid.daily_feedback_work`（AI-08）の既定値を、空文字（未選定）からAI-06（読書日次報告フィードバック）と同一のGPT-5.4-mini「高速」へ選定した（仕様書1.1（改11）S-09一部解消、データ構造編1.1（改14））。既存DBの空欄値を補う一度きりの補正は`backfill_reading_assistant_defaults`と共通の内部関数（`_backfill_assistant_defaults`）に切り出した`backfill_work_assistant_defaults`で実装。`ai.assistant_uid.goal_retrospective_work_monthly`／`_semiannual`（AI-09・AI-10）は低頻度・高品質重視の判断に実環境検証が必要なため、引き続き未選定のまま据え置く。

---

