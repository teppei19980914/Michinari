# 開発TODO：日次報告下書き保持の不具合修正・影響範囲確認

作成日: 2026-09-19
対象: 2026-09-18〜19に実施された「日次報告の下書きが黙って上書きされる」系の不具合修正（`dev/2026-09-19`ブランチ、コミット `f0cbaee`〜`66948b1`、37d7220からの差分11ファイル）についての全ソースコードフルスキャン・デグレ確認・横展開漏れ確認
前提: 0〜3章は当初調査時点（コード変更なし）の記録。ユーザー承認を受け、4章の残TODO3件はテストファイルのみ修正して対応済み（2026-09-19、詳細は4章）。本番コード（`app/`・`src/features`等の実装本体）の変更は無い。

---

## 0. スキャン範囲・方法

- 対象コミット範囲: `37d7220`（2026-09-18 PR#43マージ、前回セッション終了時点）〜`66948b1`（2026-09-19 11:30、現HEAD）。`git diff --stat 37d7220 HEAD`で変更ファイルを特定（11ファイル、881 insertions / 58 deletions）。
- **実際の本番コード変更はこのうち2ファイルのみ**（`useDailyReportDraft.ts`／`useWorkReportDraft.ts`）。残りはテスト新規追加7件、`docs/OPERATIONS.md`の記述訂正1件、`vite.config.ts`のコメント訂正1件（カバレッジ除外理由の文言修正のみ、除外対象自体は変更なし）。
- 横展開チェック: `frontend/src`全体で`useEffect`を使用しているファイルを`Grep`で洗い出し（6件）、1件ずつ内容を確認。
- リグレッションスキャン: フロントエンド全テスト（`npx vitest run`）・カバレッジ付きテスト（`npm run test`）・lint（`npm run lint`）・型検査（`npx tsc --noEmit`）、バックエンド全テスト（`pytest`）・lint（`ruff check .`）を実行し、結果を3章に記録。

---

## 1. 今回修正された不具合（事実確認）

同一の根本原因（**「クエリの再取得（refetch）をトリガーに、確認済みのはずのuseEffectが未保存の下書き入力を黙って上書きする」**）に基づく2件の不具合が別画面で修正されていた。

### 1.1 `useDailyReportDraft.ts`（SC-06/SC-07共通の下書きフック）
- **症状**: 日次報告画面（SC-06）を開いたまま、アプリ内遷移で目標詳細画面等へ移動し、読書目標・書籍を新規作成してから日次報告画面へ戻ると、新しく増えた書籍の入力欄が値を持たないまま表示され、実績が空のまま「報告済み」で確定できてしまっていた（2026-09-18発覚）。原因は`hydrate`（下書きの初期化）が`storeKey`単位で1回きりの設計だったため、`DailyReportDraftProvider`がApp全体で1つを共有する構成のもとでは、hydrate後に増えた教材・書籍・案件・目標のidに対応する下書き値が一度も作られなかったこと。
- **修正内容**: `backend/app/services`側は無変更。フロントのみ、`useHydrateDraftOnce`（初回hydrate、従来ロジックのまま切り出し）と`useMergeNewlyCreatedEntries`（hydrate後に新規追加されたidだけを補う、既存の下書き値は上書きしない）の2つのeffectに分離（`frontend/src/features/record/useDailyReportDraft.ts:71-169`）。
- **影響範囲**: `useDailyReportDraft`の呼び出し元は`DailyReportPage.tsx`（SC-06）と`ProgressOnlyPage.tsx`（SC-07）の2箇所のみ（`Grep`で確認済み、他に呼び出し元なし）。両方に同一パターンの回帰テストが追加済み（`DailyReportPage.test.tsx`「shows the reading log fields for a reading goal created after the page was already open」、`ProgressOnlyPage.test.tsx`同名テスト）。**横展開は完了している。**

### 1.2 `useWorkReportDraft.ts`（月次報告・半期評価のレビュー用フォーム下書き）
- **症状**: 月次報告・半期評価のレビュー用フォーム（GoalDetailPage 案件情報タブ）で、`report`クエリがバックグラウンド再取得されるたび（ウィンドウ再フォーカス等）、内容が変わっていなくても新しいオブジェクト参照になるため、`useEffect`が毎回`applyReport`を呼び、入力途中（未保存）の修正内容が黙って取得済みの値へ巻き戻されていた。
- **修正内容**: 最後に反映した`period_key`を`useRef`で追跡し、`report.period_key`が実際に変わった（初回表示・対象期間の切替）ときだけ`applyReport`する条件に変更（`frontend/src/features/goal/useWorkReportDraft.ts:36-59`）。
- **影響範囲**: `useWorkReportDraft`の呼び出し元は1箇所のみ（`WorkReportTab`、`Grep`で確認済み）。回帰テストは`useWorkReportDraft.test.ts`に新規追加。

---

## 2. 横展開チェック結果（同根バグの他箇所への残存有無）

`frontend/src`全体で`useEffect`を使用するファイルは以下6件のみ（`Grep "useEffect" frontend/src`で全量確認）。1件ずつ「クエリ再取得で未保存の入力を上書きしうるか」を確認した。

| ファイル | 用途 | 判定 |
| --- | --- | --- |
| `features/record/useDailyReportDraft.ts` | 下書きhydrate/マージ | **今回修正済み** |
| `features/goal/useWorkReportDraft.ts` | 月次/半期報告フォーム下書き | **今回修正済み** |
| `pages/DashboardPage.tsx` | 目標タブの初期選択（`selectedGoalId===null`の間だけ設定） | 対象外。既存選択を上書きする経路がなく、入力データの保持とは無関係 |
| `pages/CalendarPage.tsx` | 目標タブの初期選択（同上パターン） | 対象外。同上 |
| `features/record/useGoalReportTabs.ts` | （2026-09-17改修で`useEffect`は既に廃止済み、描画中の導出値に変更済み） | 対象外。コード実体に`useEffect`は存在しない（コメント内の過去形の言及のみが`Grep`にヒット） |
| `features/record/useUnsavedChangesWarning.ts` | `beforeunload`イベントリスナーの登録・解除 | 対象外。クエリ再取得とは無関係な副作用管理 |

**結論**: 「クエリ再取得が未保存の下書き・フォーム入力を上書きする」という同根の不具合パターンは、修正済みの2箇所以外に存在しない。横展開漏れなし。

なお、`features/goal/BookTab.tsx`（書籍タブの編集フォーム）は`useState(初期値)`のみで`useEffect`による同期を持たないため、同じ不具合クラスには該当しない（逆に、`book`クエリが再取得されても編集中の値は上書きされない設計であり、今回の2件とは独立して安全側）。読書の読了レポート・資格試験の総括レポートは編集可能な下書きフォームを持たない（生成→表示のみ）ため対象外。月次報告・半期評価のような「AI生成結果をその場で編集して保存する」フォームは仕様上`WorkReportTab`（仕事目標）のみであり、読書・資格試験に同型のフォームは存在しない。

---

## 3. リグレッションスキャン結果

### 3.1 フロントエンド
- `npx vitest run`（カバレッジ無し、全体）: **118 test files / 1031 tests 全通過**。
- `npm run test`（カバレッジ付き、全体）: **1030/1031 通過、1件失敗**（`CalendarPage.test.tsx`「starts on the current month and steps back and forward」がタイムアウト）。ただし同テストを単体実行すると578msで正常通過し、`CalendarPage.tsx`は今回の差分に含まれない。カバレッジ計測による全体実行時間の増加（約68秒）が原因の**既存のタイミング起因のflaky test**と判断（今回の修正が原因ではない）。カバレッジ実測は本ドキュメントの主目的ではないため深追いしていないが、次回のデプロイチェック実行時にも再現するようであれば別途対応要（4章参照）。
- `npm run lint`（oxlint）: 警告5件、いずれも今回の差分ファイルとは無関係な既存警告（`Toast.tsx`・`dailyReportDraftStore.tsx`のfast-refresh警告3件、`HelpPage.tsx`のuse-memo警告1件）。`max-lines-per-function`・`max-depth`は0件を維持（OPERATIONS.md記載の基準を満たす）。
- `npx tsc --noEmit`: エラー0件。

### 3.2 バックエンド
- 今回の差分にバックエンドファイルは含まれない（`backend/pyproject.toml`のworking tree差分は調査時点で解消済み・実質差分なし）。
- `ruff check .`: **All checks passed**。
- `pytest`（カバレッジ計測込み）: **1396 passed**、行カバレッジ・分岐カバレッジともに**100%**を確認。

### 3.3 デグレ判定
上記の結果から、今回の2件の不具合修正によるデグレは検出されなかった。唯一の異常（3.1のCalendarPageタイムアウト）は今回の変更と無関係の既存flaky testであり、単体実行では再現しない。

---

## 4. 残TODO（2026-09-19 対応済み）

いずれも今回の不具合修正がブロッカーになるものではなく、スキャン中に副次的に見つかった小さな債務。ユーザー承認（「不具合修正や残TODOも含めて、要件の取り込みをお願いします」）を受け、3件とも対応済み。

- [x] `CalendarPage.test.tsx`「starts on the current month and steps back and forward」が、カバレッジ計測込みのフルスイート実行時にまれにタイムアウトする件。単体実行では578msで正常終了し、`CalendarPage.tsx`本体（今回の差分外）に問題は無いと判断。実装側を変更せず、このテストのみ既定5000ms→15000msへ個別に猶予を広げた（`it(name, fn, 15000)`。CODING_RULES.md「実時間の当たり外れに検証を委ねないこと」と同じ考え方で、間隔を切り詰める側ではなく余裕を確保する側で対応）。他ファイルに`testTimeout`個別指定の前例は無かったため横展開はせず、このテスト固有の対応とした。
- [x] `ProgressOnlyPage.test.tsx`実行時の`Query data cannot be undefined`警告（`previous-reading-log`/`previous-work-log`）。原因はテスト側の設定漏れで、`DailyReportPage.test.tsx`の`setupQueries`（169〜171行目）が`getPreviousReadingLog`/`getPreviousWorkLog`に既定値`null`を与えているのに対し、`ProgressOnlyPage.test.tsx`の`setupQueries`には同じ既定値が無く、`vi.mock('../api/records')`のautomockが`undefined`を返していたことによる横展開漏れそのものだった。`ProgressOnlyPage.test.tsx`の`setupQueries`に同じ既定値`null`を追加して解消（プロダクションコードの変更は無し）。
- [x] `An update ... was not wrapped in act(...)`警告2件。原因は異なる2件だった。
  - `ExamResultPage.test.tsx`: `setDate`ヘルパーがネイティブのvalueセッター経由でinputイベントを手動発火しており、`@testing-library/react`の`act()`でラップされていなかった（`userEvent`/`fireEvent`は自動でactラップするが、生の`dispatchEvent`はラップされない）。`act(() => {...})`で囲んで解消。同じ手動dispatchパターンは他ファイルに無いことを`Grep`で確認済み（横展開対象なし）。
  - `TodayMessage.test.tsx`: 3箇所で`vi.waitFor`（ReactのactやDOM再描画を意識しないVitest汎用のポーリングユーティリティ）を使っていたため、クエリ解決に伴う状態更新がactの外側で起きていた。`@testing-library/react`の`waitFor`（act対応）へ置き換えて解消。`vi.waitFor`の使用箇所はこの3件のみで、他ファイルは元々全て`@testing-library/react`の`waitFor`を使っていたことを`Grep`で確認済み（このファイルだけの孤立した逸脱であり、横展開対象なし）。

**確認結果（3件対応後）**: フロントエンド全体`npm run test`（カバレッジ込み）で118ファイル1031テスト全通過、カバレッジ100%（Statements/Branches/Functions/Lines）維持、コンソール警告0件。`npm run lint`は今回の変更と無関係な既存警告5件のみ（変化なし）。`npx tsc --noEmit`エラー0件。バックエンドは対象外（変更なし）。

---

## 5. 前回セッション（初日体験改善: A〜D）との関係

前回提示した「はじめの一言」「初日のAI応答強化」「週次ダイジェストのホーム表示」「記録状況カレンダー」（A〜D）の実装計画は、今回スキャンした2ファイル（`useDailyReportDraft.ts`／`useWorkReportDraft.ts`）とは重複・依存関係が無い（A〜Dはダッシュボード・週次要約・AIプロンプト関連で、今回の修正対象は日次報告の下書き状態管理）。**前回提示した確認事項への回答が得られ次第、A〜Dの実装計画はそのまま有効である。**
