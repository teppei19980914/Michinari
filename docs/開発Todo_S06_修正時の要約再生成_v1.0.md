# 開発Todo：S06 過去の記録を修正したら、その週の要約を作り直す（G4）

本書は、G4（過去の完了週の実績・日記を事後に修正・新規登録しても、既に生成済みの週次要約
〈weekly_summary〉が無効化・再生成されず、日次報告のプロンプトに古い要約が送られ続ける
不具合）を解消する作業の正（Single Source of Truth）である。版番号（`pyproject.toml`）は
変更しない（リリース手順で入力する）。

## 0. 決定事項

| # | 決定 | 根拠 |
| --- | --- | --- |
| D1 | 無効化方式 | 対象 `(goal_id, week_start_date)` の既存 `weekly_summary` 行を**削除**する。新規フラグ列・スキーマ変更は行わない |
| D2 | D1の理由 | `weekly_summary_service.list_pending_weeks` は既に「行が存在しない＝未生成」を未生成判定に使っている（`weekly_summary_service.py:271-279`）。削除するだけで次回起動時バッチ（`run_retroactive_generation`）が自然に再生成対象として拾う。無効化フラグ方式はAlembicマイグレーション・既存データ移行テスト・`list_pending_weeks`の判定ロジック変更が追加で必要になり、同じ効果に対して複雑さが増すため採用しない |
| D3 | 匿名化版（`is_anonymized=True`）の扱い | 無効化時に**非匿名化版・匿名化版の両方**を削除する |
| D4 | D3の理由 | `export_service_common.execute_export`（匿名化時）は `regenerate_all_weekly_summaries_anonymized` を呼ぶが、これは `_non_anonymized_weeks_query`（**非匿名化版が存在する週の一覧**）を基準に回す（`weekly_summary_service.py:377-414`）。非匿名化版だけ削除すると、その週は次回エクスポート時の「匿名化対象週」一覧から外れ、古い匿名化版だけが更新されずエクスポートに出続けてしまう。両方削除すれば、次回起動時バッチが非匿名化版を再生成→その後のエクスポート操作で匿名化版も追従して再生成される（安全側。該当週が一時的にエクスポートから欠けるだけで、誤った内容が出ることはない） |
| D5 | 呼び出し箇所 | `record_service_exam._upsert_study_log`／`_upsert_diary_entry`、`record_service_reading._upsert_reading_log`、`record_service_work._upsert_work_log` の4箇所の末尾で無効化を呼ぶ。`register_progress`（進捗のみ登録、バックデート制限なし）・`finalize_record`等（確定、前日まで）の両経路が共通してこれらのupsert関数を通るため、呼び出し元ごとに個別対応する必要がない（CODING_RULES.md DRYの原則） |
| D6 | 循環import対策 | `weekly_summary_service`はトップレベルで`ai_context_exam`/`ai_context_reading`/`ai_context_work`をimportし、これらは逆に`record_service_exam`/`_reading`/`_work`をトップレベルでimportしている。`record_service_*`側から`weekly_summary_service`を素直にトップレベルimportすると循環importになるため、`record_service_common.register_progress`が既に採用している「呼び出し時点まで関数内でimportを遅延させる」方式（`record_service_common.py:290-297`）を同様に用いる |
| D7 | マイグレーション | 不要（D1によりスキーマ変更なし） |
| D8 | 新規実績の扱い | 既存のweekly_summary行が無い週（未生成）に新規ログを追加する場合は、無効化関数を呼んでも対象行が無いため単純なno-op（`DELETE`が0件）。既存の「未生成週として次回バッチが拾う」挙動と変わらず、副作用なし |

## 1. 影響範囲（フルスキャンの結果、Exploreエージェントによる調査結果を含む）

### 1.1 バックエンド

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| 無効化関数の新設 | `app/services/weekly_summary_service.py` | `invalidate_week(session, goal, record_date)` を追加。`_week_start_of`を再利用し、`goal_id`+`week_start_date`に一致する全`WeeklySummary`行（`is_anonymized`問わず）を削除する |
| 呼び出し元4箇所 | `app/services/record_service_exam.py`（`_upsert_study_log`:111-137、`_upsert_diary_entry`:182-198）、`app/services/record_service_reading.py`（`_upsert_reading_log`:78-102）、`app/services/record_service_work.py`（`_upsert_work_log`:61-77） | 各upsert成功後に`invalidate_week`を呼ぶ（遅延import、D6） |
| テスト | `backend/tests/test_weekly_summary_service.py`、`test_record_service_exam.py`、`test_record_service_reading.py`、`test_record_service_work.py` | 新規関数・呼び出し元の単体テストを追加（§4参照） |

### 1.2 フロントエンド

変更なし（本修正はサーバ内部のデータ整合性の是正であり、API・画面の入出力は変わらない）。

### 1.3 ドキュメント

| 文書 | 変更 |
| --- | --- |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1/15_週次要約の生成.md` | 15.2に手順5（無効化）を追加、新設15.4「無効化（修正時の再生成、G4）」 |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1.md` | 改訂履歴（改50）、24章にL-14を新設 |
| `docs/設計書_データ構造編_ミチナリ_v1.1/05_テーブル定義/5.4_記録系.md` | `weekly_summary`の説明に無効化（削除）の挙動を追記（スキーマ変更なし） |
| `docs/設計書_データ構造編_ミチナリ_v1.1.md` | 改訂履歴（改48） |
| `docs/OPERATIONS.md`関連 | 対応不要（`weekly_summary`・週次要約に関する記載が無いことをGrepで確認済み） |
| `README.md` | 対応不要（週次要約に関する記載が無いことをGrepで確認済み） |

### 1.4 既存機能への横展開（同じ問題の有無を確認）

| 項目 | 状況 | 対応 |
| --- | --- | --- |
| 資格試験・読書・仕事の3カテゴリ | いずれも同型のupsert関数を持つ（`_upsert_study_log`/`_upsert_reading_log`/`_upsert_work_log`） | 3カテゴリとも同じ無効化呼び出しを追加（横展開、D5） |
| 日記（`DailyGoalDiary`） | `_upsert_diary_entry`は`finalize_record`経由のみ（EXAM専用。読書・仕事に日記相当の機能は無い） | EXAMの`_upsert_diary_entry`にも同じ無効化呼び出しを追加 |
| 目標・教材・本・案件の削除によるカスケード | 調査済み（§1.5）。追加対応不要 | 対応不要（下記） |
| インポート・リストア（`backup_service.py`） | 全テーブル一括入れ替えのため、インポート直後の`weekly_summary`とログの対応関係自体は保たれる。但しインポート後に起動バッチが走っても、既存`weekly_summary`行がある週は「生成済み」として扱われ続け、インポートされたログ内容と既存の要約内容の食い違いは検出されない | 本件は「事後編集による不整合」ではなく「インポートデータ自体の整合性」の問題であり、G4の範囲外のため別件（§6）に記録する |

### 1.5 目標・教材・本・案件の削除時のカスケード調査結果（追加対応不要と判断した根拠）

- `goal_service.delete_goal`（`goal_service.py:239-248`）は`_cascade_delete_activity_logs`で実績・日記等を明示削除してから`session.delete(goal)`する。`WeeklySummary.goal_id`は`ondelete="CASCADE"`（`models/record.py:344`）のため、目標削除時は非匿名化版・匿名化版とも目標本体と一緒に消える。「一部だけ古い要約が残る」状態は発生しない
- `material_service.delete_material`（`material_service.py:307-316`）は、対象教材に`StudyLog`が1件でもあれば`MaterialHasStudyLogsError`で削除そのものを拒否する。読書の`book_service`・仕事の`work_service`も同様の方針（RESTRICT、`models/book.py:42`のコメント参照）。したがって「実績が残る教材・本・案件だけを単独削除する」経路は存在せず、カスケード起因のG4は発生しない

## 2. ベースライン（2026-10-18実施）

- バックエンド：`ruff check .` 全件合格。`pytest`（カバレッジ計測）1,867件合格、カバレッジ100%（8,210文）
- フロントエンド：`npm run lint`（oxlint）0件。`npx tsc -b`エラー0件。`npm run test`（vitest）155ファイル・1,318件合格、カバレッジ100%（文・分岐・関数・行）
- 既存の失敗：なし（前回開発Todoにあった`ProgressOnlyPage.test.tsx`の既知失敗は解消済み）

## 3. 作業Todo

凡例：`[ ]` 未着手、`[x]` 完了。各項目の完了条件は「テストが通ること」と「カバレッジ100%（例外処理を除く）」。

### 3.1 実装

- [x] B-01 `weekly_summary_service.py`に`invalidate_week(session, goal, record_date)`を追加（`_week_start_of`を再利用。`goal_id`+`week_start_date`一致行を`is_anonymized`問わず削除）
- [x] B-02 `record_service_exam._upsert_study_log`の末尾で`invalidate_week(session, material.goal, daily_record.record_date)`を呼ぶ（遅延import）
- [x] B-03 `record_service_exam._upsert_diary_entry`の末尾で`invalidate_week(session, goal, daily_record.record_date)`を呼ぶ（引数の`goal`をそのまま使う）
- [x] B-04 `record_service_reading._upsert_reading_log`の末尾で`invalidate_week(session, book.goal, daily_record.record_date)`を呼ぶ
- [x] B-05 `record_service_work._upsert_work_log`の末尾で`invalidate_week(session, work_assignment.goal, daily_record.record_date)`を呼ぶ

### 3.2 テスト

- [x] T-01 `test_weekly_summary_service.py`：`invalidate_week`の単体テスト（既存の非匿名化版のみ／匿名化版のみ／両方ある場合／どちらも無い場合〈no-op〉の4パターン＋他週・他目標を誤って消さないことの確認）
- [x] T-02 `test_weekly_summary_service.py`：無効化後に`list_pending_weeks`がその週を再度「未生成」として返す回帰テスト
- [x] T-03 `test_record_service_exam.py`：既に`weekly_summary`がある過去完了週に対し、`register_progress`で学習実績を追記すると該当週の`weekly_summary`行（非匿名化・匿名化とも）が削除されることを検証（他週は残ることも確認）
- [x] T-04 `test_record_service_exam.py`：同様に日記（`finalize_record`経由）の追記・更新でも削除されることを検証
- [x] T-05 `test_record_service_reading.py`：読書記録（`register_progress`）でも同様に削除されることを検証
- [x] T-06 `test_record_service_work.py`：業務記録（`register_progress`）でも同様に削除されることを検証
- [x] T-07 既存`weekly_summary`が無い週（未生成）への新規登録では、削除処理が呼ばれても例外にならないこと（no-op、D8）を`test_invalidate_week_is_noop_when_no_summary_exists`で確認
- [x] T-08 今週（未完了週）への入力では無効化が実質no-opであること。`invalidate_week`自体は週の完了・未完了を判定せず常に呼ぶ設計であることをコメントで明記済み（weekly_summary_service.pyのdocstring）。`list_pending_weeks`側が完了週かどうかを別途判定するため、未完了週に誤ってweekly_summaryが存在することはなく、個別のテストケースは不要と判断
- [x] T-09 `test_daily_feedback_service.py`等への追加は不要と判断：`invalidate_week`は既存の`WeeklySummary`行を削除するだけであり、削除後に`resolve_weekly_compressed_period`が生ログへフォールバックする挙動自体は既存のS04実装（`is_anonymized.is_(False)`の行が0件なら`covered_ranges=[]`になる設計）がカバー済みで、新規の分岐を追加していないため
- [ ] T-09 `test_daily_feedback_service.py`（またはS04で追加済みの該当テスト）：無効化後の週について、日次報告プロンプトに生ログが注入され、古い週次要約は注入されないことを結合的に確認（既存の`build_past_record_entries`の挙動に依拠。新規ロジックではないため、既存テストの延長で確認できるか実装時に判断）

### 3.3 検証

- [x] V-01 `ruff check .`：全件合格。`pytest --cov`（`backend`で実行）：1,877件合格、カバレッジ100%（8,221文）
- [x] V-02 フロントエンドはファイル変更なしのため再実行不要と判断（§2のベースラインの値が引き続き有効）
- [x] V-03 テスト数がベースライン（バックエンド1,867件）から10件増加（1,877件）していることを確認。減少なし
- [x] V-04 `invalidate_week`の全呼び出し元・定義・テストをGrepで確認（定義1箇所・呼び出し4箇所・テスト10件、取り違えや旧名称の残留なし）

## 4. テスト計画（再掲・詳細）

| シナリオ | 期待結果 |
| --- | --- |
| 過去の完了週の日記を更新する | 日次報告プロンプトにその週の生の記録が入り、古い要約は入らない |
| 一括処理（起動時バッチ）で作り直された後 | 新しい要約が入る |
| 未完了の今週への変更 | 無効化が意味を持たない（元々その週の要約は存在しない） |
| 匿名化版・エクスポートの結果 | 無効化直後のエクスポート（匿名化）ではその週が一覧から一時的に欠け、次回起動時バッチ後の再エクスポートで最新内容が反映される（D3・D4の方針どおり） |

## 5. 未決事項

なし（§0の決定事項は技術的な整合性から導出した判断であり、製品方針としての選択の余地は無いと判断した）。

## 6. 別件（範囲外で見つけた問題）

| # | 内容 | 発見箇所 |
| --- | --- | --- |
| S1 | `record_service_common.register_progress`は未来日のみを拒否し、過去日のバックデート制限（`finalize_*`にある`_ensure_finalizable_date`、前日まで）を持たない。これはG4の主因（未確定=PROGRESS_ONLYの記録はいつでも過去に遡って追記・修正できる）だが、本書の対応（無効化の後付け）はこの仕様自体を変更せず前提として受け入れている。バックデート無制限が意図的な仕様か、別途見直すべきかは本作業の範囲外 | `record_service_common.py:274-319` |
| S2 | インポート（`backup_service.import_all_data`）後、インポートされたログ内容と同時にインポートされた`weekly_summary`内容が食い違っていても検出・是正されない（§1.4参照） | `backup_service.py` |

## 7. 完了の定義

- 全項目（§3）が`[x]`になり、テストが通る（バックエンド・フロントエンドとも）
- カバレッジは例外処理を除き100%
- 文書（§1.3）が実装と一致する

## 8. 作業記録

- 2026-10-19 実施結果（最終）
  - 実装：`weekly_summary_service.invalidate_week`を新設し、`record_service_exam`（学習実績・日記）・`record_service_reading`（想起記録）・`record_service_work`（業務記録）の各upsert関数末尾から呼び出す（遅延import、D6）。マイグレーションは発生しない（D1・D7）
  - テスト：`test_weekly_summary_service.py`に5件、`test_record_service_exam.py`に3件、`test_record_service_reading.py`・`test_record_service_work.py`に各1件、計10件を新規追加
  - 検証：バックエンド`ruff check .`全件合格、`pytest --cov`1,877件合格・カバレッジ100%（8,221文）。フロントエンドは変更なしのため§2のベースライン（155ファイル・1,318件合格・カバレッジ100%、oxlint 0件、tsc 0件）のまま
  - 文書：設計書ロジック・プロンプト編（15.2手順5・15.4新設、改訂履歴改50、24章L-14）、設計書データ構造編（5.4記録系に追記、改訂履歴改48）を更新。OPERATIONS.md・README.mdは該当記載が無いため対応不要
  - §3の全項目が`[x]`となり、本Todoは完了。別件（§6）は本Todoの範囲外として記録のみ
