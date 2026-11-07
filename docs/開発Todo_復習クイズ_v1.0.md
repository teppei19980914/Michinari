# 開発Todo：復習クイズ（Phase 49 対象）

本書は、資格試験・読書のテーマ累積（振り返り）から AI がクイズを作り、間隔を空けて出題する「復習クイズ」機能の開発作業の正（Single Source of Truth）である。
作業は `dev/2026-11-06`（`origin/main` 2.5.0 から作成）で行う。版数は次回マイナー版（2.6.0 想定）を見込むが、`pyproject.toml` の実際の更新は `release.bat` 実行時に行う（開発中は変更しない）。

## 0. 決定事項

### 0.1 利用者に確認し、回答を得て確定した事項

| # | 決定 | 値 |
| --- | --- | --- |
| U1 | 要件7「目標ごとのQ&Aチャットとの仕組み共有」の前提訂正 | 調査の結果、「目標ごとのQ&Aチャット」は**目標相談チャットとして資格・読書・仕事の全種別で既に完全実装済み**（要件定義書6.14 R-104〜R-114）。要件7は「未実装」という誤った前提で書かれていたため訂正する。利用者の回答により、**仕組みはパターンだけ再利用する**（関数の共通化はしない）。出典検証はヘルプAIアシスタント（`help_assistant_service.py`、セクションID照合）より、目標相談チャット（`goal_consultation_service_common.py:104-130` の `_parse_answer`、応答末尾の根拠行から日付を抽出し「その回のプロンプトに実際に含めた範囲」のみを採用する検証）の方が構造的に近く、こちらの考え方を参考に新規実装する |
| U2 | クイズ作成のタイミング | 利用者の回答により**両方**実装する。①起動時バッチ（テーマ分類の直後、`run_ai_startup_tasks` 内）で自動生成、②テーマ詳細ページ等に手動の「クイズを作る／作り直す」操作を用意する。ダッシュボード初期表示では作らない（確定事項） |
| U3 | テーマ統合・改名・再構築／目標アーカイブ・削除時の既存クイズの扱い | 利用者の回答により**削除**する。テーマの統合（`merge_themes`）・改名（`rename_theme`）・再構築（`rebuild_theme`）が起きたとき、対象テーマに紐づく未出題・未確定の `quiz_question`（間隔の進行状況を含む）を削除し、次回の生成（バッチまたは手動）で作り直す。目標の削除は既存の `ForeignKey(..., ondelete="CASCADE")` 方式（§1.1参照）で自動的に連動する。**回答履歴（`quiz_answer_log`）は削除しない**（分析画面の正答率推移が、テーマ再構築のたびに失われることを避けるため。後述0.2 D4） |
| U4 | クイズの問題・回答履歴のナレッジエクスポート反映 | 利用者の回答により**含めない**。匿名化版（確定事項）・通常版（本決定）とも、`ExportSelection`（`export_service_common.py:45-61`）に項目を追加しない。クイズは記憶定着の補助であり、「紹介資料化・ブログ転換」というナレッジエクスポートの目的（`export_service_common.py:1-7`）とは性質が異なるため |

### 0.2 実装上の判断（利用者確認は不要な技術的決定。根拠を併記）

| # | 決定 | 理由 |
| --- | --- | --- |
| D1 | テーブルは2つ：`quiz_question`（問題本体＋現在の間隔進行状態＋`last_answered_at`〈NULL=未出題〉を1行に持つ。1:1のため分割しない）、`quiz_answer_log`（回答履歴、分析用） | `recap_theme` の「本文＋状態を1テーブル」方式に合わせる。間隔進行専用テーブルを分けると結合が増えるだけで利点がない。`last_answered_at`は実装時に追加：U3（テーマ変更・目標アーカイブ削除時）は全行削除、利用者操作「作り直す」は未出題のみ削除、という2つの削除範囲を区別する必要があり、`interval_index`だけでは「未出題」と「不正解で0に戻った行」を判別できないため |
| D2 | 選択肢は4列（`choice_1`〜`choice_4` + `correct_choice_index`） | 本コードベースにJSON列の前例が無い（確認済み、既存モデルはすべて素朴な型）。4択固定（要件2）のため列数固定で十分 |
| D3 | `quiz_question.theme_id` は `recap_theme.id` への `ForeignKey(ondelete="CASCADE")` のみを持つ（`goal_id` は持たない） | `recap_theme` が既に `goal_id` へCASCADEを持つため、目標削除→テーマ削除→クイズ削除の連鎖で十分。`recap_entry` のような直接の `goal_id` 重複列は、クイズでは目標単位の直接検索が無いため不要（CLAUDE.md DRYの原則：不要な列を増やさない） |
| D4 | `quiz_answer_log.theme_id` は `recap_theme.id` へCASCADE、`question_id` は `quiz_question.id` へ `ondelete="SET NULL"`（nullable） | テーマの改名・再構築で `quiz_question` 行を削除しても（U3）、分析画面の正答率推移（要件5）はテーマ単位で継続して見られる必要があるため、履歴はテーマに紐付け、問題個体への参照は失われてもよい（`SET NULL`）。テーマが統合で消える場合（`merge_themes` のsource）は履歴もCASCADEで消える（U3の対象にテーマ統合を含めたことと整合） |
| D5 | `AiPurpose.QUIZ_GENERATE` / `ConversationScope.QUIZ_GENERATE`（1種のみ、カテゴリ非依存） | `recap`（`RECAP_CLASSIFY`・`RECAP_THEME_BODY`、スコープは`RECAP`の1種）と同じ「カテゴリ非依存で用途を増やさない」方式。目標相談チャット（カテゴリ別に3種）ではなく recap 方式を採る（クイズ生成は目標ごとの対話ではなく、テーマ単位のバッチ生成であり recap と性質が同じため） |
| D6 | 利用アシスタントは新設せず、既存の週次要約用（`AI_ASSISTANT_UID_WEEKLY_SUMMARY` / `_READING`）を流用 | `recap_generation_service.py:40-44` の `_ASSISTANT_KEY_BY_CATEGORY` と同じ理由（アシスタント設定項目を増やさない） |
| D7 | 新設する `app_setting` は3件のみ：`quiz.questions_per_theme`（既定"3"）、`quiz.interval_days`（既定"1,3,7,14,30"、CSV文字列、`setting_reader.get_int_list` で読む）、`quiz.daily_limit`（既定"5"） | 要件2・3の「問題数」「間隔」「1日の上限」に対応する最小限の3件。プロンプトの文字数予算は既存の `RECAP_CLASSIFY_CHUNK_CHARS`（テーマに紐づく報告のチャンク化）と `ai.max_prompt_chars`（総量予算、既存）を流用し、新規の予算設定は追加しない（DRY） |
| D8 | 専用の設定画面UIは追加しない | `RECAP_*` の3設定キーも `frontend/src/features/settings/` に対応UIが無い（確認済み、grep 0件）。クイズの3設定も同様に内部パラメータとして扱い、既定値のseedのみ行う（利用者が変更したい場合は将来別途対応） |
| D9 | クイズ生成の入力は、テーマ本文（`RecapTheme.body`、文脈用）と、テーマに紐づく個々の報告（`recap_service.theme_entry_rows` → `entry_texts`、`(日付)本文` の形で明示的に日付を保持した生データ）の両方 | テーマ本文はAIが自由に要約した結果であり、元の日付表記が逐語的に残るとは限らない。出典検証（要件2・要件7 U1）を確実にするため、分類時と同じ「日付を明示したエントリ一覧」を生成時にも渡す（`recap_generation_service.py` の分類プロンプトと同方式）。件数が多い場合は既存の `RECAP_CLASSIFY_CHUNK_CHARS` でチャンク化し、1チャンクごとに生成する |
| D10 | 出典検証の実装はヘルプAIアシスタント方式ではなく目標相談チャット方式を模す（U1） | 具体的には、AI応答の各問題末尾に `[出典: YYYY-MM-DD]` 形式の行を出させ、その日付が「その回のプロンプトに実際に含めたチャンクの日付集合」に含まれるものだけを採用する。含まれない・解析できない問題は個別に破棄する（バッチ全体は失敗させない） |
| D11 | 複数問題の出力形式は区切り文字で分割し、問題単位で検証・破棄する | 要件2「検証に通らない問題は捨てる」は個々の問題単位の話であり、1問の不正でバッチ全体を無効にしない。区切りはプロンプトで固定文字列（例："==="）を指定し、`goal_consultation` の乱数nonce方式（第三者の埋め込みが混在しうる対話とは違い、クイズ生成はAIの純粋な出力のみを解析するため、乱数区切りは不要と判断）とは異なる単純な方式でよい |
| D12 | バッチでの自動生成は「まだ一度もクイズを生成していないテーマ」にのみ行う（questionsが0件のテーマが対象） | 要件2bの「問題数は app_setting」は1回あたりの生成数であり、起動のたびに無制限に積み増す設計ではない。手動の「作り直す」操作時は既存の未出題分を削除してから再生成する（U3と同じ削除方式） |
| D13 | `backup_service.DATA_SCHEMA_VERSION` を `"1.6"` → `"1.7"` に上げ、`_IMPORTABLE_SCHEMA_VERSIONS` に `"1.6"` を追加 | `backup_service.py:34-58` の既存の版歴（1.1〜1.6）と同じ方式。新テーブル追加のたび版を上げている既存の運用に合わせる。旧版の書き出しはインポート時にクイズ関連テーブルが空のまま復元される（既存の1.5→1.6と同じ扱い） |
| D14 | 分析画面は新規タブ「クイズ正答率」を `frontend/src/features/analytics/` に追加（既存9タブと同列） | 要件5「正答率の推移と苦手なテーマ」はテーマ横断の集計であり、既存の `ProgressTab`/`QualityTrendTab` 等と同じ画面構成に合わせるのが自然 |
| D15 | 「節目のお祝い」への「復習の連続日数」追加（要件5後段）は**本Todoの範囲外とし、見送る** | `goal_milestone_achievement`（Phase48）は指標ごとに専用の `app_setting` 閾値列（`MILESTONE_*_THRESHOLDS`）とフロント文言を持つ構造で、新指標の追加は新規閾値設定・判定ロジック・フロント文言追加を要する別規模の作業になる。要件自体も「（実装済みの場合）追加するかも検討する」という任意表現であり、スコープ拡大よりも本機能の確実な完成を優先する。将来、別Todoで対応する |

## 1. 影響範囲（フルスキャンの結果）

### 1.1 バックエンド（変更する箇所）

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| 列挙 | `app/constants/enums.py:87-125` の `AiPurpose`・`ConversationScope` | `QUIZ_GENERATE` を各1件追加（D5） |
| 設定キー | `app/constants/app_setting_keys.py`（`RECAP_*` の並び、112-116行付近） | 3キー追加（D7） |
| 初期データ | `app/init/seed_data.py`（`INITIAL_APP_SETTINGS` 184-193行付近・`INITIAL_PROMPT_TEMPLATES` 246-247行付近）、`app/init/prompt_texts.py`（または `prompt_texts_common.py`） | 既定値・プロンプト本文の追加。起動時シードは「不足分のみ投入」のため既存DBにも届く |
| モデル | `app/models/`（新規 `quiz.py`、`recap.py:29-69` と同じ書き方：`CreatedAtMixin`／`native_enum=False` の `Enum` は本機能では不使用、選択肢は素朴な列） | 新規2テーブル（`quiz_question`・`quiz_answer_log`） |
| マイグレーション | `backend/alembic/versions/`（head = `fd8470506d29`） | 新規1ファイル（`create_table` のみ。既存テーブル変更なし） |
| データ管理 | `app/services/backup_service.py:34-58` | `DATA_SCHEMA_VERSION` を1.7へ（D13） |
| AI基盤 | `app/ai/orchestration.py`（`send_and_log`・`load_template_body`・`get_max_prompt_chars`）、`app/ai/prompt_builder.py`（`build_simple`）、`app/ai/conversation.py`（`ensure_conversation`） | 既存の経路をそのまま呼び出す（変更不要、recap と同方式） |
| 新規サービス | `app/services/quiz_service.py`（出題選択・解答記録・間隔の進行計算・テーマ変更時の削除。AI非依存、`recap_service.py` 相当）、`app/services/quiz_generation_service.py`（AI呼び出しによる生成・出典検証・破棄、`recap_generation_service.py` 相当） | 追加 |
| 既存サービスへの連携 | `app/services/recap_service.py`（`rename_theme:269-273`・`merge_themes:276-`）にテーマ変更時のクイズ削除フックを追加、または呼び出し元（API層）でトランザクションをまとめて呼ぶ | 要実装時に判断（関数内で直接呼ぶと循環import の恐れがあるため、呼び出し元から明示的に両方呼ぶ方式を優先検討） |
| 起動時バッチ | `app/main.py:287-298` の `run_ai_startup_tasks()`、`recap_generation_service.run_all` の直後 | `quiz_generation_service.run_all` 呼び出しを追加（要件1:4、D12） |
| 新規API | `app/api/quiz.py`（`GET /quiz/today`・`POST /quiz/{id}/answer`・`POST /themes/{theme_id}/quiz/generate`）、`app/schemas/quiz.py`、`app/main.py`（`include_router` 登録）。AI未設定時の判定は既存の`useAiConfigured`／`GET /ai-status`を再利用し専用エンドポイントは設けない | 追加 |
| ダッシュボード | `app/api/dashboard.py:246-327` の `get_dashboard()`・`DashboardRead` スキーマ | 「今日の復習N問」フィールド追加（DB読み取りのみ、AI呼び出しなし。`_build_weekly_digest` 171-209行と同方針） |
| 分析 | `app/api/analytics.py`・`app/services/analytics_service.py` | 新規エンドポイント（正答率推移・苦手テーマ） |
| テスト | `backend/tests/`（フラット構成。新規 `test_quiz_service.py`・`test_quiz_generation_service.py`・`test_api_quiz.py`・`tests/quiz_helpers.py`〈`recap_helpers.py` 相当〉） | 追加 |

### 1.2 フロントエンド（変更する箇所）

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| API層 | `src/api/quiz.ts`（新規）、`src/types/api.d.ts`（`npm run generate:api-types` で再生成） | 追加 |
| 機能 | `src/features/quiz/`（新規：出題カード、解答UI、結果表示、AI未設定時の案内） | 追加 |
| ダッシュボード | `src/pages/DashboardPage.tsx` | 「今日の復習N問」セクション追加 |
| テーマ詳細 | テーマ詳細ページ（recap機能実装時に追加されたコンポーネント、要実装時に特定） | 「クイズを作る／作り直す」ボタン追加 |
| 分析画面 | `src/features/analytics/`（新規 `QuizAccuracyTab.tsx`、既存9タブと同列） | 追加 |
| 文言 | `src/locales/ja.json`・`en.json` | 新規 `quiz` 名前空間 |
| AI未設定時 | `src/components/AiUnconfiguredNotice.tsx`・`src/hooks/useAiConfigured.ts` | 既存を再利用（変更不要） |

### 1.3 ドキュメント（変更する箇所）

| 文書 | 変更 |
| --- | --- |
| `docs/要件定義書_ミチナリ_v1.1.md` | 新節（6.15想定）の新設、改訂履歴 |
| `docs/仕様書_ミチナリ_v1.1/06_画面仕様/`（該当チャプター） | 画面仕様（ダッシュボード・テーマ詳細・分析）、AI連携一覧、設定項目、改訂履歴 |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1/17_プロンプト設計/` | 処理フロー、プロンプト、出典検証、脅威モデル（STRIDE）、改訂履歴 |
| `docs/設計書_データ構造編_ミチナリ_v1.1/05_テーブル定義/` | `quiz_question`・`quiz_answer_log`、設定キー、改訂履歴 |
| `docs/実装フェーズ分割計画書_ミチナリ_v1.1/03_各フェーズの詳細/Phase49.md` | 新規追加、`index.md` 更新 |
| `docs/OPERATIONS.md` | 該当する運用手順があれば追記（現時点では新規の手動運用手順は想定していない） |
| `README.md` | 機能一覧への追記（要件に「2.1」という章番号参照があったが実在しないため、README構成に合わせて追記） |

### 1.4 確認だけする箇所（変更不要と確認済み）

| 項目 | 状況 |
| --- | --- |
| `backend/app/services/backup_service.py:148-234` の一括保存・復元 | `Base.metadata.sorted_tables` 方式のため、新規モデルを `Base` に登録するだけで自動対応。コード変更不要（`DATA_SCHEMA_VERSION` 更新のみ、D13） |
| `app/api/dashboard.py:246-327` の `get_dashboard()` | 既存どおりAI呼び出しなし。新フィールドもDB読み取りのみで追加できることを確認済み |
| `app/ai/orchestration.py`・`app/ai/rate_limiter.py` | 既存の送信・頻度制御・ログ記録をそのまま利用。変更不要 |
| `app/services/export_service_common.py:45-61` の `ExportSelection` | U4によりクイズ項目を追加しない。変更不要 |
| `frontend/src/components/AiUnconfiguredNotice.tsx`・`useAiConfigured.ts` | 既存コンポーネントをそのまま再利用（要件6） |
| `app/services/ai_context_exam.list_active_exam_goals`・`ai_context_reading.list_active_reading_goals` | `status == ACTIVE` かつ category で絞る既存関数をそのまま使う（`recap_generation_service.run_all:238-240` と同じ2関数）。WORKは呼ばないため自然に除外される |
| `app/services/goal_service.py:239-248` の `delete_goal` | 既存のCASCADE方式がそのまま新テーブルにも適用されることを確認済み（D3） |

### 1.5 横展開の対象

| 項目 | 対応 |
| --- | --- |
| `.claude/skills/fix-issue.md:16-24` の観点別レビュー起動条件 | 新規DBクエリ・新規AI用途・新規画面があるため、`injection-reviewer`（新規クエリ）・`xss-reviewer`（問題文・選択肢・解説の表示）・`test-coverage-reviewer`（新規ロジック）・`dry-reviewer`（新規定数・ID）・`style-reviewer`（新規ファイル）・`performance-reviewer`（ダッシュボード集計のN+1確認）を実施前に並列実行する。`secret-reviewer`・`auth-reviewer`・`dependency-reviewer` は該当変更があれば対象（新規依存は追加しない方針のため `dependency-reviewer` は該当なしの想定） |
| `AiPurpose`/`ConversationScope` への値追加の既存ルール | `goal_consultation_service_common.py:138-139` の「文字列値を揃える」慣行を踏襲（D5で1種のみのため該当は限定的） |
| 出典検証ロジックの実装場所 | ヘルプ・目標相談で個別実装（共通関数化されていない）という既存の状態を維持し、3つ目の個別実装として追加する（U1、D10） |

## 2. 現状のベースライン（開発前、2026-11-06、`dev/2026-11-06` ブランチ・`main` 2.5.0 相当）

- バックエンド（pytest）：2,158件合格、カバレッジ100%（文・分岐とも）。ruff 0件。
  - 参考：ブランチ作成前（旧 `dev/2026-10-29`、実DBとマイグレーション不整合あり）では `test_build_package_misc.py::test_run_tests_writes_coverage_data_outside_backend_dir` が1件失敗していたが、`main` からの再作成により解消（§6「既知のリスクと対策」に記録）。
  - 参考：再実行時に `test_desktop_tray.py::TestBuildIcon::test_uses_the_given_locale_for_the_tooltip_and_menu` が1回だけ失敗したが、単体実行では合格し、直後の全体再実行（2,158件）でも合格したため、再現しない一時的なフレーキーと判断（§6に記録、本機能の実装前に追加調査はしない）。
- フロントエンド（vitest + coverage）：176ファイル／1,508件合格、カバレッジ100%（文・分岐・関数・行）。
- フロントエンド（oxlint）：0件。
- フロントエンド（tsc -b）：0件。

## 3. 作業Todo

凡例：`[ ]` 未着手、`[x]` 完了。各項目の完了条件は「テストが通ること」と「カバレッジ100%（例外処理を除く）」。

### 3.1 文書改訂

- [x] D-01 要件定義書：新節（2026-11-06、6.19 R-138〜R-147、改訂履歴1.1改53）
- [x] D-02 仕様書：画面仕様（2026-11-06、6.1.6・6.8）、AI連携一覧（8.1 AI-18）、機能一覧（DSH-09・ANL-10）、改訂履歴1.1改65
- [x] D-03 設計書（ロジック・プロンプト編）：処理フロー・プロンプト・出典検証（2026-11-06、17.15新設、改訂履歴1.1改66）。STRIDEはD-07で別途実施
- [x] D-04 設計書（データ構造編）：`quiz_question`・`quiz_answer_log`、改訂履歴（2026-11-06、5.4追加、改訂履歴1.1改67）
- [x] D-05 実装フェーズ分割計画書：Phase49、index.md（2026-11-06）
- [x] D-06 README.md：機能一覧への追記（2026-11-06、「すべての種類に共通する機能」表に追加）
- [x] D-07 脅威モデル（STRIDE）：実施し設計書へ反映（2026-11-06、17.15.1新設。単一利用者ローカル運用のため認可境界の脅威は限定的、出典検証〈T・I〉とバッチの呼び出し頻度制御〈D〉が主な対策）

### 3.2 バックエンド実装

- [x] B-01 列挙・設定キーの追加（2026-11-06、`AiPurpose.QUIZ_GENERATE`・`ConversationScope.QUIZ_GENERATE`、設定キー3件）
- [x] B-02 `quiz_question`・`quiz_answer_log` モデル（D1〜D4）、マイグレーション（2026-11-06、`fa5a81543844_quiz_tables.py`、head=`fd8470506d29`→`fa5a81543844`、`create_table` のみ、実DBへの適用確認済み。自動生成時の不要な`alter_column`〈既存enum列、native_enum=Falseのため実害なし〉は削除済み）。実装中に設計を見直し、`quiz_question.last_answered_at`（NULL=未出題）を追加（U3の「テーマ変更時は全行削除」と、利用者操作「作り直す」の「未出題のみ削除」を区別するため必要と判明。Todo §0 D1に追記）
- [x] B-03 `backup_service.py`：`DATA_SCHEMA_VERSION` 1.7へ、`_IMPORTABLE_SCHEMA_VERSIONS` 更新（2026-11-06、D13）
- [x] B-04 シード：`app_setting` 既定値3件、`prompt_template`（2026-11-06、`QUIZ_GENERATE` 本文、D9・D10・D11の契約を満たす指示文。`prompt_texts_common.py`に追加）
- [x] B-05 `quiz_service.py`：出題選択（`next_due_date <= today` かつ日次上限）、解答記録（正解→次の間隔へ進める、不正解→最初の間隔へ戻す）、テーマ変更時の削除（2026-11-06、`delete_questions_for_theme`。`app/api/recap.py`のrename/merge/rebuildへフック済み）
- [x] B-06 `quiz_generation_service.py`：対象テーマの選定（D12：未生成テーマのみ、バッチ）、入力組み立て（D9）、AI送信（recap方式の`_send`相当）、出力解析・出典検証・個別破棄（D10・D11）、生成結果の保存（2026-11-06）。`recap_generation_service._chunk_by_chars`を`recap_service.chunk_by_chars`へ移設し共有（DRY、既存recapテスト50件で回帰無し確認済み）
- [x] B-07 `main.py`：`run_ai_startup_tasks()` に `quiz_generation_service.run_all` 追加（2026-11-06、recap呼び出しの直後）
- [x] B-08 API：`GET /quiz/today`・`POST /quiz/{id}/answer`・`POST /themes/{theme_id}/quiz/generate`（手動生成・作り直す、U2②）を実装（2026-11-06）。**設計変更**：`GET /quiz/config`は実装しない。フロントに既存の全画面共通フック`useAiConfigured`（`GET /ai-status`）があり、新規AI未設定時専用エンドポイントは不要と判明（既存の仕組みに従うというCLAUDE.mdの原則により、重複実装を避けた）。合わせて`RecapThemeSummaryRead`・`RecapThemeDetailRead`に`quiz_question_count`を追加（テーマ詳細の「作る」／「作り直す」表示分け用、N+1にならないよう`quiz_service.count_questions_by_theme`で一括取得）
- [x] B-09 ダッシュボード：`DashboardRead` へ `today_quiz_count` フィールド追加、`get_dashboard()` でDB集計のみ実装（2026-11-06、AI呼び出しなし）
- [x] B-10 分析：正答率推移・苦手テーマの集計API（2026-11-06、`analytics_service.compute_quiz_accuracy_trend`・`compute_quiz_theme_accuracy`、`GET /analytics/quiz-accuracy`）
- [x] B-11 セキュリティテスト：出典偽装（実在しない日付での検証突破）・形式不正ブロックの破棄・存在しない`question_id`/`theme_id`での404を`test_quiz_generation_service.py`・`test_api_quiz.py`でカバー（2026-11-06）。選択肢・解説文はAI生成文の表示のみでユーザー自由入力ではないため、フロント側のMarkdownText（生HTML非解釈）で対応（F-02）

### 3.3 フロントエンド実装

- [x] F-01 `api/quiz.ts`、型の生成し直し（2026-11-06、`npm run generate:api-types`）
- [x] F-02 `features/quiz/` の出題カード（`QuizSession.tsx`）・解答UI・結果表示（2026-11-06）。純粋関数は`quizProgress.ts`に分離。**訂正（レビュー後）**：当初ダッシュボードが0件時に非表示になることだけでAI未設定時の対応を済ませたと判断したが、要件6「AI未設定の場合は機能の説明と設定への案内だけを表示する」を満たしていなかった（`/quiz`へ直接遷移すると意味不明な「完了しました」が出る）。`QuizPage.tsx`に`useAiConfigured`／`AiUnconfiguredNotice`（目標相談チャット等と同じ既存パターン）を追加し修正。テーマ詳細の「クイズを作る」ボタン自体は、既存の「再構築」ボタンにも同種の未設定ガードが無い（既存の仕様のまま）ことと平衡させ、本Todoの範囲では変更しない
- [x] F-03 ダッシュボード「今日の復習N問」セクション（2026-11-06、`QuizTodaySection.tsx`、`DashboardPage.tsx`に配置。目標タブに依存しない全体値のため直近4週間カレンダーと同じ非依存の位置に置いた）
- [x] F-04 テーマ詳細ページに「クイズを作る／作り直す」ボタン追加（2026-11-06、既存の`RecapThemeEditCard.tsx`を拡張。別カードを新設せず関連操作をまとめた）
- [x] F-05 分析画面：`QuizAccuracyTab.tsx`（2026-11-06、既存タブと同列）。**設計変更**：正答率推移は折れ線グラフ（recharts）ではなく、週別・テーマ別の一覧表示（Card+リスト）とした。理由：データが少ない利用開始直後は折れ線の情報量が乏しく、既存の`MilestoneListTab`等も一覧表示で統一感があるため。将来データ量が増えた場合はグラフ化を検討（dataviz skillの手順に従う）
- [x] F-06 `ja.json`・`en.json`：`quiz` 名前空間・`recapTheme.quiz*`・`analytics.quizAccuracy`（2026-11-06、キー集合の一致を確認済み）
- [x] F-07 `npm run lint`（2026-11-06、oxlint 0件）・`npx tsc -b`（0件）・`npm run test`（vitest、182ファイル/1533件合格、カバレッジ100%）

### 3.4 検証

- [x] V-01 ruff・pytest・vitest（2026-11-06、新規機能のカバレッジ100%。全体の最終実行結果は §8）
- [x] V-02 既存DBからのアップグレード（2026-11-06、実際の利用者DBで確認済み。B-02実施時に`data/michinari.db`を`fd8470506d29`→`fa5a81543844`へ安全退避コピー付きで移行し、実サーバ起動＋`GET /dashboard`・`GET /quiz/today`・`GET /goals/1/recap-themes`で正常応答を確認）
- [x] V-03 一括保存・復元（2026-11-06）：`test_backup_service.py`の既存の汎用round-tripテスト（`Base.metadata`の全テーブルを動的に対象とする設計、コード変更不要）に`quiz_question`・`quiz_answer_log`の空リスト確認を追加し合格
- [x] V-04 ナレッジエクスポート（2026-11-06）：`export_service_*.py`全4ファイルに`quiz`の参照が無いことをgrepで確認（コード変更なし、U4どおり対象外）
- [x] V-05 テーマ変更時の削除（2026-11-06）：`test_api_recap.py`に改名・統合（source/target双方）・再構築それぎれのテストを追加し合格（未出題クイズは削除、`quiz_answer_log`は残ることをID単位で確認）
- [x] V-06 配布物への同梱確認（2026-11-06、`test_build_package.py`系は既存のまま全件合格。新規の同梱対象ファイル〈help_content.json相当〉は無いため変更不要）
- [x] V-07 フルスキャンの再確認（2026-11-06、§5.1参照。dry/style/label/injection/xss/test-coverage/performanceの7観点レビューを実施し、CRITICAL 1件〈ReDoS〉含め全指摘に対応済み）
- [ ] V-08 実機確認（ブラウザ）：AI未設定時の案内表示→設定後にダッシュボードへ「今日の復習」が出る→解答→間隔が進む／戻ることを確認。**本セッションでは未実施**（ブラウザ操作ツールが利用できないため）。代わりに実サーバ起動＋実DBへの疎通確認（V-02参照）とフロントエンドのproduction build成功を確認済み。利用者による実機確認が必要（§8の最終記録「残課題」参照）

## 4. 処理フロー（確定版）

### 4.1 生成（起動時バッチ、`quiz_generation_service.run_all`）

1. 対象goal：`ai_context_exam.list_active_exam_goals` と `ai_context_reading.list_active_reading_goals` の合算（recapと同じ2関数、WORKは自然に除外）。
2. 各goalの各 `RecapTheme` について、既存の `quiz_question` が1件も無いテーマのみ対象とする（D12、積み増しを防ぐ）。
3. テーマに紐づく報告一覧（`recap_service.theme_entry_rows` → `entry_texts`）を、既存の `RECAP_CLASSIFY_CHUNK_CHARS` でチャンク化する。
4. チャンクごとに、テーマ本文（文脈）・エントリ一覧（日付付き）・問題数（`quiz.questions_per_theme`）を変数にプロンプトを組み立て（`prompt_builder.build_simple`）、`ai_orchestration.send_and_log` で送信（`AiPurpose.QUIZ_GENERATE`、新規チャット、既存アシスタント流用）。
5. 応答を区切り文字で問題単位に分割し、各問題について「4択＋正解＋解説＋出典行」の形式を解析。解析失敗、または出典日付がそのチャンクの日付集合に含まれない問題は個別に破棄する（D10・D11）。
6. 採用された問題を `quiz_question` として保存する（`interval_index=0`、`next_due_date=本日`＝即時出題可能）。
7. 1目標の失敗は他目標を止めない（recapの `run_all` と同方式、例外を握りつぶしログのみ）。

### 4.2 生成（手動、`POST /themes/{theme_id}/quiz/generate`）

1. 対象テーマの既存未出題分（`quiz_question` のうち回答済みでない行。回答履歴は残す）を削除する。
2. 4.1の3〜6と同じ処理を同期的に実行し、結果を返す。

### 4.3 出題（`GET /quiz/today`）

1. `next_due_date <= 本日` の `quiz_question` を、紐づくgoalが進行中（ACTIVE・EXAM/READING）のものに限り取得する。
2. `quiz.daily_limit` 件に絞って返す（ダッシュボードの「今日の復習N問」も同じ件数を表示）。

### 4.4 解答（`POST /quiz/{id}/answer`）

1. 正解：`interval_index` を1つ進め、`quiz.interval_days` の該当日数だけ `next_due_date` を進める（配列の末尾を超えたら末尾の間隔を維持）。
2. 不正解：`interval_index` を0へ戻し、`next_due_date` を本日（または翌日）に設定。
3. いずれも `quiz_answer_log` へ1行追加（`question_id`・`theme_id`・`is_correct`・`answered_at`）。

### 4.5 テーマ変更時の削除（U3・D3・D4）

1. `rename_theme`・`merge_themes`・`rebuild_theme` の呼び出し元（API層、同一トランザクション）で、影響するテーマID（改名・再構築はそのテーマ、統合はsource・targetの両方）について、未回答の `quiz_question` を削除する。
2. `quiz_answer_log` は削除しない（`theme_id` は改名・再構築では変わらず、統合でsourceが消える場合のみCASCADEで削除される）。

## 5. 検証の基準

| 指標 | 基準 |
| --- | --- |
| 出典検証の正確性 | 実在しない日付を出典とする問題が1件も採用されないこと（単体テストで検証） |
| 1テーマからの生成数 | `quiz.questions_per_theme` 件以内（AIが解析不能な問題を含めて多く返した場合でも、採用数はこの設定を超えない） |
| ダッシュボード初期表示 | 既存の性能要件（2秒以内）を維持すること（AI呼び出しを伴わないことを計測で確認） |
| AI呼び出し失敗時の影響範囲 | ダッシュボード・記録機能に影響しないこと（起動時バッチの例外握り潰しを確認） |

## 5.1 観点別レビュー（コミット前チェック、2026-11-06実施）

`dry-reviewer`・`style-reviewer`・`label-checker`・`injection-reviewer`・`xss-reviewer`・`test-coverage-reviewer`・`performance-reviewer`を並列実行。検出事項と対応:

| # | エージェント | 重要度 | 指摘内容 | 対応 |
| --- | --- | --- | --- | --- |
| 1 | injection-reviewer | **CRITICAL** | `quiz_generation_service._FIELD_PATTERN`の`.+?`連鎖＋`re.DOTALL`によるReDoS（CWE-1333）。実測で入力約1KB・n=16の繰り返しで3.6秒、増加率からn=40〜50（AI応答として非現実的でない量）で数時間停止と推定。発火経路はAI応答（間接プロンプトインジェクション・AIの反復出力故障モードを想定、信頼できない外部入力） | 修正済み：`[^\n]+?`＋`re.DOTALL`除去で構造的に解消、`_MAX_BLOCK_CHARS`（2000字）の多層防御を追加、`_FIELD_PATTERN`→`_QUESTION_BLOCK_PATTERN`に改名。回帰テスト`test_parse_blocks_does_not_hang_on_adversarial_repetition`を追加（1秒以内に完了することを確認） |
| 2 | dry-reviewer | HIGH | `quiz_generation_service._send`と`recap_generation_service._send`がほぼ同一コードを複製（`_ASSISTANT_KEY_BY_CATEGORY`も含む） | 修正済み：`app/services/theme_ai_dispatch.py`を新設し`send_theme_scoped_prompt`に共通化。両ファイルの`_send`は薄いラッパーに縮小 |
| 3 | dry-reviewer | MEDIUM | 「月曜始まりの週開始日」計算が`analytics_service`（新規）・`weekly_summary_service._week_start_of`・`metrics_service._bucket_start`の3箇所に重複 | 部分対応：`weekly_summary_service._week_start_of`を`week_start_of`として公開関数化し、`analytics_service.compute_quiz_accuracy_trend`はこれを呼ぶよう修正。`metrics_service`側の既存重複は本機能のスコープ外として見送り |
| 4 | dry-reviewer | MEDIUM | フロントの`formatAccuracyPercent`が既存`utils/format.ts`の`formatPercent`と同じ計算式を再実装 | 修正済み：`formatAccuracyPercent`は`formatPercent`に委譲するラッパーへ変更 |
| 5 | label-checker | 該当 | `QuizAccuracyTab.tsx`の全角括弧「（」「）」がJSXへ直書き（ゼロハードコーディング違反） | 修正済み：`analytics.quizAccuracy.fractionLabel`をja.json/en.jsonへ追加し置換 |
| 6 | xss-reviewer | MEDIUM | `MarkdownText`の「生HTMLを解釈しないためXSSにならない」という安全性主張に対する回帰テストが無い | 対応済み：`MarkdownText.test.tsx`にXSS回帰テスト2件（`<img onerror>`・`javascript:`リンク）を追加 |
| 7 | test-coverage-reviewer | HIGH | `RecapThemeDetailPage.tsx`のクイズ生成連携（成功/0件/失敗の3分岐）がページファイルのカバレッジ除外設定の陰で実質無検証 | 修正済み：`RecapThemeDetailPage.test.tsx`に3テスト追加（生成成功トースト、0件時トースト、確認キャンセル→実行→失敗時のエラー表示） |
| 8 | test-coverage-reviewer | MEDIUM | 生成数の上限（`question_count`切り詰め）が未検証 | 修正済み：有効ブロック5件→採用3件を確認するテストを追加 |
| 9 | test-coverage-reviewer | MEDIUM | 不正解時の`next_due_date`更新が未検証 | 修正済み：既存テストへアサート追加 |
| 10 | test-coverage-reviewer | MEDIUM | `QuizAccuracyTab`の「trend有り・weak_themes無し」分岐が未検証 | 修正済み：テスト追加 |
| 11 | test-coverage-reviewer | LOW | `DashboardPage`→`QuizTodaySection`の`today_quiz_count`受け渡しの結合テストが無い | 修正済み：`DashboardPage.test.tsx`に2テスト追加 |
| 12 | style-reviewer | LOW | `frontend/src/api/quiz.ts`の`answerQuiz`にJSDocが無く他2関数と不統一 | 修正済み：JSDoc追加 |
| 13 | performance-reviewer | — | 問題なし（N+1なし、AI呼び出しなし）。ダッシュボード応答時間の実測は未実施（コードレビューのみ） | §3.4 V-08（実機確認）で利用者に実測を依頼 |

全修正後、関連テストファイルを再実行し合格・回帰無しを確認済み（§8参照）。ReDoS修正で追加した長さ上限ガード（`_MAX_BLOCK_CHARS`超のブロック破棄）自体のテストが当初漏れていたため（カバレッジ98%で検出）、`test_generate_for_theme_discards_block_exceeding_the_max_length`を追加し100%へ復帰。OSVスキャン（`vuln-scan.sh`）実行、既知の脆弱性0件（新規依存追加なし）。

## 6. 既知のリスクと対策

| リスク | 対策 |
| --- | --- |
| 偽の出典・区切り偽装 | 固定区切り文字での分割＋出典日付の実在検証（チャンク単位の日付集合との照合）。不正な問題は個別破棄 |
| テーマの積み増しによる肥大化 | バッチは未生成テーマのみ対象（D12）。手動の作り直しは既存未出題分を削除してから生成 |
| テーマ変更時に古い内容のクイズが残る | U3・4.5の削除フローで対応。回答履歴は残すため分析の連続性は維持 |
| プロンプト予算超過 | 既存の `RECAP_CLASSIFY_CHUNK_CHARS` によるチャンク化、`build_simple` の `was_truncated` 時は送信中止（既存方針を踏襲） |
| ダッシュボード・記録機能への影響 | AI呼び出しを起動時バッチ・手動操作のみに限定し、`GET /dashboard` 等の初期表示経路には一切含めない（B-09で回帰テスト） |
| `test_desktop_tray.py` の一時的なフレーキー（§2参照） | 本機能とは無関係と判断済み。実装中に再発した場合は原因調査する（ユーザー指示：発見した不具合は本セッションで修正する） |

## 7. 完了の定義

- 全項目（§3）が `[x]` になり、テストが通る（バックエンド・フロントエンドとも）。
- カバレッジは例外処理を除き100%。
- §5の基準を満たすか、未達の場合は理由と対応を §8 に記録する。
- 文書（§1.3）が実装と一致する。
- §2のベースラインと比較し、既存テストが1件も壊れていないこと、テスト件数の増減が意図どおりであることを確認する。

## 8. 作業記録

（作業の進行に応じて追記する）

- 2026-11-06：工程1〜3完了。要件7の前提訂正（U1）・作成タイミング（U2）・テーマ変更時の扱い（U3）・ナレッジエクスポート（U4）を利用者に確認し確定。ベースライン計測のため `dev/2026-10-29`（実DBとマイグレーション不整合により `test_build_package_misc.py` が1件失敗）から `main`（`origin/main` 2.5.0、`fd8470506d29` まで含む）を基点に `dev/2026-11-06` を新規作成。

- 2026-11-06 実施結果（最終）
  - バックエンド全体：2,203件合格、カバレッジ100%（文9,791・分岐1,738、いずれも欠落0）。ruff 0件。
  - フロントエンド全体：182ファイル／1,542件合格、カバレッジ100%（文・分岐・関数・行）。oxlint 0件、`tsc -b` 0件、production build成功（新規ページ・新規ルートを含め1,417モジュール変換、既存のチャンクサイズ警告のみで新規エラーなし）。
  - **レビュー後の追加修正**：要件6（AI未設定時の表示）がダッシュボードの非表示のみでは不十分と判明（`/quiz`へ直接遷移すると意味不明な完了表示が出る不具合）。`QuizPage.tsx`に`useAiConfigured`／`AiUnconfiguredNotice`を追加し修正（F-02参照）。仕様書6.1.6も合わせて修正。
  - OSVスキャン（`vuln-scan.sh`）：既知の脆弱性0件（新規依存ライブラリは追加していない）。
  - 観点別レビュー（§5.1）：dry/style/label/injection/xss/test-coverage/performanceの7エージェントを実行。**CRITICAL 1件（ReDoS、CWE-1333、実測確認）を検出・修正済み**。HIGH 2件（recap/quiz間の`_send`重複→`theme_ai_dispatch.py`へ共通化、フロントのクイズ生成分岐が未テスト→`RecapThemeDetailPage.test.tsx`に3テスト追加）・MEDIUM多数（詳細は§5.1表）も全て対応済み。
  - 実機確認：実サーバ（uvicorn）を実際の利用者DB（`data/michinari.db`）に対して起動し、`GET /dashboard`（`today_quiz_count=0`を確認）・`GET /quiz/today`（`[]`）・`GET /goals/1/recap-themes`（`[]`、まだ振り返りバッチが実行されていないため空が正しい）が正常応答することを確認。フロントエンドはproduction buildの成功のみ確認（ブラウザ操作ツールが本環境に無く、画面を実際にクリックしての確認は未実施）。
  - §2のベースラインとの比較：既存テストは1件も壊れていない（バックエンド2,158→2,203件〈+45、復習クイズの新規テスト〉、フロントエンド1,508→1,541件〈+33〉。いずれも意図どおりの増加）。
  - 残課題：V-08（ブラウザでの実機確認）は利用者に依頼する。具体的な確認手順は本機能の報告メッセージに記載する。「節目のお祝い」への「復習の連続日数」追加（要件5後段、D15で見送り）は本Todoの範囲外として別タスク化を検討。
