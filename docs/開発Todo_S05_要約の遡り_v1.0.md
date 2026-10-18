# 開発Todo：S05 週次要約の遡りを目標開始日まで広げる（G3）

本書は、週次要約の起動時遡及生成（`weekly_summary_service.run_retroactive_generation`）が
直近`summary.lookback_weeks`（既定4週）しか遡らず、4週以上アプリを起動しなかった期間の週が
その後も要約されなくなる不具合（G3）を解消する作業の正（Single Source of Truth）である。
作業は `dev/2026-10-18` で行う。版番号（`pyproject.toml`）は変更しない。

## 0. 決定事項（2026-10-18、利用者確認済み）

| # | 決定 | 値 |
| --- | --- | --- |
| G3-1 | 生成順序 | 新しい週から生成する（日次報告への効果が大きい直近週を優先）。1回の起動内で上限件数に達したら、残りの古い週は次回以降の起動で生成する |
| G3-2 | `summary.lookback_weeks`の扱い | 廃止する。概念自体（遡及対象の検索窓）が今回の変更でなくなるため、意味を変えて再利用せず削除する。既存DBに残る値は無害な孤立データとして残し、削除マイグレーションは行わない（データ構造編1.1改46の前例と同じ方針） |
| G3-3 | 新設する上限件数設定 | `summary.retroactive_max_per_run`（INTEGER、既定値 `10`）。1回の起動で生成する(goal, week)の組み合わせ数の上限。AI呼び出し1件あたり実測10〜16秒＋呼び出し間隔2秒を踏まえ、1回の起動あたり約2〜3分に収まる値とした |
| G3-4 | 失敗の可視化 | 追加しない（今回は対象外）。既存の`ai_log`のエラー記録とアプリログ（`_logger.exception`）のみで足りるとする。同じ週の失敗が続く場合の利用者向け通知は将来課題とする |

## 1. 影響範囲（フルスキャンの結果）

### 1.1 バックエンド

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| 設定キー | `app/constants/app_setting_keys.py` | `SUMMARY_LOOKBACK_WEEKS`を削除し、`SUMMARY_RETROACTIVE_MAX_PER_RUN = "summary.retroactive_max_per_run"`を追加 |
| 初期データ | `app/init/seed_data.py`（`INITIAL_APP_SETTINGS`のimport・エントリ） | `SUMMARY_LOOKBACK_WEEKS`のimport・エントリ（`("4", INTEGER)`）を削除し、`SUMMARY_RETROACTIVE_MAX_PER_RUN`のimport・エントリ（`("10", INTEGER)`）を追加。起動時シードは「不足分のみ投入」のため既存DBにも新キーが届く |
| サービス | `app/services/weekly_summary_service.py` | `_CategorySpec`に`effective_start_date`（カテゴリ別の実質開始日。資格試験・仕事は`goal.start_date`、読書は`goal.book.start_date`）を追加。`_earliest_effective_start_date`を新設（全目標中の最も早い実質開始日を返す）。`list_pending_weeks`の`lookback_weeks`引数を廃止し、`_earliest_effective_start_date`から`last_completed_sunday`までの全週を対象にする。`run_retroactive_generation`は`SUMMARY_LOOKBACK_WEEKS`の読み出しをやめ、`SUMMARY_RETROACTIVE_MAX_PER_RUN`を読み出して`list_pending_weeks`の戻り値（新しい週順）の先頭から上限件数分のみ生成する |
| 起動フロー | `app/main.py`（`run_ai_startup_tasks`） | 変更なし（既に別スレッドで実行済み、呼び出しシグネチャ`run_retroactive_generation(session, today)`は不変であることを確認する） |
| テスト | `backend/tests/test_weekly_summary_service.py` | `lookback_weeks=4`を渡す既存7箇所の呼び出しを更新。`test_list_pending_weeks_respects_lookback_limit`は前提自体が無くなるため、新しい挙動（目標開始日まで遡る・上限件数で区切る）を検証するテストへ置き換える |
| テスト | `backend/tests/test_seed_data.py` | キー数の総数は自己調整（`len(INITIAL_APP_SETTINGS)`比較）のため変更不要。個別の値検証は無い（確認のみ） |

### 1.2 フロントエンド

影響なし。`summary.lookback_weeks`・新設する`summary.retroactive_max_per_run`はいずれも設定画面に露出しない基盤値（既存の`server.graceful_shutdown_seconds`等と同じ位置づけ）であり、`settings_service.py`・`schemas/setting.py`・フロントエンドのどこにも参照が無いことをGrepで確認済み。

### 1.3 ドキュメント

| 文書 | 変更 |
| --- | --- |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1/15_週次要約の生成.md` | 15.2の手順2・手順4を改訂（目標開始日までの遡及、上限件数と新しい週優先、残りは次回以降）。手順3の「category=READINGは対象外」という記述はL-11で既に古くなっているため、本改訂で合わせて是正する |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1/24_未決事項.md` | G3の解消をL-13として追加 |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1.md` | 改訂履歴に改49を追加 |
| `docs/設計書_データ構造編_ミチナリ_v1.1/05_テーブル定義/5.2_設定・マスタ系.md` | `summary.lookback_weeks`の行を削除し、`summary.retroactive_max_per_run`の行を追加 |
| `docs/設計書_データ構造編_ミチナリ_v1.1.md` | 改訂履歴に改47を追加 |
| `docs/実装フェーズ分割計画書_ミチナリ_v1.1/02_フェーズ一覧.md` | Phase 45（S05）の節を追加（Phase44の形式を踏襲） |
| `docs/実装フェーズ分割計画書_ミチナリ_v1.1/03_各フェーズの詳細/Phase45.md` | 新設 |
| `docs/実装フェーズ分割計画書_ミチナリ_v1.1.md` | 改訂履歴に改26を追加 |

`要件定義書_ミチナリ_v1.1.md`・`仕様書_ミチナリ_v1.1.md`・`OPERATIONS.md`は、本件が既存要件（週次要約の遡及生成）の内部的な上限緩和であり新しい要件・画面・運用手順を追加しないため、Grep確認の結果対象外と判断した（§6参照）。

### 1.4 既存機能への横展開（同じ問題の有無を確認）

| 項目 | 状況 | 対応 |
| --- | --- | --- |
| `recap_generation_service.run_all`（振り返りテーマの起動時バッチ） | `recap_service.collect_pending_entries`は`goal.start_date`から対象日の前日までの全期間を対象にしており、本件のような固定窓（lookback）は持たない。同種の不具合は無い | 対応不要（確認のみ） |
| `summary.inject_weeks`等、過去に撤廃された窓設定キー（L-12） | 日次報告フィードバックの注入窓は既に撤廃済みで、本件とは別の設定キー・別の問題だったことを確認済み | 対応不要（確認のみ） |

## 2. ベースライン（2026-10-18、作業開始前）

- バックエンド：`ruff check .` 全件合格。`pytest`（`backend`で実行）1,860件合格、カバレッジ100%（8,176文・1,526分岐）
- フロントエンド：`npm run test`（vitest）155ファイル・1,318件合格、カバレッジ100%（文・分岐・関数・行）。`npm run lint`（oxlint）0件。`npx tsc -b` エラー0件
- 既存の失敗：無し

## 3. 作業手順

凡例：`[ ]` 未着手、`[x]` 完了。各項目の完了条件は「テストが通ること」と「カバレッジ100%（例外処理を除く）」。

### 3.1 設定キーの入れ替え

- [x] T-01 `app/constants/app_setting_keys.py`：`SUMMARY_LOOKBACK_WEEKS`を削除、`SUMMARY_RETROACTIVE_MAX_PER_RUN`を追加
- [x] T-02 `app/init/seed_data.py`：importとエントリを対応させて入れ替え（初期値 `"10"`、INTEGER）

### 3.2 `weekly_summary_service.py`の実装

- [x] T-03 `_CategorySpec`に`effective_start_date: Callable[[Session, Goal], dt.date]`を追加。`_EXAM_SPEC`・`_WORK_SPEC`は`goal.start_date`、`_READING_SPEC`は`goal.book.start_date`を返す
- [x] T-04 `_earliest_effective_start_date(session) -> dt.date | None`を新設：3カテゴリそれぞれの目標を取得し、`effective_start_date`の最小値を返す。目標が1件も無ければ`None`
- [x] T-05 `list_pending_weeks(session, today)`：`lookback_weeks`引数を削除。`_earliest_effective_start_date`が`None`、または最も早い週の開始（月曜）が`last_completed_sunday`より後の場合は空リストを返す。それ以外は、最も早い週から`last_completed_sunday`までの全週を対象に、既存の判定（週内のログ有無・生成済み判定）を行う。ループの走査順は変更しない（直近週→過去週、= 新しい週から並ぶ）
- [x] T-06 `run_retroactive_generation(session, today)`：`SUMMARY_LOOKBACK_WEEKS`の読み出しをやめ、`SUMMARY_RETROACTIVE_MAX_PER_RUN`を読み出す。`list_pending_weeks(session, today)`の戻り値（新しい週が先頭）の先頭から上限件数分だけを生成対象にする（`pending[:max_per_run]`）。それ以外のロジック（1件ごとのcommit/rollback、失敗の継続）は変更しない

### 3.3 テスト

- [x] T-07 既存の`list_pending_weeks`呼び出し7箇所から`lookback_weeks=4`引数を削除
- [x] T-08 `test_list_pending_weeks_respects_lookback_limit`を、新しい挙動を検証するテストへ置き換える（`test_list_pending_weeks_reaches_back_to_goal_start_date`・`test_list_pending_weeks_orders_newest_week_first`）
- [x] T-09 読書目標は`book.start_date`、資格試験・仕事は`goal.start_date`を基準に遡ることを確認するテストを追加（`test_list_pending_weeks_reading_reaches_back_to_book_start_date`）
- [x] T-10 目標が1件も無い場合・目標が今週開始で完了週がまだ無い場合に`list_pending_weeks`が空リストを返すことを確認するテストを追加（カバレッジ100%のため分岐も網羅）
- [x] T-11 `run_retroactive_generation`が`summary.retroactive_max_per_run`件までしか生成しないことを確認するテスト（`test_run_retroactive_generation_respects_max_per_run`）
- [x] T-12 上限により生成されなかった週が、次回の`run_retroactive_generation`呼び出しで生成されることを確認するテスト（`test_run_retroactive_generation_picks_up_remaining_weeks_on_next_run`）
- [x] T-13 新しい週が古い週より先に生成されること（生成順序）を確認するテスト（`test_run_retroactive_generation_generates_newest_week_first`）
- [x] T-14 既存の`test_run_retroactive_generation_continues_after_one_failure`・`test_run_retroactive_generation_respects_call_interval`が新しい実装でも通ることを確認済み（`backend`で`pytest`実行、1,867件合格・カバレッジ100%、ベースラインの1,860件から正味+7件）

### 3.4 ドキュメント改訂

- [x] D-01 設計書（ロジック・プロンプト編）15.2：手順2・手順4を改訂し、手順3のREADING除外の誤記を是正。改訂履歴に改49を追加
- [x] D-02 設計書（ロジック・プロンプト編）24章：L-13を新設
- [x] D-03 設計書（データ構造編）5.2：設定キー表の入れ替え。改訂履歴に改47を追加
- [x] D-04 実装フェーズ分割計画書：Phase 45（S05）を新設（02_フェーズ一覧.md・03_各フェーズの詳細/Phase45.md）。改訂履歴に改26を追加

## 4. テスト計画

- 目標開始日から数か月分の未生成の週があるとき、上限件数（既定10）ずつ生成され、複数回の起動で全週が埋まること（T-11・T-12）
- 失敗した週が次回に再試行され、他の週の生成を妨げないこと（既存T-14で確認。1件ごとのcommit/rollbackは変更していないため回帰しないはず）
- 記録の無い週・未完了の今週（`last_completed_sunday`より後）は対象にならないこと（既存テストと新規T-10で確認）
- 新しい週が古い週より先に生成されること（T-13）
- 読書目標は`book.start_date`、資格試験・仕事は`goal.start_date`を実質開始日とすること（T-09）
- ベースライン（§2）と比較し、バックエンド・フロントエンドのテスト件数が減っていないこと（1件を置き換えるため、バックエンドは差し引き±0件程度の見込み。減った場合は理由を報告する）

## 5. 未決事項

無し（§0の決定事項で全て確定済み）。

## 6. 別件（範囲外で見つけた問題）

| # | 内容 | 対応方針 |
| --- | --- | --- |
| 1 | `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1/15_週次要約の生成.md`の手順3「category=READINGの目標はstudy_logを持たないため自動的に対象外」という記述は、L-11（読書・仕事への週次要約新設）で実装が変わった後も是正されていなかった（本書D-01で合わせて是正する。本件は影響範囲が同一箇所のため別件ではなく本作業に含めた） |
| 2 | `docs/設計書_データ構造編_ミチナリ_v1.1.md`改45に「なお改43（2026-10-06付）は本文書に存在しない章を指しており…過去ログのため本分割では修正しない」という既知の誤記が記録されている。本件とは無関係のため対応しない |
