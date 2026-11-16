# 開発Todo：単語帳（要件A〜Eの5回に分割、本書は全体の正）

本書は、資格試験の目標に紐づく単語帳機能（要件A：基盤＋AI非依存の問題集／要件B：今日の復習への統合／要件C：日次フィードバック・目標相談への用語注入／要件D：日次報告からの用語提案／要件E：習得の可視化）の開発作業の正（Single Common of Truth）である。各要件は別セッションで、前の要件のPRをmainへマージしてから着手する。
作業は `dev/2026-11-15`（`origin/main` マージ直後）で行う。版数は次回マイナー版を見込むが、`pyproject.toml` の実際の更新は `release.bat` 実行時に行う（開発中は変更しない）。

## 0. 決定事項

### 0.1 利用者に確認し、回答を得て確定した事項

| # | 決定 |
| --- | --- |
| U1 | 単語帳は必ず1つの目標に紐づける。作れるのは資格試験（EXAM）の目標のみ。目標を削除したら、単語帳・カード・解答履歴もすべて削除する（ForeignKey ondelete="CASCADE"）。目標のアーカイブ・中断・完了では削除しない。どの状態の目標でも、閲覧・編集・出題はできる |
| U2 | 単語帳の問題集は単語帳だけを材料にし、AIを使わない（カードをめくる・入力式・ローカルの4択の3形式）。AIで問題を作るのは既存の「今日の復習」だけ（要件B） |
| U3 | AIへの用語注入は資格試験のみ。対象は日次フィードバック（通常・ひとこと）と目標相談（要件C） |
| U4 | 今日の復習との関係：要件Bで、単語帳を今日の復習の問題の材料に加える（日次報告と単語帳から、完全ランダムに出題）。今日の復習での正誤は、単語帳の成績に反映しない。単語帳自体には間隔反復を持たせない |
| U6 | 単語帳の成績は「正答数・誤答数（合計）・正答率・連続誤答数・最終解答日」とする。連続誤答数は、直近の解答から遡って連続して間違えた回数（直近が正解なら0）。いずれも単語帳の問題集での解答だけから集計する |
| U5 | 単語帳は、ナレッジエクスポートの対象に含めない |

### 0.2 実装上の判断（利用者確認は不要な技術的決定。根拠を併記）

| # | 決定 | 理由 |
| --- | --- | --- |
| D1 | テーブルは3つ：`vocab_deck`（デッキ本体、`goal_id`へ直接CASCADE）、`vocab_card`（カード、`deck_id`へCASCADE）、`vocab_answer_log`（単語帳の問題集での解答履歴のみ） | `recap_theme.goal_id`・`milestone.goal_id`と同じ「目標への直接CASCADE」方式（`app/models/recap.py:37`・`app/models/milestone.py:33`）。成績は保存せず`vocab_answer_log`から都度算出するため専用の集計テーブルは作らない |
| D2 | `VocabDeck`/`VocabCard`は`TimestampMixin`（`created_at`/`updated_at`両方）、`VocabAnswerLog`は`CreatedAtMixin`のみ | `app/models/base.py:31`の`TimestampMixin`を使う（`app_setting`/`prompt_template`と同じ組み合わせ）。解答履歴は追記のみで更新されないため`quiz_answer_log`と同じく`CreatedAtMixin`のみで十分 |
| D3 | `vocab_answer_log.mode`は`Enum(VocabQuizMode, native_enum=False, validate_strings=True)` | `app/models/material.py`・`app/models/goal.py`の既存Enum列と同じ書き方（本コードベースの標準） |
| D4 | Alembic head確認時点（2026-11-15）で`0e22c031f0ca`（フルスキャンで確認）。新規テーブルの`create_table`のみのため、CODING_RULES.md「DBマイグレーションのテスト」の除外規定（新規テーブルのみは対象外）に従い、既存データへの安全性テストは追加しない。完了条件の実DB確認（退避コピー＋起動確認）は別途実施する | 復習クイズ（`fa5a81543844_quiz_tables.py`）と同じ判断 |
| D5 | `backup_service.DATA_SCHEMA_VERSION`は現在すでに`"1.8"`（ひとこと記録モード Phase52で導入済み）。利用者の元のプロンプトは「1.7→1.8」としていたが、フルスキャンで実際の値を確認した結果、**`"1.8"→"1.9"`**へ上げ、`_IMPORTABLE_SCHEMA_VERSIONS`に`"1.8"`を追加する | 実装前のフルスキャンで判明した食い違い。既存の版歴と同じ運用（新テーブル追加のたび版を上げる） |
| D6 | 新設する7つの`app_setting`のうち`vocab.term_max_chars`=200・`vocab.meaning_max_chars`=2000はデフォルト値を独自に決定（他5件は利用者プロンプトの既定値をそのまま使用） | `term`は`quick_record.note_max_chars`（200、短い1行相当）、`meaning`は`ai.help_answer_max_chars`・`ai.goal_consultation_answer_max_chars`（いずれも2000、説明文相当）を参考に、既存の同種の上限と揃えた |
| D7 | 新設7設定キーは`quiz.*`と同じ扱い（内部パラメータとしてseedのみ投入し、専用の設定画面UIは追加しない） | `quiz.questions_per_theme`等3件も設定画面に未配線（grep確認済み、既存の既知ギャップ）。利用者プロンプトは要件Aの新設キーについて設定画面配線を明示的に要求していないため、同じ扱いに揃える（CODING_RULES.mdの「画面から変更可能」原則との食い違いは既存ギャップとして許容、将来別Todoで検討） |
| D8 | グローバルナビへの追加（要件6）は本機能が初の採用パターン（復習クイズはダッシュボード経由のみでナビ非掲載） | 利用者プロンプトの明示指示。`GlobalNav.tsx`の`NAV_ITEMS`・`routes.ts`に追加する新規パターンとして実装する |
| D9 | 単語帳タブは資格試験目標の`EXAM_TABS`のみに追加する（READING_TABS/WORK_TABSには追加しない） | U1「作れるのは資格試験の目標のみ」のため。`roadmap`/`goalConsultation`のような全カテゴリ共通タブとは異なる |
| D10 | 入力式解答の判定は`question_safety.normalize_for_match`（NFKC・小文字化・空白除去）を呼んだ後、カタカナ→ひらがな変換を別関数（`vocab_service.normalize_for_vocab_match`）で追加適用する | 利用者プロンプトの明示指示（既存の禁止語判定の正規化挙動を変えないため、拡張は別関数にする） |
| D11 | 4択の誤答選択肢生成の乱数は`random.Random`インスタンスを引数で受け取れるようにし、既定は`random.Random()`（新規シード） | テストで固定可能にする利用者プロンプトの明示指示。既存コードベースに乱数を使う前例は無いため新規パターン |

### 0.3 要件B着手前の確認（2026-11-15、要件Aの完了検証）

要件B着手前に、ソースコード全体と本書を照合し、要件Aが漏れなく完了しているかを検証した。

- **発見した記帳漏れ**：A-D01（要件定義書の新節）が`[ ]`未完了のままだったが、実体（6.23 R-167〜R-176、改訂履歴1.1改57）は2026-11-15に実装済みであることをgrepで確認した。Todoのチェック更新を本セッションで修正した（記帳漏れのみ、実装の漏れではない）。
- 他の全項目（A-D02〜A-V04）は実体が存在することをファイル確認で照合し、§8の2026-11-16記録（別名区切り文字の不具合発見・修正）どおり不具合は1件のみだったことを確認した。追加の不具合・横展開漏れは発見しなかった。
- 以上により、要件Aは完了条件（§7）を満たしていると判断し、要件Bへ着手する。

### 0.4 要件B 実装上の判断（利用者確認は不要な技術的決定。根拠を併記）

| # | 決定 | 理由 |
| --- | --- | --- |
| B-D1 | `AiPurpose.VOCAB_QUIZ_GENERATE`・`ConversationScope.VOCAB_QUIZ_GENERATE`は`enums.py`の`QUIZ_GENERATE`の直後に追加する | 既存の並び（テーマ系の用途を隣接させる、GOAL_CONSULTATION_WORK等と同じ追加チロノジー順）に合わせる |
| B-D2 | プロンプト本文は`prompt_texts_exam.py`に置く（`prompt_texts_common.py`ではない） | 単語帳は資格試験(EXAM)専用（要件A U1）であり、既存の`QUIZ_GENERATE`（EXAM・READING両対応のため`_common`）とは異なりカテゴリ非依存ではない。カテゴリ専用プロンプトは`_exam`/`_reading`/`_work`に置く既存の置き場所ルールに従う |
| B-D3 | ブロック解析の共通化は、新規モジュール`app/services/quiz_block_parsing.py`へ「区切り分割＋5フィールド抽出（出典は生文字列のまま）」を切り出し、`quiz_generation_service._parse_blocks`（テーマ：日付検証）と`vocab_quiz_generation_service`の解析（カードID検証）の両方がこれを呼ぶ方式にする。既存の`quiz_generation_service._MAX_BLOCK_CHARS`・`_send`への外部参照（テストより）はモジュール属性として引き続き解決できるようにする | 利用者プロンプトの明示指示（既存の`_parse_blocks`と共通化してよい、既存テストは変えない）。出典の形式（日付／#カードID）が異なるため、検証そのものは呼び出し側で分離する必要がある |
| B-D4 | テーマ由来の出典解析で、日付変換（`dt.date.fromisoformat`）に`try/except`を追加し、不正な暦日（存在しない月日等）のブロックは個別に破棄する（従来は未捕捉の`ValueError`でその目標の生成全体が失敗していた） | 共通化（B-D3）で出典の正規表現制約を緩めた副作用として必要になった変更。1ブロックの不正でバッチ全体を失敗させない既存方針（D11）に揃える、既存テストに暦日不正のケースは無いため回帰なし |
| B-D5 | 単語帳由来の問題検証で追加する「4択の重複禁止」チェックは、単語帳由来のみに適用し、既存のテーマ由来の解析には追加しない | 利用者プロンプトは単語帳由来の検証基準としてのみ明示。既存のテーマ由来フローへ無関係な検証を追加するのは本Todoのスコープ外（挙動変更は避ける） |
| B-D6 | `quiz_answer_log.vocab_card_id`は利用者指定どおり`ondelete="CASCADE"`（`SET NULL`ではない） | カード削除は利用者の直接操作であり、`VocabAnswerLog.card_id`（要件A）も同じCASCADE方式。テーマの改名・統合・再構築（システム起因の間接的な消失、D4のSET NULL）とは異質で、カードが消えた後に紐づけて保持する対象（単語帳という安定した集計単位）が無いため、要件A内の既存方式に揃える |
| B-D7 | 目標のアーカイブ・削除時の単語帳由来クイズの扱いは、既存のテーマ由来クイズと同じにする：削除はCASCADE連鎖（goal→vocab_deck→vocab_card→quiz_question/quiz_answer_log、既存U1のCASCADEにそのまま乗る）、アーカイブは`get_due_questions`のGoal.status==ACTIVE絞り込みで自然に除外 | 利用者プロンプトの明示指示。既存のテーマ由来（goal→recap_theme→quiz_question CASCADE、ACTIVE絞り込み）と対称的な設計のため、特別な削除フックは不要 |
| B-D8 | 単語帳カードの選択順「チェック付き→新しく登録した順」は`(is_checked DESC, id DESC)`で実装する | 「新しく登録した順」はID昇順（登録順そのまま）ではなく新しい順と解釈（文言どおり）。IDを登録順の代理キーとして使うのは既存方針（カードの`display_order`とは別に、作成の新旧はid大小で判定可能なため追加のタイムスタンプ比較は不要） |
| B-D9 | 起動時バッチでの上限`vocab.quiz_cards_per_startup`（既定20）は、対象ゴール横断の合計件数に対する上限（1回の起動で新規に問題を作るカードの総数が20枚まで）とする。ボタンからの生成は、そのデッキ内で同じ上限（20）を単独に適用する | 利用者プロンプトの理由書き「登録が多いとAIの呼び出しが数百回になるのを防ぐ」は複数デッキ・複数目標を横断した総量の話であり、デッキ単独の上限ではない。ボタンは単一デッキのみが対象のため同じ上限がそのまま単独の上限として働く |
| B-D10 | 一括登録の入力形式「#カードID 用語／意味／別名」で、別名が無いカードは「／別名」部分を省略する（2フィールドのみ）。複数別名は「、」で連結する | 利用者プロンプトに区切り文字の明示が無いため、既存の一括登録プレビュー表示（別名は`|`区切りの入力形式）とは別物として、読みやすい日本語の読点で統一する |
| B-D11 | 参考用語（{{glossary_reference}}）の行フォーマットは「・用語（別名1、別名2）: 意味」。別名が無い場合は「・用語: 意味」（括弧を省略） | 利用者プロンプトの書式「・用語（別名）: 意味」に対し、複数別名時の連結方法とゼロ別名時の省略規則を明確化する必要があったための補足決定 |
| B-D12 | `{{glossary_reference}}`・`{{nonce}}`を追加する`QUIZ_GENERATE`テンプレート改訂は、既存の`{{entries}}`（報告本文）側にはnonce区切りを追加しない（現状維持） | スコープの最小化。報告本文への区切り強化は既存機能（復習クイズ要件A相当）の挙動変更であり、本Todo（単語帳由来の新規データ経路の保護）の範囲外。将来必要なら別Todoで検討する |
| B-D13 | `vocab_quiz_generation_service`の対象は「ACTIVEな資格試験の目標」に限定する（`ai_context_exam.list_active_exam_goals`を再利用、読書は呼ばない） | 単語帳はEXAM専用（要件A U1）であり、vocab_deckがREADING/WORK目標に存在しえないため、カテゴリ絞り込みは安全側の防御的チェックとして追加する（通常は空集合になるだけ） |
| B-D14 | `vocab_service.build_glossary_reference`のカード並び順（デッキ表示順→カード表示順）は固定とし、要件C向けの可変化は行わない。マッチ対象の文章群・文字数予算のみを引数化する | 利用者プロンプトは「カードの選び方（絞り込み・並び順）と文字数の予算を引数で受け取る」よう明示しているが、要件Bの時点では並び順を変える具体的な要求が無いため、過剰な一般化（CLAUDE.md「設計しない」原則）を避け、要件C着手時に必要なら拡張する |



## 1. 影響範囲（フルスキャンの結果）

### 1.1 バックエンド（変更する箇所）

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| 列挙 | `app/constants/enums.py` | `VocabQuizMode`を追加 |
| 設定キー | `app/constants/app_setting_keys.py` | `vocab.*` 7キー追加 |
| 初期データ | `app/init/seed_data.py` | 7キーの既定値投入 |
| モデル | `app/models/vocab.py`（新規） | `VocabDeck`/`VocabCard`/`VocabAnswerLog` |
| マイグレーション | `backend/alembic/versions/`（head=`0e22c031f0ca`） | 新規1ファイル（`create_table`のみ） |
| データ管理 | `app/services/backup_service.py` | `DATA_SCHEMA_VERSION`を1.9へ（D5） |
| ドメイン例外 | `app/services/exceptions.py`・`app/api/errors.py` | `VocabDeckGoalCategoryError`等を追加し`_STATUS_AND_CODE`へ登録 |
| 新規サービス | `app/services/vocab_service.py` | CRUD・一括登録解析・成績集計・出題選択・判定（AI非依存） |
| 新規API | `app/api/vocab.py` + `app/schemas/vocab.py`、`app/main.py`（`include_router`登録） | 追加 |
| テスト | `backend/tests/test_vocab_service.py`・`test_api_vocab.py`・`tests/vocab_helpers.py`（新規） | 追加 |

### 1.2 フロントエンド（変更する箇所）

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| API層 | `src/api/vocab.ts`（新規）、`src/types/api.d.ts`（再生成） | 追加 |
| 機能 | `src/features/vocab/`（新規：一覧・詳細・一括登録・出題） | 追加 |
| ナビ・ルーティング | `src/components/GlobalNav.tsx`・`src/constants/routes.ts` | 追加（D8） |
| 目標詳細 | `src/pages/GoalDetailPage.tsx`（`EXAM_TABS`のみ） | タブ追加（D9） |
| 文言 | `src/locales/ja.json`・`en.json` | 新規`vocab`名前空間 |

### 1.3 ドキュメント（変更する箇所）

| 文書 | 変更 |
| --- | --- |
| `docs/要件定義書_ミチナリ_v1.1.md` | 新節（6.23想定）、改訂履歴 |
| `docs/仕様書_ミチナリ_v1.1/`（画面仕様・設定項目） | 単語帳関連画面、改訂履歴 |
| `docs/設計書_データ構造編_ミチナリ_v1.1/05_テーブル定義/` | `vocab_deck`/`vocab_card`/`vocab_answer_log`、改訂履歴 |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1/` | 出題・判定フロー、STRIDE、改訂履歴 |
| `docs/実装フェーズ分割計画書_ミチナリ_v1.1/` | Phase53、`02_フェーズ一覧.md`更新 |
| `README.md` | 機能一覧への追記 |
| `backend/app/content/help_content.json` | 新規section |

### 1.4 確認だけする箇所（変更不要と確認済み）

| 項目 | 状況 |
| --- | --- |
| `.claude/hooks/*.sh`・`.claude/agents/*.md`・`.claude/settings.json` | すべて汎用（git diff・whole repo基準）。単語帳固有の追加設定は不要（フルスキャン済み） |
| `export_service_common.py`の`ExportSelection` | U5により変更不要 |
| `backup_service.py`の一括保存・復元 | `Base.metadata.sorted_tables`方式のため新規モデルをBaseへ登録するだけで自動対応 |

### 1.5 要件B：影響範囲（フルスキャンの結果、2026-11-15）

#### 1.5.1 バックエンド（変更する箇所）

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| 列挙 | `app/constants/enums.py` | `AiPurpose.VOCAB_QUIZ_GENERATE`・`ConversationScope.VOCAB_QUIZ_GENERATE`を`QUIZ_GENERATE`の直後に追加（B-D1） |
| 設定キー | `app/constants/app_setting_keys.py` | `vocab.quiz_cards_per_startup`・`vocab.quiz_reference_max_chars`の2キー追加 |
| 初期データ | `app/init/seed_data.py`・`app/init/prompt_texts_exam.py` | 2キーの既定値、`VOCAB_QUIZ_GENERATE`テンプレート本文登録 |
| 既存プロンプト改訂 | `app/init/prompt_texts_common.py`の`QUIZ_GENERATE` | `{{glossary_reference}}`・`{{nonce}}`変数を追加（B-U6） |
| モデル | `app/models/quiz.py` | `QuizQuestion.theme_id`/`citation_date`をNULL可、`vocab_card_id`追加（CASCADE、index）、CHECK制約2本。`QuizAnswerLog.theme_id`をNULL可、`vocab_card_id`追加（CASCADE） |
| マイグレーション | `backend/alembic/versions/`（head=`1bd06141379f`） | 新規1ファイル（`batch_alter_table`、既存データ保持テスト対象＝CODING_RULES.md「DBマイグレーションのテスト」適用。`QUIZ_GENERATE`プロンプト本文更新を同梱） |
| 共有化 | `app/services/quiz_block_parsing.py`（新規） | 問題ブロックの区切り分割・5フィールド抽出を共通化（B-D3） |
| 既存サービス改修 | `app/services/quiz_generation_service.py` | `_parse_blocks`を共通モジュール呼び出しへ縮小（出典は日付検証のみ残す、B-D4）。`generate_for_theme`に`nonce`生成・`{{glossary_reference}}`組み立て呼び出しを追加 |
| 既存サービス改修 | `app/services/quiz_service.py` | `get_due_questions`をテーマ・単語帳の両ソース合算＋日付・ID由来ハッシュ順へ変更（既存のdaily_limit挙動は固定テストで確認済みの上で変更）。`record_answer`を`vocab_card_id`を持つ問題にも対応。`delete_questions_for_vocab_card`新設 |
| 既存サービス改修 | `app/services/recap_service.py` | `chunk_by_chars`の型ヒントを`Protocol`（`.text`のみ要求）へ緩め、カード由来の入力でも再利用可能にする |
| 既存サービス改修 | `app/services/vocab_service.py` | `build_glossary_reference`（共通の参考用語組み立て、要件Cでも再利用）、カード編集時のクイズ削除フック呼び出し元（API層から呼ぶため関数自体はquiz_service側） |
| 新規サービス | `app/services/vocab_quiz_generation_service.py` | 対象カード選定（優先順・上限）、AI送信（`theme_ai_dispatch`再利用）、出力解析・検証（形式・出典カードID・選択肢重複・根拠・1カード1問）、保存、`run_all`・`generate_for_deck` |
| API改修 | `app/api/quiz.py`・`app/schemas/quiz.py` | `QuizQuestionRead`に出所種別・単語帳名を追加。`POST /vocab-decks/{deck_id}/quiz/generate`を`app/api/vocab.py`へ追加 |
| API改修 | `app/api/vocab.py` | `update_vocab_card`にクイズ削除フック追加。デッキのクイズ生成エンドポイント追加 |
| 起動時バッチ | `app/main.py`の`run_ai_startup_tasks()` | `quiz_generation_service.run_all`の直後に`vocab_quiz_generation_service.run_all`を追加（B-U5） |
| 分析 | `app/services/analytics_service.py` | 変更不要（`QuizAnswerLog.theme_id`とのINNER JOINのため単語帳由来はそのまま対象外。回帰テストで固定） |
| テスト | `backend/tests/` | `test_vocab_quiz_generation_service.py`・`test_quiz_block_parsing.py`（新規）、既存`test_quiz_service.py`・`test_quiz_generation_service.py`・`test_api_quiz.py`・`test_api_vocab.py`・`test_analytics_service.py`・`test_bootstrap.py`系（マイグレーション安全性）へ追記 |

#### 1.5.2 フロントエンド（変更する箇所）

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| API層 | `src/api/quiz.ts`・`src/types/api.d.ts`（再生成） | 出所種別・単語帳名フィールド追加 |
| 機能 | `src/features/quiz/QuizSession.tsx` | 出所に応じた出典表示切替、単語帳由来なら「単語帳で確認する」リンク |
| 単語帳詳細 | `src/features/vocab/VocabDeckHeader.tsx` | 「今日の復習の問題を作る」ボタン追加（`useAiConfigured`/`AiUnconfiguredNotice`、既存パターン） |
| 文言 | `src/locales/ja.json`・`en.json` | `quiz`名前空間の出所ラベル、`vocab.deckDetail`のボタン文言追加 |

#### 1.5.3 ドキュメント（変更する箇所）

| 文書 | 変更 |
| --- | --- |
| `docs/要件定義書_ミチナリ_v1.1.md` | 6.23節へ要件B（R-177〜）追記、改訂履歴 |
| `docs/仕様書_ミチナリ_v1.1/` | 6.1.6（今日の復習）・6.20（単語帳）・AI連携一覧・設定項目、改訂履歴 |
| `docs/設計書_データ構造編_ミチナリ_v1.1/05_テーブル定義/` | `quiz_question`・`quiz_answer_log`の列変更、改訂履歴 |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1/` | 2つの材料の統合、出典・根拠検証、出題順、STRIDE、改訂履歴 |
| `docs/実装フェーズ分割計画書_ミチナリ_v1.1/` | Phase53の要件B追記（または新規Phase） |
| `README.md` | 単語帳説明への要件B反映 |
| `backend/app/content/help_content.json` | 今日の復習セクションの説明更新 |

#### 1.5.4 確認だけする箇所（変更不要と確認済み）

| 項目 | 状況 |
| --- | --- |
| `app/services/analytics_service.py`のテーマ別正答率集計 | `QuizAnswerLog`と`RecapTheme`のINNER JOINのため、`theme_id`がNULLの単語帳由来の行は自然に対象外（回帰テストで固定） |
| `backup_service.py`の一括保存・復元 | 列追加のみで新規テーブルは無いため、既存の汎用round-trip方式がそのまま対応。`DATA_SCHEMA_VERSION`は要件Aで上げた"1.9"が未リリース（`ver2.10.0`タグ後の未コミット、2026-11-15に本セッションでコミット予定）のため、同じリリースへ含めて据え置く |
| `export_service_*.py` | 単語帳はナレッジエクスポート対象外（要件A U5）のまま変更不要 |

## 2. 現状のベースライン（開発前、2026-11-15、`dev/2026-11-15`ブランチ）

- バックエンド（`python -m pytest -q --cov-report=term-missing`）：2,293件合格、カバレッジ100%（文9,909・分岐1,800、いずれも欠落0）。`ruff check .` 0件。
- フロントエンド（`npm run test -- --run`）：203ファイル／1,658件合格、カバレッジ100%（文・分岐・関数・行）。`npm run lint`（oxlint）0件。`npx tsc -b` 0件。

### 2.1 要件B着手前のベースライン再計測（要件Aマージ後、2026-11-15同日）

- バックエンド（`python -m pytest -q`）：**2,427件合格**、カバレッジ100%（文10,522・分岐1,938、いずれも欠落0）。`ruff check .` 0件。
- フロントエンド（`npm run test -- --run`）：**217ファイル／1,738件合格**、カバレッジ100%（文・分岐・関数・行）。`npm run lint`（oxlint）0件。`npx tsc -b` 0件。
- 要件B完了時はこの2.1の値と比較する（§2の値は要件A着手前のもので、要件Bの比較対象ではない）。

## 3. 作業Todo

凡例：`[ ]` 未着手、`[x]` 完了。各項目の完了条件は「テストが通ること」と「カバレッジ100%（例外処理を除く）」。

### 3.A 要件A：単語帳の基盤と問題集（本セッションの対象）

#### 3.A.1 文書改訂
- [x] A-D01 要件定義書：新節（6.23 R-167〜R-176、改訂履歴1.1改57で2026-11-15に実施済み。Todoのチェック更新漏れを要件B着手前の確認で2026-11-15に修正）
- [x] A-D02 仕様書：3（機能一覧GOL-23）・4（画面一覧SC-22）・6.20（新規、SC-22単語帳）、改訂履歴1.1改69
- [x] A-D03 設計書（ロジック・プロンプト編）：30章新設（単語帳の判定・出題ロジック、処理フロー・STRIDE・検証の基準）、旧30章「未決事項」は31章へ採番替え、改訂履歴1.1改71
- [x] A-D04 設計書（データ構造編）：5.1（VocabQuizMode）・5.2（vocab.*設定キー7件）・5.4（3テーブル定義）・5.6（インデックス）・6（APIエンドポイント一覧・エラーコード3件）、改訂履歴1.1改71
- [x] A-D05 実装フェーズ分割計画書：Phase53、02_フェーズ一覧.md・03/index.md更新、改訂履歴1.1改32
- [x] A-D06 README.md：資格試験セクションへ単語帳の説明を追記
- [x] A-D07 help_content.json：新規section「vocab」（`frontend/src/locales/ja.json`の`help.sections.vocab`が正、`scripts/export_help_content.py`で生成）。既存「目標一覧・目標詳細編集」セクションのタブ数（6→7）も合わせて更新
- [x] A-D08 脅威モデル（STRIDE）実施（設計書30.6に反映。信頼境界・DoS/Tampering対策・既存の単一利用者ローカル運用前提を記載）

#### 3.A.2 バックエンド実装
- [x] A-B01 列挙・設定キーの追加（`VocabQuizMode`、`vocab.*` 7キー）
- [x] A-B02 `vocab_deck`/`vocab_card`/`vocab_answer_log`モデル・マイグレーション（`1bd06141379f`、head=`0e22c031f0ca`から。実DB〈退避コピー〉で適用・起動確認済み）
- [x] A-B03 `backup_service.py`：`DATA_SCHEMA_VERSION` 1.8→1.9へ（当初想定の1.7→1.8ではなく実際値を確認して訂正、§0 D5）
- [x] A-B04 シード：`app_setting`既定値7件
- [x] A-B05 ドメイン例外・エラー変換登録（`VocabDeckGoalCategoryError`等3件、`_STATUS_AND_CODE`へ登録）
- [x] A-B06 `vocab_service.py`：デッキ/カードCRUD・並び替え・チェック切り替え
- [x] A-B07 `vocab_service.py`：一括登録解析（プレビュー→確定）・エクスポート
- [x] A-B08 `vocab_service.py`：成績集計（都度算出、N+1禁止。`compute_card_stats`・`count_cards_by_deck`）
- [x] A-B09 `vocab_service.py`：出題選択（絞り込み・並び順・問題数）
- [x] A-B10 `vocab_service.py`：入力式判定・4択生成
- [x] A-B11 API：`app/api/vocab.py` + `app/schemas/vocab.py`、`main.py`登録（12エンドポイント）
- [x] A-B12 セキュリティテスト：巨大入力・不正行・XSSペイロード・404・カテゴリ拒否・ReDoS回帰（1秒以内）

#### 3.A.3 フロントエンド実装
- [x] A-F01 `api/vocab.ts`、型再生成（`npm run generate:api-types`）
- [x] A-F02 `features/vocab/`：一覧（`VocabDeckListTab.tsx`）・詳細（`VocabDeckHeader.tsx`・`VocabCardList.tsx`・`VocabImportExportPanel.tsx`）
- [x] A-F03 `features/vocab/`：出題セッション（`VocabQuizSetupForm.tsx`・`VocabQuizQuestionView.tsx`・`VocabQuizSummaryView.tsx`・`useVocabQuizSession.ts`、3形式）
- [x] A-F04 グローバルナビ・ルーティング追加（`VocabHomePage.tsx`〈資格試験の目標選択〉、`/vocab`・`/vocab/:deckId`・`/vocab/:deckId/quiz`）
- [x] A-F05 `GoalDetailPage.tsx`：単語帳タブ追加（EXAM_TABSのみ。目標の状態に関わらず常に編集可能、他タブと異なりreadOnlyを渡さない）
- [x] A-F06 `ja.json`/`en.json`：`vocab`名前空間、`help.sections.vocab`
- [x] A-F07 lint・tsc・test（oxlint 0件、tsc 0件、vitest全件合格）

#### 3.A.4 検証
- [x] A-V01 ruff・pytest・vitest（カバレッジ100%。バックエンド2,410件、フロントエンド217ファイル/1,738件）
- [x] A-V02 既存DBからのアップグレード確認（実際の利用者DBを退避コピーし、`alembic upgrade head`→サーバ起動→単語帳作成・一括登録・4択出題・解答・成績反映をAPI経由で実機確認。実DBは一切変更していない〈md5一致確認済み〉）
- [x] A-V03 観点別レビュー（§5.1、7エージェント実施。CRITICAL/HIGH計3件検出・修正済み）
- [x] A-V04 実機確認手順の提示（報告メッセージに記載）

### 3.B 要件B：今日の復習への統合（本セッションの対象）

#### 3.B.0 準備
- [x] B-00 要件Aの完了検証（§0.3）、影響範囲の確定（§1.5）、ベースライン再計測（§2.1）
- [x] B-01 `/threat-model`実施（STRIDE、§5.2へ記録、2026-11-15）

#### 3.B.1 バックエンド実装
- [x] B-B01 列挙・設定キーの追加（`VOCAB_QUIZ_GENERATE`、`vocab.quiz_cards_per_startup`・`vocab.quiz_reference_max_chars`）
- [x] B-B02 `quiz_question`/`quiz_answer_log`のマイグレーション（CHECK制約、`batch_alter_table`、既存データでのupgrade/downgradeテスト、`a0c24f1a0f15`）。`QUIZ_GENERATE`プロンプト本文更新を同梱
- [x] B-B03 `quiz_block_parsing.py`新設（共通ブロック解析）、`quiz_generation_service._parse_blocks`を縮小（既存テスト無変更で合格）
- [x] B-B04 `recap_service.chunk_by_chars`の型ヒントをProtocol化
- [x] B-B05 `vocab_service.build_glossary_reference`（参考用語の共通組み立て関数、テスト11件）
- [ ] B-B06 `vocab_quiz_generation_service.py`：対象カード選定・AI送信・検証・保存・`run_all`/`generate_for_deck`
- [x] B-B07 `quiz_generation_service.generate_for_theme`：nonce生成・`{{glossary_reference}}`注入（テスト3件、DELIMITER_REPLACEMENTS検証含む）
- [x] B-B08 `quiz_service.get_due_questions`：2ソース合算＋日付・ID由来ハッシュ順（テスト6件追加、既存daily_limit挙動は変更なし）
- [x] B-B09 `quiz_service.record_answer`・`delete_questions_for_vocab_card`（テスト2件追加）
- [ ] B-B10 API：`app/api/vocab.py`（デッキのクイズ生成エンドポイント、カード編集時のクイズ削除フック）、`app/schemas/quiz.py`（出所種別・単語帳名）
- [ ] B-B11 `main.py`：起動時バッチへ`vocab_quiz_generation_service.run_all`追加
- [ ] B-B12 セキュリティテスト：実在しないカードID・根拠のない問題・選択肢重複・敵対的な繰り返し入力（1秒以内）・禁止語を含むカードの除外

#### 3.B.2 フロントエンド実装
- [ ] B-F01 `api/quiz.ts`・型再生成（`npm run generate:api-types`）
- [ ] B-F02 `QuizSession.tsx`：出所に応じた出典表示、単語帳由来の「単語帳で確認する」リンク
- [ ] B-F03 `VocabDeckHeader.tsx`：「今日の復習の問題を作る」ボタン
- [ ] B-F04 `ja.json`/`en.json`文言追加
- [ ] B-F05 lint・tsc・test

#### 3.B.3 検証
- [ ] B-V01 ruff・pytest・vitest（カバレッジ100%、§2.1との比較）
- [ ] B-V02 既存DBからのアップグレード確認（実利用者DB退避コピー）
- [ ] B-V03 観点別レビュー（起動条件に該当するエージェントを並列実行）
- [ ] B-V04 実機確認手順の提示

#### 3.B.4 文書改訂
- [ ] B-D01〜D07（§1.5.3の7文書）

### 3.C 要件C：日次フィードバック・目標相談への用語注入（別セッション）
（着手時に追記）

### 3.D 要件D：日次報告からの用語提案（別セッション）
（着手時に追記）

### 3.E 要件E：習得の可視化（別セッション）
（着手時に追記）

## 4. 処理フロー（要件A確定版）

### 4.1 一括登録（貼り付け）
1. 利用者がタブ区切り（無ければカンマ区切り）のテキストを貼り付ける。
2. サーバーは`csv`モジュールで解析し、行ごとに「用語・意味・別名（任意）・補足（任意）」へ分解する。
3. プレビューを返す（取り込む件数・エラー行と理由・デッキ内で用語が重複する行）。重複は正規化（`normalize_for_vocab_match`）後の用語・別名で判定する。
4. 利用者が確定すると、重複・エラー行を除いた分を`vocab_card`へ登録し、重複件数を返す。`vocab.import_max_rows`を超える行は拒否する。

### 4.2 出題（問題集）
1. 利用者がデッキ画面で出題形式・絞り込み・並び順・問題数を選ぶ。
2. サーバーは絞り込み・並び順に従いカードを選定し、形式に応じた出題データ（4択は選択肢カードIDを含む）を返す。セッション自体は保存しない。
3. 解答ごとに`vocab_answer_log`へ1行追加する。入力式はサーバー側で正規化後に判定、4択は選んだ選択肢カードIDと出題カードIDの一致で判定、カードめくりは自己判定を受け取る。

### 4.3 成績集計
1. `vocab_answer_log`をカード単位でGROUP BY集計し、正答数・誤答数・正答率を算出する。
2. 連続誤答数は`answered_at`・`id`順に解答を並べ、直近から遡って不正解が連続する件数を数える（ウィンドウ関数またはPython側での1回の走査）。
3. 1回のクエリで全カード分をまとめて算出し、N+1を禁止する。

## 5. 検証の基準

| 指標 | 基準 |
| --- | --- |
| 一括登録の安全性 | `vocab.import_max_rows`超の行・巨大行・XSSペイロードを含む行が拒否またはプレーンテキストとして安全に扱われること |
| 所有関係の検証 | 他目標のデッキ・カードへの操作が404になること |
| カテゴリ制約 | 資格試験以外の目標への単語帳作成が拒否されること |
| 成績集計のN+1 | 1クエリでの一括集計（EXPLAINまたはクエリ発行回数のテストで確認） |
| ダッシュボード等既存機能への影響 | 既存のAPI応答・テストに変化が無いこと |

## 5.1 観点別レビュー（コミット前チェック、2026-11-15実施）

`dry-reviewer`・`style-reviewer`・`label-checker`・`injection-reviewer`・`xss-reviewer`・`test-coverage-reviewer`・`performance-reviewer`を並列実行（レート制限により一時中断、復帰後に全件完了）。検出事項と対応:

| # | エージェント | 重要度 | 指摘内容 | 対応 |
| --- | --- | --- | --- | --- |
| 1 | injection-reviewer | **HIGH** | `confirm_bulk_import`（一括登録確定API）が`parse_bulk_import`（プレビュー）の検証結果を信頼する前提で、行数上限（`vocab.import_max_rows`）・文字数上限（`vocab.term_max_chars`/`vocab.meaning_max_chars`）を一切再検証しておらず、プレビューを経由せず確定APIへ直接送ることでこれらを完全に回避できた（リソース枯渇攻撃が可能） | 修正済み：`confirm_bulk_import`内で行数・各行の文字数を再検証するよう変更（信頼境界をクライアントで止めない）。回帰テスト2件を追加 |
| 2 | performance-reviewer | HIGH | `list_vocab_decks`（単語帳一覧API）が、各デッキの`card_count`取得のため`_deck_read`内でデッキ件数分のクエリを発行するN+1 | 修正済み：`vocab_service.count_cards_by_deck`（1回のGROUP BY集計）を新設し、`_deck_read`はカード件数を引数で受け取る方式へ変更。単体テスト・複数デッキでのAPIテストを追加 |
| 3 | dry-reviewer | HIGH | フロントの絞り込みキー配列（`'ALL'`等6値）が`VocabCardList.tsx`・`VocabQuizSetupForm.tsx`の2箇所に同一内容で直書き | 修正済み：`frontend/src/features/vocab/vocabCardFilters.ts`を新設し両ファイルから共通利用 |
| 4 | dry-reviewer | HIGH | `isLastQuestion`/`nextIndex`が既存の復習クイズ（`quizProgress.ts`）と完全に同一のロジックで再実装されていた | 修正済み：`frontend/src/utils/sessionProgress.ts`へ切り出し、`quizProgress.ts`・`vocabQuizProgress.ts`の両方がre-exportする方式へ変更（既存の呼び出し元・テストへの影響なし） |
| 5 | dry-reviewer | MEDIUM | デッキ・カードの表示順採番が`len(既存件数)`方式で、中間の行を削除した後に追加した行が既存の`display_order`と衝突しうる（`material_service`の`max+1`方式と異なる） | 修正済み：`vocab_service._next_display_order`（デッキ用）、カード側は既にフェッチ済みの一覧から`max+1`を算出する方式に変更。衝突しないことを確認する回帰テストを追加 |
| 6 | performance-reviewer | LOW | `create_card`/`confirm_bulk_import`が容量チェックと採番のため同じデッキの全カードを2回フェッチ | 修正済み：1回のフェッチ結果を両方に再利用する方式へ変更（上記5の修正と同時に対応） |
| 7 | test-coverage-reviewer | MEDIUM | 上限ちょうどの境界（デッキのカード数上限・一括登録の行数上限・出題の問題数上限）が「超過」側しか検証されておらず、`>`/`>=`取り違いを検知できない | 修正済み：ちょうど上限で成功する境界テストを4件追加 |
| 8 | test-coverage-reviewer | MEDIUM | `question_count`の下限（0・負数）側が未検証（`or`条件の片方のみ） | 修正済み：`question_count=0`で400になるテストを追加 |
| 9 | test-coverage-reviewer | MEDIUM | 他デッキのカードが、カード一覧・4択の誤答選択肢に混入しないことの検証が無い | 修正済み：クロスデッキ分離のAPIテストを2件追加 |
| 10 | test-coverage-reviewer | LOW | `judge_typed_answer`がカタカナ用語→ひらがな回答の一方向しか検証されていない | 修正済み：逆方向（ひらがな用語→カタカナ回答）のテストを追加 |
| 11 | test-coverage-reviewer | LOW | 書き出し（export）のテストがダウンロードされるBlobの本文内容を検証していない（ファイル名のみ） | 修正済み：Blob本文をアサートするよう修正 |
| 12 | test-coverage-reviewer | LOW | テストヘルパー`make_answer_log`が未使用 | 対応済み：`compute_card_stats`のタイムスタンプ同時刻タイブレーク（CODING_RULES.md「タイムスタンプでの並び替え」）の回帰テストで活用 |
| 13 | 利用者依頼の再フルスキャン（2026-11-16） | **HIGH** | 一括登録の別名欄は利用者プロンプトの明示指示で`|`区切りだが、保存形式（改行区切り、`judge_typed_answer`が`splitlines()`で読む）への変換を行っておらず、一括登録した複数別名が入力式判定で1本の文字列としてしか一致しなかった。既存テストは別名1件のみのケースしか検証しておらず検出されなかった | 修正済み：`vocab_service._parse_import_aliases`を新設し`|`→改行へ変換。一括登録→入力式判定の通し動作確認テスト2件を追加 |
| — | style-reviewer / label-checker / xss-reviewer | — | 指摘なし（命名規則・コメント規約・ハードコード文言・XSS対策のいずれも既存方針に合致） | 対応不要 |

全修正後、関連テストファイルを再実行し合格・回帰無しを確認済み（§8参照）。

## 5.2 脅威モデル（STRIDE、要件B、`/threat-model`実施、2026-11-15）

要件Bは既存の`quiz_question`/`quiz_answer_log`テーブルを変更し、利用者が登録した単語帳カード（用語・意味・別名、自由入力）を初めてAIへ送る新たな用途（単語帳由来のクイズ生成、テーマ由来クイズ生成への参考用語注入）を作るため、実装前に本分析を行う。

### データフロー

```
[起動時バッチ main.run_ai_startup_tasks] ─┐
[単語帳詳細「今日の復習の問題を作る」ボタン] ─┤→ [vocab_quiz_generation_service] → カード選定
                                              （ACTIVE資格試験の目標、use_in_ai=True、未生成）
                                                      ↓
                                        chunk_by_chars（文字数予算） → 1チャンクごとに
                                        禁止語を含むカードを除外 → DELIMITER_REPLACEMENTS変換
                                        → nonceで区切り → theme_ai_dispatch.send_theme_scoped_prompt
                                        （既存の週次要約用アシスタント、信頼境界：ローカルアプリ→外部AI基盤）
                                                      ↓
                                        AI応答 → quiz_block_parsing（形式検証）
                                        → 出典カードID実在検証・選択肢重複検証・根拠検証・1カード1問
                                                      ↓
                                        quiz_question（vocab_card_id）へ保存

[既存：quiz_generation_service.generate_for_theme] → {{glossary_reference}}として同じ変換・nonce区切りで
  単語帳カードの用語・意味をテーマ生成プロンプトへ注入（既存のentries/theme_bodyの経路は変更しない）

[GET /quiz/today] → quiz_service.get_due_questions（テーマ由来＋単語帳由来を合算、日付+ID由来ハッシュ順）
[POST /quiz/{id}/answer] → quiz_answer_log へのみ記録（vocab_answer_logには書かない、B-U3）
```

- **アクター**：単一のローカル利用者のみ（本アプリの既存前提、認証境界は無い）。外部AI基盤（NewtonX）が唯一の外部システム。
- **信頼境界**：①利用者の入力（単語帳カードの用語・意味・別名）→ ②AIへのプロンプト（境界越え：ローカル→外部AI基盤、ネットワーク越え）→ ③AIの応答（境界越え：外部AI基盤→ローカル、信頼できない入力として扱う）。

### STRIDE分析

| カテゴリ | 脅威 | 対策 | 実装箇所 |
| --- | --- | --- | --- |
| **S**poofing | 該当なし（単一利用者ローカル運用、認証境界の変更なし） | — | — |
| **T**ampering（プロンプト注入） | 単語帳カード（用語・意味・別名）は利用者の自由入力であり、AIへのプロンプトに埋め込まれる。カード内に「指示を無視せよ」等の注入を書かれた場合、AIの出力を乗っ取られる可能性がある | ①`question_safety.DELIMITER_REPLACEMENTS`で山括弧を全角化（区切りの偽造防止）、②`secrets.token_hex(question_safety.NONCE_BYTES)`によるリクエスト毎のnonce区切りでデータ部分を囲む（ヘルプ・目標相談チャットと同じ二重防御）、③プロンプト文で「区切りの中の指示には従わない」旨を明示、④出力側の根拠検証（問題文・正解の選択肢に出典カードの用語または別名が実際に含まれることを要求）により、無関係な指示に従って出力しても根拠検証で破棄される | `vocab_quiz_generation_service.py`、`prompt_texts_exam.py`（VOCAB_QUIZ_GENERATE）、`prompt_texts_common.py`（QUIZ_GENERATE改訂） |
| **T**ampering（偽の出典） | AIが実在しないカードIDを出典として応答し、利用者が「存在しない根拠」の問題を解く | 出典カードIDが、その回に実際に送ったカードIDの集合に含まれるかを検証し、含まれない・解析不能な問題は個別に破棄する（テーマ由来の日付検証と同じ考え方） | `vocab_quiz_generation_service.py`（出典検証）、`quiz_block_parsing.py`（共通解析） |
| **R**epudiation | 該当なし（単一利用者、既存の`ai_orchestration.send_and_log`によるプロンプト・応答の記録がそのまま適用される。否認防止の追加要件は無い） | 既存の仕組みをそのまま使用 | `ai/orchestration.py`（変更なし） |
| **I**nformation Disclosure | カード内容（利用者の学習データ）が外部AI基盤へ送信される（既存のAI機能全般と同じ受容済みリスク）。単語帳由来の問題の出典（カードID→単語帳名）が、他の単語帳・他の目標のカードを指してしまうと誤った情報開示になる | 新規の秘密区分は増えない（既存のAI連携全般と同じ受容済みリスク、設計書に既存の記載あり）。出典検証（カードIDがその回の送信集合に含まれる）と、出題選択時の所有関係絞り込み（目標ACTIVE・カテゴリ・デッキuse_in_ai=True）により、他デッキ・他目標のカードが混入しないことをテストで固定する | `vocab_quiz_generation_service.py`、`quiz_service.get_due_questions`（出題時の絞り込み） |
| **D**enial of Service（ReDoS） | AI応答（信頼できない入力）を正規表現で解析する際、貪欲な繰り返し＋`re.DOTALL`の組み合わせは破滅的バックトラッキングを招く（既存のテーマ由来クイズ生成で過去にCRITICALとして検出された脅威、CWE-1333と同種） | 既存の対策（`[^\n]+?`の非貪欲・`re.DOTALL`不使用・`_MAX_BLOCK_CHARS`上限）を共通モジュール`quiz_block_parsing.py`へそのまま引き継ぎ、単語帳由来の解析にも適用する。敵対的な繰り返し入力で1秒以内に完了することをテストで確認する | `quiz_block_parsing.py` |
| **D**enial of Service（AI呼び出し量） | 単語帳の登録件数が多い利用者で、起動のたびに大量のAI呼び出し・プロンプト送信が発生しうる | `vocab.quiz_cards_per_startup`（既定20）で1回の起動あたりの新規生成カード数を上限化。`chunk_by_chars`による文字数予算チャンク化（既存のテーマ生成と同方式）。バッチは「まだ問題を持たないカード」のみを対象とし、積み増しを防ぐ（既存のテーマ生成のD12と同じ考え方） | `vocab_quiz_generation_service.py`、`app_setting`（`vocab.quiz_cards_per_startup`） |
| **D**enial of Service（起動停止） | AI呼び出し失敗（ネットワーク不通・レート制限等）が起動処理全体を止める | 既存の`run_all`と同方式（目標単位でtry/except、1件の失敗が他目標・他の起動処理を止めない）をそのまま適用 | `vocab_quiz_generation_service.run_all` |
| **E**levation of Privilege | 他目標・他デッキのカードが、出題（`GET /quiz/today`）や生成時の参考用語（`{{glossary_reference}}`）に混入する。`use_in_ai=False`に変更したデッキのカードが出題され続ける | 出題クエリ（`quiz_service.get_due_questions`）・生成クエリ（`vocab_quiz_generation_service`）・参考用語組み立て（`vocab_service.build_glossary_reference`）のいずれも、クエリ時点で`VocabDeck.use_in_ai == True`・`Goal.status == ACTIVE`・`Goal.category == EXAM`を再検証する（生成時にtrueだったことをキャッシュしない）。クロスデッキ・クロス目標の混入が無いことをテストで固定する | `quiz_service.py`、`vocab_quiz_generation_service.py`、`vocab_service.py` |

### 受容したリスク

- 単語帳カードの内容が外部AI基盤（NewtonX）へ送信されること自体は、既存の全AI機能（日記・報告本文等）と同じ受容済みリスクであり、本機能固有の追加リスクではない。単一利用者ローカル運用のため、他者への情報漏洩経路は存在しない。
- 既存のテーマ由来クイズ生成の`{{entries}}`（報告本文）には、本Todoではnonce区切りを追加しない（B-D12、スコープの最小化。将来必要なら別Todoで検討）。

### 設計書への反映
STRIDE分析は`docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1/`の該当章（単語帳由来の出題ロジック改訂）へ転記する（文書改訂B-D01〜D07で実施）。

## 6. 既知のリスクと対策

| リスク | 対策 |
| --- | --- |
| 一括登録での巨大入力・ReDoS | `csv`モジュール（正規表現連鎖なし）を使用。行数・文字数は`app_setting`で制限し、確定API（プレビュー経由以外の直接呼び出しを含む）でも再検証する（§5.1 #1） |
| 他目標のリソースへの不正操作 | 全操作でgoal_id/deck_id/card_idの所有関係を検証し404化。4択の誤答選択肢も単一デッキ内に限定（§5.1 #9で回帰確認） |
| 用語・意味のXSS | プレーンテキスト表示のみ、生HTMLを解釈する仕組みを使わない（xss-reviewerで確認済み） |
| DATA_SCHEMA_VERSIONの食い違い | フルスキャンで実際値を確認し1.9へ正しく更新（D5） |
| デッキ一覧のN+1・表示順の衝突 | performance-reviewer・dry-reviewerで検出し修正済み（§5.1 #2・#5） |

## 7. 完了の定義

- §3.A（要件A）が全て`[x]`になり、バックエンド・フロントエンドともテストが通る。→ 達成
- カバレッジは例外処理を除き100%。→ 達成（バックエンド100%、フロントエンド100%）
- §5の基準を満たすか、未達の場合は理由と対応を§8に記録する。→ 達成
- 文書（§1.3）が実装と一致する。→ 達成
- §2のベースラインと比較し、既存テストが1件も壊れていないこと。→ 達成（後述§8参照）

## 8. 作業記録

- 2026-11-15：要件Aの開発着手。フルスキャン（4系統の調査エージェント＋直接のファイル確認）を実施し、復習クイズ（Phase49）を最も近い前例として本文書を作成。フルスキャンにより2点の食い違いを発見：①`DATA_SCHEMA_VERSION`は提示時点で既に"1.8"（ひとこと記録モードで導入済み）のため1.9へ上げる（D5）②`quiz.*`設定キーは設定画面未配線の既知ギャップがあり、新設の`vocab.*`も同様の扱いとする（D7）。いずれも利用者へ報告済み。ベースライン計測：バックエンド2,293件／カバレッジ100%／ruff 0件、フロントエンド203ファイル・1,658件／カバレッジ100%／oxlint・tsc 0件。

- 2026-11-15（続き）：バックエンド（モデル・マイグレーション・サービス層・API層）、フロントエンド（API層・単語帳機能一式・グローバルナビ・目標詳細タブ）を実装。カード単体の並び替え（ドラッグ等によるdisplay_order変更）は要件に明記が無いため見送り、実装していた`reorder_cards`相当のバックエンド機能・テスト・フロントAPIを削除した（スコープの過剰実装、§0.2相当の判断）。

- 2026-11-15（続き）：コミット前チェックとして観点別レビュー7エージェントを並列実行（詳細は§5.1）。HIGH 3件・MEDIUM 4件・LOW 5件を検出し、全て修正済み。特にinjection-reviewerが検出した「一括登録確定APIがプレビューの検証を信頼し、直接呼び出しで文字数・行数制限を回避できる」問題は要件Aの安全性に直結するため優先的に対応した。

- 2026-11-15（続き）：実際の利用者DB（`data/michinari.db`）をスクラッチパッドへ退避コピーし、コピー上でマイグレーション（`0e22c031f0ca`→`1bd06141379f`）を適用。実サーバ（uvicorn、別ポート）を起動し、`GET /health`・`GET /dashboard`・単語帳の作成→一括登録（プレビュー→確定）→4択出題開始→解答→成績反映、をAPI経由で確認。実DBは一切変更していないことをmd5チェックサムで確認済み。

- 2026-11-15（最終）：全体最終テスト実行。バックエンド2,425件合格／カバレッジ100%（文10,519・分岐1,938、欠落0）、ruff 0件。フロントエンド217ファイル／1,738件合格／カバレッジ100%（文・分岐・関数・行）、oxlint 0件、`tsc -b` 0件。ベースライン（§2）との比較：既存テストは1件も壊れていない（バックエンド+132件、フロントエンド+14ファイル・+80件。いずれも単語帳機能の新規テストによる意図どおりの増加）。

- 2026-11-16：利用者の依頼により再フルスキャンを実施し、元の要件（決定事項・機能一覧・新規app_setting・完了条件）と実装を1件ずつ照合した。**不具合を1件検出**：一括登録（貼り付け）の別名欄は利用者プロンプトの明示指示で`|`区切りだが、保存形式（`judge_typed_answer`が`splitlines()`で読む改行区切り）への変換を行っていなかった（既存テストは別名1件のみのケースで、複数別名の分割を検証していなかったため検出されなかった）。`vocab_service._parse_import_aliases`を新設して修正し、一括登録→入力式判定の通し動作確認テスト2件を追加（`test_parse_bulk_import_converts_pipe_separated_aliases_to_newline_separated`・`test_bulk_imported_alias_matches_in_typed_answer_judging`）。他の決定事項・機能・設定項目・完了条件は実装と一致していることを確認し、デグレ・横展開漏れは検出されなかった。修正後、バックエンド全件再実行（2,425件合格、カバレッジ100%、ruff 0件）。以上により、要件Aの完了条件（§7）を満たしたと判断する。要件B〜E（今日の復習統合・AI注入・用語提案・習得可視化）は別セッションで着手する。
