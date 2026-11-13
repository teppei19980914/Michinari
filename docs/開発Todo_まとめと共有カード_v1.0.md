# 開発Todo：ふりかえりまとめと社内共有カード（v2.9.0 対象）

本書は、積み上げを1枚のカードにまとめ社内チャットへ共有できる「ふりかえりまとめと社内共有カード」の
開発作業の正（Single Source of Truth）である。規模はマイナーバージョンアップに相当する新フェーズ
Phase 51。作業は `dev/2026-11-11`（`origin/main` 2.8.0 から作成）で行う。

## 0. 決定事項（2026-11-11 時点で確定）

| # | 決定 | 値 |
| --- | --- | --- |
| U1 | トリガー① 目標完了時 | `CLOSED_WITH_RESULT`の目標のみ（既存の`canGenerateRetrospective`・`retrospective_service`と同じ扱い。読了・受験結果の登録・案件のクローズはいずれも本状態に帰着する） |
| U2 | トリガー② 期間指定 | 利用者回答により、**目標を1つ選んで期間を指定**する設計に確定。複数目標をまとめた全体集計は対象外（テーマ頻度・節目・道のりマップ縮小図がgoal単位のデータのため）。ステータス不問（`ACTIVE`中の目標でも期間指定は可） |
| U3 | 既定期間（期間指定モード） | 開始＝当年1/1、終了＝サーバ論理日（`GET /records/today`、クライアント側で論理日を判断しない既存ルールに従う）。UIはプリセット＋カレンダーで`LogExportSection.tsx`と同型にする |
| U4 | 永続化 | **しない**。集計はGETで都度算出、AI一文は専用POSTで明示操作時のみ生成し結果はフロント状態のみに保持（新規テーブルを作らない。DBマイグレーション不要）。送信・記帳は既存の`send_and_log`経由で`ai_log`へ自動記録される（既存ルールの範囲内） |
| U5 | AI一文の生成方式 | 利用者回答により、**記録本文の逐語引用ではなく、要約・一般化して新しく生成した一文**に確定。既存の`build_anonymize_instruction`と同じ考え方のプロンプト指示を追加する。入力（期間内の日記・振り返り本文等をAIに読ませること自体）は既存の総括レポート等と同様に許容されるが、**出力は一般化された一文のみ**とし、原文の引用・言い換えに留まらない生成を指示文で明示する |
| U6 | 匿名化の扱い | 本カードは**常に匿名化方式を適用**する（`KnowledgeExportPage`の`anonymize`トグルとは独立。利用者が選べない）。日記本文・AI対話履歴はカードのいかなる経路でも取得しない（`export_service_common.ExportSelection`の既定除外と同じ方針を踏襲） |
| U7 | カード項目 | 記録日数（期間内、`DailyRecord.record_date`の重複なし件数）／最長の連続記録日数（期間内、新規算出）／いちばん多く書いたテーマ（EXAM・READINGのみ。WORKは項目自体を表示しない）／達成した節目（`GoalMilestoneAchievement`のうち`achieved_at`が期間内）／道のりマップ縮小図（`GoalRoadmapMini`を埋め込み）／AIが選んだ一文（AI設定時のみ、未設定時は項目を省略） |
| U8 | 画面の配置 | 新規ページを作らず、既存2画面に共通コンポーネント`SummaryCardSection`を追加する。`GoalDetailPage`（任意ステータス、期間指定モード）と`KnowledgeExportPage`（`CLOSED_WITH_RESULT`時、目標完了時モード＝既定期間は目標の`start_date`〜クローズ日）。WORKは`KnowledgeExportPage`の`WorkRetrospectivesNote`の下に併置（導線の一本化、`user_product_design_motto`の既存方針に合わせる） |
| U9 | 新規AI用途 | `AiPurpose`/`ConversationScope`に`SUMMARY_CARD_SENTENCE`／`SUMMARY_CARD_SENTENCE_READING`／`SUMMARY_CARD_SENTENCE_WORK`の3値を追加（既存の`DAILY_FEEDBACK`系・`WEEKLY_SUMMARY`系と同じ「種別ごとに分ける」命名パターンに揃える。値追加のみでDB変更は不要） |
| U10 | アシスタント設定キー | `ai.assistant_uid.summary_card`を新設（既存の週次要約用等は流用しない。呼び出し頻度・プロンプト予算が独立しているため既存流儀どおり専用キーとする）。あわせて使い捨てチャット用の`ai.summary_card_folder_name`（既定「ミチナリ_まとめ」）も新設する（ヘルプ・目標相談と同じ`ensure_conversation`＋`discard_conversation`の組で、discard側がfolder_nameを必須で要求するため） |
| U11 | 新規エンドポイント | `GET /goals/{goal_id}/summary-card?date_from=&date_to=`（集計のみ、AI抜き）／`POST /goals/{goal_id}/summary-card/sentence`（AI一文、明示操作時のみ呼ぶ）。クエリ名は`from`がPythonの予約語のため`date_from`／`date_to`とする |
| U12 | 画像化方式 | 新規ライブラリ追加なし。SVGでカードを構築→`XMLSerializer`で文字列化→`Blob(image/svg+xml)`→`Image`要素へ読込→`canvas.drawImage`→`canvas.toBlob('image/png')`。描画前に`document.fonts.ready`を待ち日本語フォントの読み込み待ちを行う（Webフォント埋め込みは新規依存になるため行わず、OS標準フォントに委ねる） |
| U13 | 保存・コピー | 保存は既存`downloadBlob.ts`を再利用。コピーは`navigator.clipboard.write([new ClipboardItem({'image/png': blob})])`。非対応環境はトーストで保存のみ案内（新規依存なし） |
| U14 | 外部送信 | 行わない（アプリから直接の投稿・送信はしない。保存・コピーのみ） |
| 版 | バージョン | 2.9.0。`pyproject.toml`の版更新は**リリース手順（`release.bat`）で入力する**（開発中は変更しない） |

## 1. 影響範囲（フルスキャンの結果）

### 1.1 バックエンド

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| 列挙 | `app/constants/enums.py`：`AiPurpose`・`ConversationScope` | 値の追加3件×2（非ネイティブ列挙のためDB変更不要） |
| 設定キー | `app/constants/app_setting_keys.py` | `ai.assistant_uid.summary_card`を追加 |
| 初期データ | `app/init/seed_data.py`（`INITIAL_APP_SETTINGS`・`INITIAL_PROMPT_TEMPLATES`）、`app/init/prompt_texts.py` | 初期値・プロンプト本文3種の追加。起動時シードは不足分のみ投入のため既存DBにも届く |
| 集計ロジック（新規） | `app/services/metrics_service.py` | `compute_longest_consecutive_report_days(session, goal, date_from, date_to, treat_holiday_as_buffer)`を追加。既存`compute_consecutive_report_days`と同じ「BUFFER/OFF日は中断しない」定義を踏襲し、最大連続区間を走査して返す |
| 集計ロジック（再利用・確認のみ） | `metrics_service`（記録日数の集計パターン）、`recap_service.theme_entry_rows`（テーマ頻度）、`milestone_service_common.list_achievements`（節目一覧） | 変更なし。新規サービスから呼び出すのみ |
| 新規サービス | `app/services/summary_card_service.py`（集計の束ね＋AI一文生成の呼び出し） | 追加。100行超過・カテゴリ分岐が肥大化した場合は`CODING_RULES.md`の分割規則（`summary_card_service_common.py`／`_exam.py`／`_reading.py`／`_work.py`）に従う |
| 新規API | `app/api/summary_card.py`、`app/schemas/summary_card.py`、`app/main.py`（ルーター登録） | 追加。ドメイン例外→API層変換の既存方式に従う |
| 設定配線 | `app/services/settings_service.py`、`app/schemas/setting.py` | 新アシスタント設定の配線（`help_assistant_service`導入時のB-11と同型） |
| AI基盤 | `app/ai/orchestration.py`（`send_and_log`） | 既存経路をそのまま使用。変更なし（確認のみ） |
| テスト | `backend/tests/test_metrics_service.py`（最長連続日数）、`backend/tests/test_summary_card_service.py`、`backend/tests/test_api_summary_card.py` | 追加 |

### 1.2 フロントエンド

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| API層 | `src/api/summaryCard.ts`（新規）、`src/types/api.d.ts`（`npm run generate:api-types`で再生成） | 追加 |
| 機能（新規） | `src/features/summaryCard/`：期間選択（`LogExportSection.tsx`と同型のプリセット＋カレンダー）、項目表示/非表示トグル（フロント状態のみ）、カードSVG構築、SVG→PNG変換の純粋関数、クリップボードコピー | 追加 |
| 共通部品の再利用 | `src/features/goal/GoalRoadmapMini.tsx`（設計時から再利用想定、変更なし）、`src/utils/downloadBlob.ts`（変更なし） | 確認のみ・再利用 |
| 画面への組み込み | `src/pages/GoalDetailPage.tsx`、`src/pages/KnowledgeExportPage.tsx` | `SummaryCardSection`の追加 |
| 設定画面 | `src/features/settings/assistantFields.ts`、`src/features/settings/AiConnectionSection.test.tsx`（フィクスチャ） | 新アシスタント欄の追加 |
| 文言 | `src/locales/ja.json`／`en.json` | `summaryCard.*`一式（カード項目名・期間ラベル・保存/コピーのボタン・失敗時の案内等）。キー構造はja/en一致必須（`localeKeyUsage.test.ts`） |
| 定数 | `src/constants/queryKeys.ts` | 必要な場合のみ追加（実装時判断） |

### 1.3 ドキュメント

| 文書 | 変更 |
| --- | --- |
| `docs/要件定義書_ミチナリ_v1.1.md` | 新設節（R番号は実装時に次番号を確認）、改訂履歴 |
| `docs/仕様書_ミチナリ_v1.1.md` | 機能一覧表、SC-03（`GoalDetailPage`）・SC-13（`KnowledgeExportPage`）の画面仕様改訂、設定項目、改訂履歴 |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1.md` | 処理フロー、`SUMMARY_CARD_SENTENCE`系プロンプト、入力・出力検証、脅威モデル（STRIDE）、改訂履歴 |
| `docs/設計書_データ構造編_ミチナリ_v1.1.md` | 設定キー`ai.assistant_uid.summary_card`、`AiPurpose`/`ConversationScope`追加値、改訂履歴 |
| `docs/実装フェーズ分割計画書_ミチナリ_v1.1.md` | Phase 51 の追加 |
| `docs/OPERATIONS.md` | 該当サブファイルへの追記が必要か実装時に判断（新規の運用手順は現時点で想定なし） |

### 1.4 既存機能への横展開（同じ問題の有無を確認）

| 項目 | 状況 | 対応 |
| --- | --- | --- |
| レビューエージェントの起動条件 | 新規AI用途・新規画面・新規エンドポイントを含む | `dry-reviewer`／`style-reviewer`／`label-checker`／`xss-reviewer`／`secret-reviewer`／`test-coverage-reviewer`／`performance-reviewer`を並列起動（`auth-reviewer`／`injection-reviewer`／`dependency-reviewer`は変更範囲外のため対象外） |
| 3種別×全状態の描画分岐 | 既存`goalStatus.ts`・`goalCategoryVariant`相当のパターンに揃える | 新規分岐は既存の判定関数（`isClosedGoalStatus`等）を再利用し、独自の状態判定を作らない |
| AI未設定時の表示パターン | `useAiConfigured`／`AiUnconfiguredNotice`の既存パターン | そのまま適用（AI一文の項目のみ省略、カード自体は生成可能） |

## 2. 現状のベースライン（開発前、2026-11-11、`dev/2026-11-11`＝`main` 2.8.0起点で確認）

- バックエンド：`ruff check .` 0件。`pytest --cov=app` **2,269件合格、カバレッジ100%**。
- フロントエンド：`npx oxlint src/` 0件。`npx tsc -b` 0件。`npm run test`（vitest）**186ファイル／1,574件合格、カバレッジ100%**（Statements/Branches/Functions/Lines）。
- 先行して`dev/2026-11-08`で実行した同種の確認では`pytest`に1件の失敗（`test_run_tests_writes_coverage_data_outside_backend_dir`）が出たが、原因は本機能と無関係のブランチ分岐（同ブランチは既に2回`main`へマージ済みで取り残しの状態）。`main`起点の`dev/2026-11-11`へ作業ブランチを変更して解消済み（`dev/2026-11-08`は削除せず残置）。

## 3. 作業Todo

凡例：`[ ]` 未着手、`[x]` 完了。各項目の完了条件は「テストが通ること」と「カバレッジ100%（例外処理を除く）」。

### 3.1 文書改訂

- [x] D-01 要件定義書：新設節、改訂履歴（2026-11-11、6.21 R-154〜R-159、改55）
- [x] D-02 仕様書：機能一覧、SC-03・SC-13改訂、設定項目、改訂履歴（2026-11-11、EXP-06、AI-19〜21、改67）
- [x] D-03 設計書（ロジック・プロンプト編）：処理フロー、プロンプト3種、検証、STRIDE、改訂履歴（2026-11-11、28章新設、旧28章「未決事項」を29章へ採番替え、改69）
- [x] D-04 設計書（データ構造編）：設定キー、`AiPurpose`/`ConversationScope`、改訂履歴（2026-11-11、改69）
- [x] D-05 実装フェーズ分割計画書：Phase 51（2026-11-11、改30）
- [x] D-06 OPERATIONS.md：必要性を判断（2026-11-11、新規の運用手順は無いため追記不要と判断。既存のPAT/release手順に変更なし）

### 3.2 バックエンド実装

- [x] B-01 列挙・設定キーの追加（`AiPurpose`/`ConversationScope`各3値、`ai.assistant_uid.summary_card`）（2026-11-11）
- [x] B-02 シード：アシスタント既定値、プロンプト本文（`prompt_texts.SUMMARY_CARD_SENTENCE`系3種）（2026-11-11）
- [x] B-03 `metrics_service.compute_longest_consecutive_report_days`の実装とテスト（BUFFER/OFF日の扱いを既存関数と揃える境界値テストを含む）（2026-11-11、`test_metrics_service.py`に5件追加）
- [x] B-04 `summary_card_service.py`：期間内集計の束ね（記録日数・最長連続日数・テーマ頻度・節目）、WORKでのテーマ頻度省略分岐（2026-11-11）
- [x] B-05 `summary_card_service.py`：AI一文生成（匿名化・一般化指示、利用者操作時のみ呼ぶ、`send_and_log`経由）（2026-11-11、使い捨てチャット方式、`discard_conversation`で後始末）
- [x] B-06 API：`GET /goals/{goal_id}/summary-card`、`POST /goals/{goal_id}/summary-card/sentence`、ドメイン例外→API層変換（2026-11-11）
- [x] B-07 設定の配線：`settings_service`・`schemas/setting.py`（2026-11-11、既存の汎用ラウンドトリップテストでカバレッジ100%を確認済み）
- [x] B-08 セキュリティテスト：期間の不正値（2026-11-11、`test_api_summary_card.py::test_get_summary_card_rejects_from_after_to`等で検証。他目標IDへの不正アクセスは既存の`goal_service.get_goal`の404処理を再利用、単一利用者前提のため追加の認可境界は無し）
- [x] B-09 匿名化テスト：（2026-11-11、`test_api_summary_card.py::test_get_summary_card_returns_aggregate_and_excludes_diary_body`で日記本文がレスポンス文字列に一切含まれないことを確認）

### 3.3 フロントエンド実装

- [ ] F-01 `api/summaryCard.ts`、型の生成し直し（`npm run generate:api-types`）
- [ ] F-02 `features/summaryCard/`：期間選択の純粋関数とテスト（既定期間の算出、プリセット切替）
- [ ] F-03 `features/summaryCard/`：カード項目の表示/非表示トグル状態とテスト
- [ ] F-04 `features/summaryCard/`：SVGカード構築の純粋関数とテスト（`GoalRoadmapMini`の埋め込み、AI未設定時・節目0件時・テーマ0件時の省略表示）
- [ ] F-05 `features/summaryCard/`：SVG→PNG変換・クリップボードコピーのユーティリティとテスト（フォント読み込み待ち、非対応環境のフォールバック）
- [ ] F-06 `SummaryCardSection`コンポーネントと描画テスト（プレビュー表示、AI一文生成ボタンの明示操作、保存・コピーボタン）
- [ ] F-07 `pages/GoalDetailPage.tsx`・`pages/KnowledgeExportPage.tsx`への組み込みと描画テスト
- [ ] F-08 設定画面：`assistantFields.ts`の追加、フィクスチャ更新
- [ ] F-09 `ja.json`／`en.json`：`summaryCard.*`一式
- [ ] F-10 `npm run lint`（oxlint 0件）・`npx tsc -b`（0件）・`npm run test`（カバレッジ100%）

### 3.4 検証

- [ ] V-01 ruff・pytest・vitest（新規機能のカバレッジ100%。全体の最終実行は§9）
- [ ] V-02 既存DBからのアップグレード確認（スキーマ変更なしのため影響なしのはずだが、起動確認で裏付ける）
- [ ] V-03 実機テスト：3種別（EXAM/READING/WORK）×目標完了時／期間指定の各組み合わせでカード生成→PNG保存→クリップボードコピーを確認
- [ ] V-04 実機テスト：AI未設定時でもカードが生成できることを確認
- [ ] V-05 配布物への同梱確認（新規の静的資産追加は想定なしのため、既存のビルド構成で問題ないことを`backend/tests/test_build_package.py`で確認）
- [ ] V-06 フルスキャンの再確認（横展開：§1.4の各項目が実装に反映されているか）

## 4. 処理フロー（確定版）

1. 利用者が`GoalDetailPage`（期間指定）または`KnowledgeExportPage`（目標完了時、既定期間）でカードセクションを開く。
2. フロントが`GET /goals/{goal_id}/summary-card?date_from=&date_to=`を呼び、記録日数・最長連続記録日数・テーマ頻度（EXAM/READINGのみ）・達成した節目・道のりマップ用の進捗比率を取得する（AI呼び出しなし）。
3. プレビューを表示。利用者は項目ごとに表示/非表示を切り替えられる（フロント状態のみ）。
4. AI設定済みの場合のみ「AIに一文を選んでもらう」ボタンを表示。押すと`POST /goals/{goal_id}/summary-card/sentence`を呼び、期間内の記録・振り返り本文を入力として、匿名化・一般化された一文を生成する（`send_and_log`経由、1回限り。再生成は再度ボタンを押したときのみ）。
5. 完成したプレビューから「PNG保存」または「コピー」を選択。フロントでSVGを構築→フォント読み込み待ち→canvas経由でPNG化→`downloadBlob`またはクリップボードAPIへ。
6. アプリから外部への直接送信は行わない（手元のPNG・クリップボードを利用者自身が社内チャットへ貼る）。

## 5. 検証の基準

| 指標 | 基準 |
| --- | --- |
| 匿名化対象情報（日記本文・AI対話履歴・固有の事情）のカードへの混入 | 0件（レスポンススキーマ・テストで保証） |
| AI未設定時のカード生成可否 | 生成可能（AI一文の項目のみ省略） |
| 3種別×2トリガー（目標完了時／期間指定）でのカード生成 | 全組み合わせで生成可能 |
| PNG画像の日本語フォント描画 | 文字欠け・豆腐表示なし（実機確認） |

## 6. 既知のリスクと対策

| リスク | 対策 |
| --- | --- |
| AI一文が原文に近い言い回しのまま出力され、匿名化が実質機能しない | プロンプト指示で「要約・一般化し、原文の言い回しをそのまま使わない」ことを明示。既存の`build_anonymize_instruction`と同水準の指示文とし、過度な期待（完全な機械検証）は置かない |
| PNG化時のフォント未読込による文字欠け | `document.fonts.ready`を待ってから`canvas.drawImage`。実機（Windows・Chrome系WebView2）で確認 |
| クリップボードAPI非対応環境（非HTTPS等） | `navigator.clipboard`の存在確認とtry/catch。失敗時はトーストで保存のみ案内 |
| 期間指定でレコードが0件の目標を選んだ場合の空表示 | 「対象期間に記録がありません」の文言を用意し、0件でもエラーにしない |
| 新規AI用途の追加によるプロンプト注入リスク | 既存の`ai_context_common`の構築パターンをそのまま使用。新規の文字列結合処理を増やさない |

## 7. 完了の定義

- 全項目（§3）が`[x]`になり、テストが通る（バックエンド・フロントエンドとも）。
- カバレッジは例外処理を除き100%。
- §5の基準を満たすか、未達の場合は理由と対応を§9に記録する。
- 文書（§1.3）が実装と一致する。

## 8. 作業記録

（作業の進行に応じて追記する）

- 2026-11-11：工程1（前提資料読込・ベースライン記録）・工程2（フルスキャン）完了。backend/frontendともテスト全green（詳細は§2）。工程3として本Todoを作成。未決定だった2論点（期間指定の対象範囲、AI一文の生成方式）は利用者確認により確定（§0 U2・U5）。作業ブランチは`dev/2026-11-08`の分岐問題を検出したため`main`起点の`dev/2026-11-11`へ変更済み。
