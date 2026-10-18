# 開発Todo：S04 日次報告の共通化・全期間化・縮退順の見直し（G1・G2・G10）

本書は、資格試験・読書・仕事3種別の日次報告フィードバックが送る「過去の記録」の組み立てを
共通化し、全期間を対象とし、縮退順を原則どおりに揃える開発作業の正（Single Source of
Truth）である。作業は `dev/2026-10-11`（現行ブランチ）で行う。版は変更しない
（`pyproject.toml` 2.1.0 のまま）。

## 0. 決定事項

| # | 決定 | 値・根拠 |
| --- | --- | --- |
| D1 | 当日の対話の保護 | 新原則「当日の入力（実績・日記・対話）は縮退の対象にしない」の「対話」は、現行の会話ターントリミング（資格試験`build_daily_feedback`段階3、読書・仕事`build_with_degradable_entries`の履歴トリミング）を廃止することを意味する（利用者確認済み、2026-10-17） |
| D2 | 「切り詰めず送信しない」の適用範囲 | 日次報告3用途（資格・読書・仕事）のみに限定する。共有エンジン`build_with_degradable_entries`自体の既存フォールバック仕様（末尾切り詰め）は変更しない。総括レポート・読了レポート・月次報告・半期評価・AI評価レポートの5用途は現状維持（利用者確認済み） |
| D3 | 不要設定キーの扱い | `summary.inject_weeks`（設定画面表示中）・`ai.reading_recall_recent_days`（API経由のみ）・`ai.work_recent_log_days`（未露出）の3キーを削除する。既存DBに残る値は無害な孤立データとして残し、削除マイグレーションは行わない（利用者確認済み） |
| D4 | 共通処理の形 | `ai_context_common.py`に`PastRecordEntries`（`weekly_summary_entries`・`raw_entries`、いずれも古い順）と`build_past_record_entries(session, goal, period_start, period_end, raw_entries)`を新設する。内部で`resolve_weekly_compressed_period(limit=None)`＋`exclude_covered_dates`を呼ぶだけの薄いラッパーとし、3サービス層（`daily_feedback_service`・`reading_feedback_service`・`work_feedback_service`）の重複呼び出しをこれに統一する（DRY） |
| D5 | 資格試験の新変数（G2対応） | `ai_context_exam.py`に`build_recent_study_entries(session, goal, period_start, period_end) -> list[DatedLogEntry]`を新設する。1日1エントリとし、その日の実績（教材別の完了量・時間・周回・品質指標）と日記（学んだこと・行動所感）を1つのテキストへ結合する（`build_week_logs_text`・`build_week_diaries_text`の日次版に相当、既存の整形方針を踏襲）。テンプレート変数名は`{{recent_logs}}`（読書`recent_recalls`・仕事`recent_work_logs`と同じ命名規則）とし、`DAILY_FEEDBACK`テンプレートへ`# これまでの記録（週次要約が無い日）`の見出しで追加する。本文は利用者レビュー対象として提案値を3-2に記載する |
| D6 | 読書の`period_start`修正 | `reading_feedback_service.py`が`period_start=goal.start_date`を使っているのは誤りで、読了レポート（`retrospective_service.py`）は`book.start_date`を使っている（`book.start_date`は`update_book`で独立に変更可能なため、`goal.start_date`と一致しない場合がある）。本改修で`book.start_date`に統一する |
| D7 | 資格試験の週次要約フロア撤廃 | 現行`build_daily_feedback`段階1の「週次要約は最低1件残す」という下限は、新原則（相当過去の記録が外れることを許容する）と矛盾するため撤廃し、読書・仕事と同じ「0件まで削ってよい」方式に揃える |
| D8 | 資格試験の縮退順 | `build_daily_feedback`の縮退順を「①`weekly_summaries`を古い順に0件まで→②`recent_logs`を古い順に0件まで→③締切が遠い教材の集約表示（現行のまま）→④それでも超える場合は送信しない」に変更する。対話履歴・日記本文の先頭切り詰め（現行段階3・4）は廃止する（D1・D7関連） |
| D9 | 「送信しない」の実現方法 | 共有エンジン`build_with_degradable_entries`自体は変更しない（D2）。代わりに`prompt_builder.py`へ追加専用の事前判定ヘルパー（例：`minimum_chars_with_empty_stages`）を新設し、各サービス層が「全stageを空にしても（当日対話は保持したまま）上限を超えるか」を事前判定してから既存のビルド関数を呼ぶ。超える場合はビルドを呼ばずに新しいドメイン例外`DailyFeedbackPromptTooLongError`（`app/services/exceptions.py`、`RecapPromptTooLongError`と同じ形）を送出し、`api/errors.py`の`_STATUS_AND_CODE`へ`(409, "DAILY_FEEDBACK_PROMPT_TOO_LONG")`を追加する。画面文言は`errors.DAILY_FEEDBACK_PROMPT_TOO_LONG`（ja/en）に新設する（文言案は3-5） |
| D10 | 週次要約の文字数見積り | 一時DBでの実測データが無いため、`weekly_summary`生成プロンプト（`WEEKLY_SUMMARY`系、17.3・17.11・17.12）の要件6項目の記述密度から推定する。**推定・一次ソース未検証**と明記して報告する（3-6） |

## 1. 影響範囲（フルスキャンの結果）

### 1.1 バックエンド

| 領域 | 対象ファイル | 変更の種類 |
| --- | --- | --- |
| 共通処理 | `app/services/ai_context_common.py` | `PastRecordEntries`・`build_past_record_entries`を新設（D4）。既存の`resolve_weekly_compressed_period`・`exclude_covered_dates`は無変更 |
| 資格試験 | `app/services/ai_context_exam.py` | `build_recent_study_entries`を新設（D5）。`build_recent_weekly_summaries`（新しい順・inject_weeks制限版）は呼び出し元が無くなるため削除 |
| 資格試験 | `app/services/daily_feedback_service.py` | `build_past_record_entries`呼び出しへ変更。`period_start=goal.start_date`、`period_end=target_date - 1日`。`SUMMARY_INJECT_WEEKS`参照を削除 |
| 読書 | `app/services/reading_feedback_service.py` | `period_start`を`goal.start_date`→`book.start_date`に修正（D6）。`build_past_record_entries`呼び出しへ統一。`AI_READING_RECALL_RECENT_DAYS`・`SUMMARY_INJECT_WEEKS`参照を削除 |
| 仕事 | `app/services/work_feedback_service.py` | `build_past_record_entries`呼び出しへ統一。`AI_WORK_RECENT_LOG_DAYS`・`SUMMARY_INJECT_WEEKS`参照を削除 |
| プロンプト組み立て | `app/ai/prompt_builder.py` | `build_daily_feedback`：段階1の下限撤廃（D7）、`recent_logs`段階追加、段階3・4（対話・日記トリミング）削除（D8）。`build_with_degradable_entries`：対話履歴トリミングループが読書・仕事以外では常に空リストに対して動作するだけであることを確認しつつ、無変更（D2・D9）。事前判定ヘルパー`minimum_chars_with_empty_stages`等を新設（D9） |
| 例外 | `app/services/exceptions.py` | `DailyFeedbackPromptTooLongError(DomainError)`を新設 |
| API変換 | `app/api/errors.py` | `_STATUS_AND_CODE`へ追加 |
| 設定キー | `app/constants/app_setting_keys.py` | `SUMMARY_INJECT_WEEKS`・`AI_READING_RECALL_RECENT_DAYS`・`AI_WORK_RECENT_LOG_DAYS`の3定数を削除（D3） |
| 設定スキーマ | `app/schemas/setting.py` | `PromptDegradationSettingsRead`/`Update`から`summary_inject_weeks`・`reading_recall_recent_days`を削除 |
| 設定サービス | `app/services/settings_service.py` | `PromptDegradationSettings`・`get_app_settings`・`_update_prompt_degradation`から該当フィールドを削除 |
| 初期データ | `app/init/seed_data.py` | `INITIAL_APP_SETTINGS`から3キーを削除 |
| テンプレート初期データ | `app/init/prompt_texts_exam.py` | `DAILY_FEEDBACK`へ`{{recent_logs}}`セクションを追加（D5） |
| テンプレート投入 | `app/init/seed_data.py`（`INITIAL_PROMPT_TEMPLATES`・既存DBへの不足分投入） | `DAILY_FEEDBACK`の初期文面を更新。既存DBで`is_customized=false`の行のみ新文面へ反映する既存の仕組み（`f7c3e9a1b5d6`と同じ手法）をマイグレーションで実施。`is_customized=true`（利用者編集済み）の行は変更しない（変数が無いままになるが、既存の「編集済みは触らない」方針と同じ） |
| マイグレーション | `backend/alembic/versions/` | 新規1件：`DAILY_FEEDBACK`テンプレート文面の反映（`create_table`なし、データ更新のみ） |

### 1.2 フロントエンド

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| 型生成 | `frontend/src/types/api.d.ts` | `openapi-typescript`で再生成（設定スキーマの2フィールド削除を反映） |
| 設定画面 | `frontend/src/features/settings/PromptDegradationSection.tsx` | `summaryInjectWeeks`の状態・入力欄・送信項目を削除 |
| 文言 | `frontend/src/locales/ja.json`・`en.json` | `settings.promptDegradation.summaryInjectWeeksLabel`を削除。`settings.help.p2`（プロンプト縮退の説明文）の「週次要約をプロンプトに注入する週数」記述を是正。新規`errors.DAILY_FEEDBACK_PROMPT_TOO_LONG`を追加 |
| エラー表示 | 既存の`apiErrorMessage()`機構（`frontend/src/api/client.ts`） | 変更不要（`code`追加で自動解決される設計のため） |

### 1.3 ドキュメント

| 文書 | 変更 |
| --- | --- |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1.md` | 16.5（資格試験の縮退、下限撤廃・recent_logs追加・段階削除）、17.2（`{{recent_logs}}`追加）、17.6・17.8（`period_start`の表現統一）、21.4・22.4（inject_weeks記述の削除）、23章未決事項の更新、改訂履歴追加 |
| `docs/設計書_データ構造編_ミチナリ_v1.1.md` | 設定キー一覧から3キー削除、改訂履歴追加 |
| `docs/仕様書_ミチナリ_v1.1.md` | 設定項目一覧（6.11）から「週次要約の注入週数」を削除、改訂履歴追加 |
| `docs/実装フェーズ分割計画書_ミチナリ_v1.1.md` | Phase 44（本改修）の追加 |
| `docs/OPERATIONS.md` 配下 | 設定キー廃止に伴う記述があれば更新（現時点で既存記述は確認済み、無ければ変更不要） |

### 1.4 既存機能への横展開（同じ問題の有無を確認）

| 項目 | 状況 | 対応 |
| --- | --- | --- |
| `build_with_degradable_entries`の対話履歴トリミング | 読書・仕事の日次報告フィードバックのみが`conversation_history`を非空で渡す（総括レポート等5用途は常に空リスト） | D1・D2により、トリミングループ自体は残すが、事前判定（D9）により日次報告3用途では到達しない設計にする。他5用途への影響なし（空リストに対しては元から無意味） |
| `summary.inject_weeks`依存の他箇所 | 日次報告3用途以外（総括レポート・読了レポート・月次報告・半期評価）は元から`limit=None`で未使用 | 対応不要（確認のみ） |

## 2. 現状のベースライン（2026-10-17、本改修着手前）

- バックエンド：`ruff check backend` 全件合格。`pytest`（`backend`で実行）1845件成功、カバレッジ100%（8156 stmts / 1512 branches、計測対象全ファイル100%）
- フロントエンド：`npm run test`（vitest）155ファイル / 1318件成功、カバレッジ100%（Statements/Branches/Functions/Lines）。`npm run lint`（oxlint）0件。`npx tsc --noEmit`エラー0件
- 既存の失敗：なし（上記いずれも全件成功のため、本改修との区別は不要）

## 3. 作業手順

### 3-1. 共通処理の新設（DRY）
- [x] `ai_context_common.py`に`PastRecordEntries`・`build_past_record_entries`を追加し、テストを追加する
- [x] `ai_context_exam.py`の`build_recent_weekly_summaries`（新しい順、inject_weeks版）を削除し、`build_recent_study_entries`（1日1エントリ版）へ置き換える（3-2で実施。3-3のサービス層更新完了後に呼び出し元が無いことを再確認する）

### 3-2. 資格試験への適用（G2）
- [x] `ai_context_exam.py`に`build_recent_study_entries`を新設する（1日1エントリ、実績＋日記を結合、`DatedLogEntry`で返す）
- [x] `prompt_texts_exam.py`の`DAILY_FEEDBACK`へ`{{recent_logs}}`セクションを追加する（見出し`# これまでの記録（週次要約が無い日）`。設計書17.2への追記は3-8でまとめて行う）
- [x] 既存DBの`is_customized=false`な`DAILY_FEEDBACK`テンプレートへ新文面を反映するAlembicマイグレーション`ca4cefcbe9c4`を追加した（`f7c3e9a1b5d6`と同じ手法）。`test_migration_prompt.py`・`test_seed_data.py`（ハッシュ更新）にテスト追加・反映済み

### 3-3. 3用途共通：全期間化（G1）
- [x] `daily_feedback_service.py`・`reading_feedback_service.py`・`work_feedback_service.py`を`build_past_record_entries`呼び出しへ統一する
- [x] `reading_feedback_service.py`の`period_start`を`book.start_date`に修正する（D6）
- [x] `SUMMARY_INJECT_WEEKS`・`AI_READING_RECALL_RECENT_DAYS`・`AI_WORK_RECENT_LOG_DAYS`の参照をサービス層から削除する（設定キー自体の削除は3-6）

### 3-4. 縮退順の是正（G10）
- [x] `build_daily_feedback`から段階1の下限（最低1件）を撤廃する（D7）
- [x] `build_daily_feedback`に`recent_logs`の縮退段階を追加する
- [x] `build_daily_feedback`の段階3（対話履歴トリミング）・段階4（日記先頭切り詰め）を削除する（D1・D8）

### 3-5. 「切り詰めず送信しない」の実装（D9）
- [x] `prompt_builder.py`に事前判定ヘルパー`exceeds_with_entries_emptied`（`DegradableFeedbackContext`向け）を追加。`DailyFeedbackContext`向けは`build_daily_feedback`自体に`BuildResult.exhausted`フィールドを追加して対応（共有エンジンの契約は変えず、呼び出し元1件のみのため直接拡張）
- [x] `app/services/exceptions.py`に`DailyFeedbackPromptTooLongError`を追加
- [x] `app/api/errors.py`の`_STATUS_AND_CODE`へ`(409, "DAILY_FEEDBACK_PROMPT_TOO_LONG")`を追加
- [x] `ja.json`/`en.json`へ`errors.DAILY_FEEDBACK_PROMPT_TOO_LONG`を追加
- [x] 3サービス層（`daily_feedback_service`・`reading_feedback_service`・`work_feedback_service`）に事前判定→例外送出を組み込む

### 3-6. 不要設定の削除（D3）
- [x] `app_setting_keys.py`・`schemas/setting.py`・`settings_service.py`・`seed_data.py`から3キーを削除
- [x] `PromptDegradationSection.tsx`から`summaryInjectWeeks`関連を削除する
- [x] `openapi-typescript`で型を再生成する
- [x] `ja.json`/`en.json`の`settings.promptDegradation.summaryInjectWeeksLabel`・関連説明文（`settings.help.p2`）を削除・是正する

### 3-7. 週次要約サイズの見積り（実装なし、D10）
- [x] 実測データ（一時DB等）は無いため、`WEEKLY_SUMMARY`系プロンプトの要件項目数から推定した。**以下は推定・一次ソース未検証であることを明記する**：
  - 資格試験`WEEKLY_SUMMARY`（17.3）：必須6項目（学習量と品質の推移・主題と理解度・妨げとなった要因・状態所見・前週からの変化・周回進捗）。各項目1〜2文（日本語40〜80字/文）と仮定すると、1週あたり約500〜900字（中央値約700字）
  - 読書`WEEKLY_SUMMARY_READING`（17.11）・仕事`WEEKLY_SUMMARY_WORK`（17.12）：必須4項目（資格試験より2項目少ない）。同様の仮定で1週あたり約350〜600字（中央値約450字）
  - `ai.max_prompt_chars`既定30,000字に対し、資格試験は30,000÷700≈**43週（約10ヶ月）**、読書・仕事は30,000÷450≈**67週（約15ヶ月）**で週次要約だけで上限に達する計算になる。実際は固定変数（目標情報・当日入力等、数百字程度）と週次要約が無い直近日の生ログも同時に占有するため、到達週数はこれより少なくなる
  - 月単位の要約（階層化）の実装判断はこの見積りを踏まえて人が行う（L2参照、本セッションでは実装しない）

### 3-8. ドキュメント更新
- [x] 設計書 ロジック・プロンプト編（15.3・16.5・17.2・17.6・17.8・21.4・22.4・24章L-12、改48）、データ構造編（5.2、改46）、仕様書（6.11・8.4・8.5、改56）、実装フェーズ分割計画書（Phase44、改25）を更新した。OPERATIONS.mdは該当記述が無かったため変更不要

## 4. テスト計画

3種別（資格・読書・仕事）それぞれについて、以下を網羅する：

- [ ] 週次要約0件・一部の週だけ要約済み・全週要約済み・上限ちょうど・上限超過の5パターン
- [ ] 上限超過時に最も古い記録（週次要約→生ログ）から外れ、当日の入力（実績・日記・対話）が最後まで残ること
- [ ] 当日の入力だけで上限を超える場合に、`DailyFeedbackPromptTooLongError`が送出され、AI呼び出し（`send_and_log`）が行われないこと
- [ ] 週次要約済みの週の生の記録が二重に注入されないこと（既存`exclude_covered_dates`のテストを再利用・拡張）
- [ ] `was_truncated`が`ai_log`と画面の両方に正しく伝わること（縮退が発生したが送信はできたケース）
- [ ] 資格試験：`recent_logs`に実績のみの日・日記のみの日・両方ある日・どちらも無い日（該当日なし）が正しく整形されること
- [ ] 読書：`period_start`が`book.start_date`に修正されたことを確認する回帰テスト（`goal.start_date`と`book.start_date`が異なるケース）
- [ ] 設定削除：`settings_service`・設定APIのテストから3キー関連の記述を削除し、スキーマに存在しないことを確認する
- [ ] マイグレーション：既存データに対する安全性テスト（`CODING_RULES.md`のDBマイグレーション規則に従う。本件は既存行の`UPDATE`のみで列追加は無いため、通常のカバレッジ範囲で対応）

## 5. 未決事項

| # | 内容 | 扱い |
| --- | --- | --- |
| L1 | 3-2の`{{recent_logs}}`新規プロンプト文面（見出し・本文）の最終確定 | 実装時にユーザーレビューを経て確定する（提案値はD5・3-2に記載） |
| L2 | 月単位の要約（階層化）を実装するか | 本セッションでは実装しない（ブリーフ指示どおり）。3-7の見積り結果を踏まえ、別セッションで人が判断する |

## 6. 別件（範囲外で見つけた問題）

| # | 内容 | 対応 |
| --- | --- | --- |
| M1 | `ai.reading_recall_recent_days`は設定スキーマ（API）には存在するが、`PromptDegradationSection.tsx`の画面には表示されていなかった（画面と API の不整合、本改修以前から） | 本改修で該当キー自体を削除するため、不整合は解消される。追加対応不要 |
| M2 | `ai_context_exam.build_week_diaries_text`（週次要約向け、既存・本改修で未変更）は日記を「行動・所感→学んだこと」の順で整形するが、新設`build_recent_study_entries`（日次報告向け、本改修）は「学んだこと→行動・所感」の順にした（`record.py`の既存コメント「学んだことが主」、およびDAILY_FEEDBACKテンプレート自体の変数順と揃えるため）。既存のweek_diaries側の順序は本改修のスコープ外のため変更していないが、2つの整形関数で日記の表示順が異なる状態が残っている（dry-reviewerで指摘） | 対応不要（スコープ外）。将来week_diaries側の順序を見直す際は本件を踏まえる |
| M3 | `prompt_builder.py`に`_NO_WEEKLY_SUMMARIES_TEXT`、`reading_feedback_service.py`・`work_feedback_service.py`に同義の`_NO_OLDER_WEEKLY_SUMMARIES_TEXT`（名前まで完全一致、値も同一）が別々に定義されている（本改修以前から。dry-reviewerで指摘） | 対応不要（スコープ外、既存の重複）。将来この文言を変更する際は3箇所同時に直す必要がある点に留意する |
