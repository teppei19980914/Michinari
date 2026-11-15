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

## 2. 現状のベースライン（開発前、2026-11-15、`dev/2026-11-15`ブランチ）

- バックエンド（`python -m pytest -q --cov-report=term-missing`）：2,293件合格、カバレッジ100%（文9,909・分岐1,800、いずれも欠落0）。`ruff check .` 0件。
- フロントエンド（`npm run test -- --run`）：203ファイル／1,658件合格、カバレッジ100%（文・分岐・関数・行）。`npm run lint`（oxlint）0件。`npx tsc -b` 0件。

## 3. 作業Todo

凡例：`[ ]` 未着手、`[x]` 完了。各項目の完了条件は「テストが通ること」と「カバレッジ100%（例外処理を除く）」。

### 3.A 要件A：単語帳の基盤と問題集（本セッションの対象）

#### 3.A.1 文書改訂
- [ ] A-D01 要件定義書：新節
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

### 3.B 要件B：今日の復習への統合（別セッション）
（着手時に追記）

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
| — | style-reviewer / label-checker / xss-reviewer | — | 指摘なし（命名規則・コメント規約・ハードコード文言・XSS対策のいずれも既存方針に合致） | 対応不要 |

全修正後、関連テストファイルを再実行し合格・回帰無しを確認済み（§8参照）。

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

- 2026-11-15（最終）：全体最終テスト実行。バックエンド2,410件合格／カバレッジ100%（文10,519・分岐1,938、欠落0）、ruff 0件。フロントエンド217ファイル／1,738件合格／カバレッジ100%（文・分岐・関数・行）、oxlint 0件、`tsc -b` 0件。ベースライン（§2）との比較：既存テストは1件も壊れていない（バックエンド+117件、フロントエンド+14ファイル・+80件。いずれも単語帳機能の新規テストによる意図どおりの増加）。以上により、要件Aの完了条件（§7）を満たしたと判断する。要件B〜E（今日の復習統合・AI注入・用語提案・習得可視化）は別セッションで着手する。
