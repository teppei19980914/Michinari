# 開発Todo：S07 長期レポートの補完と要約の適用（G6・G7）

本書は、資格試験の総括レポート（G6）に週次要約が無い過去日の生ログを補う改修と、仕事のAI評価レポート（G7）の業務記録を週次要約で圧縮する改修を行う作業の正（Single Source of Truth）である。版番号（`pyproject.toml`）は変更しない（リリース手順で入力する）。

## 0. 決定事項

| # | 決定 | 根拠 |
| --- | --- | --- |
| D1 | G6：新変数の名称・対象期間 | `GOAL_RETROSPECTIVE`に`{{recent_logs}}`を追加する。対象期間は`goal.start_date`〜生成時点（`today`）の全期間（読書の読了レポートが`book.start_date`〜`today`を使うのと同じ考え方、CLAUDE.md DRYの原則）。実績・日記の整形は既存の`ai_context_exam.build_recent_study_entries`（DAILY_FEEDBACKのS04 G2で新設済み）をそのまま再利用し、新規関数は作らない |
| D2 | G6：テンプレート変数追加の方式 | `f7c3e9a1b5d6`（weekly_summaries追加）・`ca4cefcbe9c4`（recent_logs追加）と同じ方式を踏襲する：新規Alembicマイグレーションで`is_customized=False`（利用者が未編集）の行のみ本文を更新し、編集済みテンプレートは上書きしない（`{{recent_logs}}`は注入されないまま残る＝既存挙動を壊さない）。`app/init/prompt_texts_exam.py`のINITIAL定数も合わせて更新し、新規インストールのシードにも反映する |
| D3 | G7：段階的縮退の構成 | `work_evaluation_service.generate_evaluation_report`の`stages`を`[feedback_history, work_logs]`の2段から`[feedback_history, weekly_summaries(work), work_logs(raw)]`の3段へ変更する。`work_logs`の圧縮は`ai_context_common.resolve_weekly_compressed_period`＋`exclude_covered_dates`を使い、`work_report_service.generate_monthly_report`と同じ配線にする（period_start=`work_assignment.start_date`、period_end=`today`） |
| D4 | G7：縮退の優先順位 | 利用者確認済み（2026-10-19、AskUserQuestion）：**履歴（feedback_history）→業務記録の週次要約→業務記録の生ログ**の順に外す。現行コード（履歴を業務記録より先に全て外す）の優先順位をそのまま踏襲し、業務記録（週次要約・生ログとも）を履歴より長く保持する |
| D5 | G7：設計書17.13の既存記載の扱い | 17.13には「評価レポートは低頻度生成であり、月次報告・半期評価のような最大6ヶ月分の生ログ注入という規模には至らないため、L-11の圧縮層を導入する必要性が薄い」という2026-09-23時点の設計判断が明記されている（`docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1/17_プロンプト設計/17.13_AI評価レポート.md:16`）。しかし評価レポートの対象期間は`work_assignment.start_date`〜生成時点の**全期間**で上限が無く、月次報告（最大1ヶ月）・半期評価（最大6ヶ月）と異なり案件が長期化するほど生ログが際限なく増える。この前提の変化により既存判断を見直し、17.13の当該記述を本改修の内容・理由に置き換える（決定事項として明記し、利用者への質問は行わない。本セッションの指示書で明示的に依頼された変更のため） |
| D6 | 共通定数の集約 | `_NO_WEEKLY_SUMMARIES_TEXT`（文言「（週次要約はありません）」）が`retrospective_service.py`・`work_report_service.py`の2箇所に同一内容で重複済み。本改修で`work_evaluation_service.py`に3箇所目を作ると更にDRY違反が拡大するため、`ai_context_common.py`へ公開定数`NO_WEEKLY_SUMMARIES_TEXT`として集約し、3ファイルとも参照に置き換える |
| D7 | 月次報告・半期評価（work_report_service.py） | フルスキャンの結果、既に原則通り（`resolve_weekly_compressed_period`＋`exclude_covered_dates`）実装済みであることを確認した。差分なし、ロジック変更は行わない（D6の定数参照統一のみ行う） |
| D8 | バージョン | `pyproject.toml`は変更しない（リリース手順`release.bat`で入力する） |

## 1. 影響範囲（フルスキャンの結果）

### 1.1 バックエンド

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| 共通定数 | `app/services/ai_context_common.py` | 公開定数`NO_WEEKLY_SUMMARIES_TEXT`を新設（D6） |
| 資格の総括レポート | `app/services/retrospective_service.py`（`_build_exam_context`） | `recent_logs`ステージを追加（D1）。ローカル`_NO_WEEKLY_SUMMARIES_TEXT`を共通定数参照に置換（D6） |
| 月次報告・半期評価 | `app/services/work_report_service.py` | ローカル`_NO_WEEKLY_SUMMARIES_TEXT`を共通定数参照に置換のみ（D6・D7、ロジックは変更なし） |
| 仕事のAI評価レポート | `app/services/work_evaluation_service.py`（`generate_evaluation_report`） | `stages`を3段化（D3・D4）。`ai_context_common`のインポート追加 |
| 初期文面（資格） | `app/init/prompt_texts_exam.py`（`GOAL_RETROSPECTIVE`） | `{{recent_logs}}`セクションを追加（D1・D2） |
| 初期文面（仕事） | `app/init/prompt_texts_work.py`（`EVALUATION_REPORT_WORK`） | `{{weekly_summaries}}`セクションを追加（D3） |
| マイグレーション | `backend/alembic/versions/`（head=`ca4cefcbe9c4`） | 新規1件：`GOAL_RETROSPECTIVE`・`EVALUATION_REPORT_WORK`の`prompt_template.body`を更新（`is_customized=False`行のみ、`f7c3e9a1b5d6`と同様に複数purposeを1マイグレーションで扱う） |
| 影響なし（既存関数の再利用のみ） | `app/services/ai_context_exam.py`（`build_recent_study_entries`）、`app/services/ai_context_work.py`（`build_work_logs_entries_for_period`） | 変更なし |
| テスト | `backend/tests/test_migration_prompt.py`・`test_api_closure.py`・`test_work_evaluation_service.py`・既存テストの定数参照先確認 | 新規・既存改修（§3.3） |

### 1.2 フロントエンド

変更なし（本改修はサーバ内部のプロンプト組み立てのみを対象とし、API・画面の入出力は変わらない）。

### 1.3 ドキュメント

| 文書 | 変更 |
| --- | --- |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1/17_プロンプト設計/17.5_総括レポート.md` | 注入する変数表に`{{recent_logs}}`追加、初期文面更新、縮退段階の説明を改訂 |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1/17_プロンプト設計/17.13_AI評価レポート.md` | 注入する変数表に`{{weekly_summaries}}`追加、初期文面更新、縮退段階の説明を「履歴→週次要約→生ログ」の3段に改訂し、L-11の圧縮層を見送った旧記載をD5の理由に置き換え |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1.md` | 改訂履歴（改51）、24章にL-15を新設 |
| `docs/設計書_データ構造編_ミチナリ_v1.1.md`・`05_テーブル定義/5.5_AI連携系.md` | 確認の結果、`prompt_template`の変数名一覧やスキーマは保持しておらず影響なし（grep確認済み、§1.4参照）。改訂不要 |
| `docs/OPERATIONS.md`関連・`README.md` | 確認の結果、該当する記載なし（grep確認済み）。改訂不要 |
| `docs/要件定義書_ミチナリ_v1.1.md`・`docs/仕様書_ミチナリ_v1.1.md` | 利用者向けの要求・画面仕様に変更はないため改訂不要（S04〜S06の内部改善と同じ扱い） |

### 1.4 既存機能への横展開（同じ問題の有無を確認）

| 項目 | 状況 | 対応 |
| --- | --- | --- |
| 読書の読了レポート（`_build_reading_context`） | 既に`resolve_weekly_compressed_period`＋`exclude_covered_dates`で週次要約・生ログの2段を実装済み（G6実装の手本） | 対応不要 |
| 月次報告・半期評価（`work_report_service.py`） | 既に原則通り実装済み（D7で確認） | 対応不要 |
| 日次報告フィードバック3種（資格・読書・仕事） | S04（日次報告の共通化・全期間化・縮退順の見直し）で既に対応済み | 対応不要（本改修の対象外） |
| `_NO_WEEKLY_SUMMARIES_TEXT`の重複 | `retrospective_service.py`・`work_report_service.py`に既存重複あり（D6で発見） | 本改修で`ai_context_common.py`へ集約し解消する |
| `prompt_template`の変数名一覧をデータ構造編が保持しているか | `05_テーブル定義/5.5_AI連携系.md`をgrep確認した結果、変数名・本文の詳細は保持していない（テーブル定義〈列名・型〉のみ） | 改訂不要（§1.3） |

## 2. ベースライン（2026-10-19実施）

- バックエンド：`ruff check .` 全件合格。`pytest`（カバレッジ計測）**1,880件合格**、カバレッジ100%（8,228文）
- フロントエンド：`npm run lint`（oxlint）0件。`npx tsc -b`エラー0件。`npm run test`（vitest）155ファイル・**1,318件合格**、カバレッジ100%（文・分岐・関数・行）
- 既存の失敗：なし

## 3. 作業手順

凡例：`[ ]` 未着手、`[x]` 完了。各項目の完了条件は「テストが通ること」と「カバレッジ100%（例外処理を除く）」。1手順＝1つの検証可能な変更。

### 3.1 文書改訂

- [x] D-01 `17.5_総括レポート.md`：注入する変数表に`{{recent_logs}}`追加、初期文面へ「# 直近の実績・日記」セクション追加、縮退段階の説明を更新
- [x] D-02 `17.13_AI評価レポート.md`：注入する変数表に`{{weekly_summaries}}`追加、初期文面へ「# それ以前の経過（週次要約）」セクション追加（月次報告のセクション名`{{weekly_summaries}}`の見出し文言に揃える）、段階的縮退の説明を「履歴→週次要約→生ログ」の3段へ改訂（D5の理由を明記）
- [x] D-03 ロジック・プロンプト編メイン：改訂履歴に改51を追加、24章にL-15を新設
- [x] D-04 §1.3で確認した「改訂不要」の各文書について、実装完了時点で改めてgrep確認し、差分が無いことを記録に残す（§6参照。データ構造編・OPERATIONS.md・README.mdのいずれも引き続き該当記載なしを確認）

### 3.2 バックエンド実装

- [x] B-01 `ai_context_common.py`へ公開定数`NO_WEEKLY_SUMMARIES_TEXT = "（週次要約はありません）"`を追加
- [x] B-02 `retrospective_service.py`：`_build_exam_context`に`recent_logs`ステージを追加する。`ai_context_common.resolve_weekly_compressed_period(session, goal, period_start=goal.start_date, period_end=today)`で圧縮範囲を求め、`weekly_summaries`ステージの`entries`をその結果に差し替え、`exclude_covered_dates(ai_context_exam.build_recent_study_entries(session, goal, goal.start_date, today), compressed.covered_ranges)`を`recent_logs`ステージとして追加する。ローカル`_NO_WEEKLY_SUMMARIES_TEXT`定義を削除し`ai_context_common.NO_WEEKLY_SUMMARIES_TEXT`を参照する（あわせて、対象期間を問わず全件取得していた専用関数`ai_context_exam.build_all_weekly_summaries_entries`を廃止し`compressed.weekly_summary_entries`を直接使うよう統一。読書の実装と同じ形になりDRY違反が無くなる）
- [x] B-03 `work_report_service.py`：ローカル`_NO_WEEKLY_SUMMARIES_TEXT`定義を削除し`ai_context_common.NO_WEEKLY_SUMMARIES_TEXT`を参照するよう統一する（圧縮ロジックは変更しない）
- [x] B-04 `work_evaluation_service.py`：`generate_evaluation_report`で`ai_context_common.resolve_weekly_compressed_period(session, work_assignment.goal, period_start=work_assignment.start_date, period_end=today)`を呼び、`stages`を`[feedback_history, weekly_summaries, work_logs]`の順に変更する（D4）。`work_logs`の`entries`は`ai_context_common.exclude_covered_dates(ai_context_work.build_work_logs_entries_for_period(session, work_assignment, work_assignment.start_date, today), compressed.covered_ranges)`とする。`weekly_summaries`の`empty_text`は`ai_context_common.NO_WEEKLY_SUMMARIES_TEXT`
- [x] B-05 `prompt_texts_exam.py`：`GOAL_RETROSPECTIVE`の「# 週ごとの経過\n{{weekly_summaries}}」の直後に「# 直近の実績・日記\n{{recent_logs}}」を追加
- [x] B-06 `prompt_texts_work.py`：`EVALUATION_REPORT_WORK`の「# この案件の日々の業務記録\n{{work_logs}}」の直前に「# それ以前の経過（週次要約）\n{{weekly_summaries}}」を追加（`GOAL_RETROSPECTIVE_WORK_MONTHLY`と同じ見出し文言）
- [x] B-07 新規Alembicマイグレーション（`0ad4f28cd909`、`down_revision=ca4cefcbe9c4`）を作成：`GOAL_RETROSPECTIVE`・`EVALUATION_REPORT_WORK`の`prompt_template.body`を新文面へ更新する（`is_customized=False`行のみ、upgrade/downgradeを対称に実装、`f7c3e9a1b5d6`と同じ構成）
- [x] B-08（dry-reviewerの指摘を受け追加）`resolve_weekly_compressed_period`→`weekly_summariesステージ`→`exclude_covered_dates`した生ログステージ、という3行セットの組み立てパターンが本改修で5箇所（総括レポートのEXAM・READING、月次報告、半期評価、AI評価レポート）に重複したため、`ai_context_common.py`へ`build_weekly_compressed_stages(compressed, *, raw_key, raw_entries, raw_empty_text)`を新設し、5箇所すべてから呼び出すよう統一した（`work_evaluation_service.py`は圧縮不可の`feedback_history`ステージがあるため`[feedback_stage, *ai_context_common.build_weekly_compressed_stages(...)]`の形）

### 3.3 テスト

- [x] T-01 `test_migration_prompt.py`：新マイグレーションの検証4パターン（`GOAL_RETROSPECTIVE`の非カスタマイズ／カスタマイズ、`EVALUATION_REPORT_WORK`の非カスタマイズ／カスタマイズ）。`test_weekly_logs_prompt_migration_updates_non_customized_template`／`_preserves_customized_template`として追加、4件合格
- [x] T-02 `test_api_closure.py`：`test_generate_retrospective_on_reading_goal_includes_weekly_summary`と対になる`test_generate_retrospective_on_exam_goal_includes_weekly_summary_and_recent_logs`を追加し、既存週次要約が`{{recent_logs}}`側へ二重に入らず`{{weekly_summaries}}`側のみへ注入されることを確認する
- [x] T-03 同上（1関数にまとめて実装）：週次要約が無い週の実績・日記が`{{recent_logs}}`の生ログとして注入されること
- [x] T-04 `test_work_evaluation_service.py`：`test_generate_evaluation_report_compresses_work_logs_with_weekly_summary`を追加。既存週次要約がある古い週は圧縮され、要約が無い直近週の業務記録は生ログのまま`{{work_logs}}`へ注入されること
- [x] T-05 `test_generate_evaluation_report_degrades_history_then_weekly_then_logs`を追加：上限超過時に「履歴→週次要約→生ログ」の順で段階的に外れること（D4の配線確認。`ai.max_prompt_chars`を境界値〈1500字・1200字〉に設定し2段階で検証）
- [x] T-06 上記テストの2段階が、各段階で対象ステージの記録を外すことを確認（本テストは各ステージ1件のため全件除去＝最古の除去と同義。`build_with_degradable_entries`の既存挙動を新ステージ構成でも再確認）
- [x] T-07 `NO_WEEKLY_SUMMARIES_TEXT`参照先統一後、旧ローカル定数名（`_NO_WEEKLY_SUMMARIES_TEXT`）を直接参照しているテストが無いかgrepで確認（該当なし。`prompt_builder.py`の同名だが無関係な定数＝DAILY_FEEDBACK用「まだ週次要約はありません」が1件あるのみで本改修の対象外）
- [x] T-08（フルスキャン時未発見・実装時に発覚）`test_seed_data.py::test_initial_prompt_templates_content_is_unchanged_by_the_file_split`：`INITIAL_PROMPT_TEMPLATES`全体のSHA256ハッシュを固定値と比較する回帰テスト（S02決定事項S10、本来は分割時の転記ミス検知用）が、本改修の正規の文面変更により失敗した。転記ミスでなく意図した変更であることを確認したうえで、期待ハッシュ値を更新し、次回以降の文面変更時の更新手順をテストのdocstringへ明記した
- [x] T-09（test-coverage-reviewerの指摘を受け追加）`test_api_closure.py::test_generate_retrospective_on_exam_goal_degrades_weekly_summary_before_recent_logs`：`_build_exam_context`の2段階縮退が「週次要約（古い範囲）→recent_logs（直近の生ログ）」の順で外れることを検証する（work_evaluation_serviceの3段階縮退テストとの整合性確認。`test_generate_retrospective_on_exam_goal_includes_weekly_summary_and_recent_logs`はdedupのみを検証しstages順序は検証していなかったため追加。閾値はテンプレート文面に依存させず、十分大きい上限で実測した全長から動的に算出し、文面変更への耐性を確保した）

### 3.4 検証

- [x] V-01 `ruff check .` → `pytest`（backend）→ `npm run lint`・`npx tsc -b`・`npm run test`（frontend）を全件実行し、§2のベースラインと比較する（B-08のDRY共通化後の最終実行：backend ruff合格・pytest 1,886件合格・カバレッジ100%。frontend lint 0件・tsc -b 0件・vitest 1,318件合格・カバレッジ100%〈フロントエンドはファイル変更なしのため結果不変〉）
- [x] V-02 旧ローカル定数定義（`_NO_WEEKLY_SUMMARIES_TEXT`）が3ファイルのいずれにも残っていないことをgrepで確認する（T-07で実施済み）
- [x] V-03 既存DBのコピーで新マイグレーションを適用し、既存の`prompt_template`行（カスタマイズ済み・未済み双方）が仕様通り更新・保持されることを確認する（CODING_RULES.md「DBマイグレーションのテスト」の対象は`add_column`/`alter_column`等スキーマ変更を伴うものに限られ、本マイグレーションは`UPDATE`のみでスキーマ変更が無いため対象外。同等の検証はT-01（`upgrade_to`で1つ前のリビジョンまで構築→実データ行を挿入→headへ適用→内容を確認）で既に充足している）

## 4. テスト計画

- 要約が一部の週だけある状態で、残りの週の生の記録がプロンプトに入ること（T-03・T-04）
- 要約済みの週の生の記録が二重に入らないこと（T-02）
- 上限超過時に最も古い記録から外れること、かつ段階の優先順位（D4）通りに外れること（T-05・T-06）

## 5. 未決事項

- 縮退の優先順位（D4）：利用者確認済み（2026-10-19、AskUserQuestion）。「履歴→週次要約→生ログ」に決定済みのため、実装時の再確認は不要
- §1.3で「改訂不要」と判断した文書（データ構造編・OPERATIONS.md・README.md）に、実装完了時点（D-04）で新たな差分が見つかった場合は、本章へ追記したうえで反映する

## 6. 別件（範囲外で見つけた問題）

- test-coverage-reviewerの指摘：Alembicマイグレーションの`downgrade()`は、本マイグレーション（`0ad4f28cd909`）を含めリポジトリ全体で一度もテスト実行されていない（`command.downgrade`を呼ぶテストがbackend全体に存在しない）。CODING_RULES.md「DBマイグレーションのテスト」は`upgrade`適用時の既存データに対する安全性のみを要求しており`downgrade()`のテストは明文で要求されていないため、本PR固有の後退ではなく既存の全マイグレーションと同じ慣行。恒久対応（全マイグレーションへのdowngradeテスト追加）は本Todoの範囲外のため、是正するかは運用判断として別件に記録するに留める
- dry-reviewer・test-coverage-reviewerの指摘事項（B-08・T-09で対応したもの以外）に対応要と判断した項目はなし
- マージ後の横展開チェック（`grep -rn 'key="weekly_summaries"' backend/app`）で、`reading_feedback_service.py`・`work_feedback_service.py`（日次報告フィードバック、DAILY_FEEDBACK_READING／_WORK）にも同名キーの`DegradableEntryStage`が計2箇所見つかった。ただし本PRはこの2ファイルを一切変更しておらず（`git diff`で差分0件を確認済み）、両者はS04で新設済みの別の共通化（`ai_context_common.build_past_record_entries`。`resolve_weekly_compressed_period`＋`exclude_covered_dates`を内部で呼び、`weekly_summary_entries`／`raw_entries`を1回で返す）を既に利用しており、本PRで5→1箇所へ集約した「`resolve_weekly_compressed_period`を呼び出し側で直接呼ぶ」パターンとは異なる。将来的に`build_weekly_compressed_stages`と`build_past_record_entries`を1つに統合する余地はあるが、安定稼働中の日次報告フィードバック（S04対象）へ本Todoの範囲外で手を入れることは避け、対応不要・将来課題として記録するに留める
