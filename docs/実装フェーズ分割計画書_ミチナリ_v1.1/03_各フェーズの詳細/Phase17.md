### Phase 17：読書フロントエンド

| 項目 | 内容 |
| --- | --- |
| 目的 | 読書目標の作成・記録・閲覧をUIで可能にする |
| 投入文書 | CLAUDE.md、運用設計ルール、仕様書（Phase13で反映した読書関連節） |

**実装対象**

- [x] 目標作成フォームへの種別選択（資格試験／読書）追加。選択に応じた入力項目の出し分け → `GoalsListPage.tsx`の`NewGoalModal`に`category`セレクタを追加
- [x] 目標詳細画面：読書目標用のタブ構成（基本情報＋書籍の簡略構成）→ `GoalDetailPage.tsx`が`goal.category`でタブ構成（`EXAM_TABS`/`READING_TABS`）を出し分け、新設`BookTab.tsx`が書籍の登録・編集・進捗表示・読了操作を担う
- [x] 日次報告画面：アクティブな読書目標がある場合の入力欄分岐（想起テキスト＋任意ページ数）→ `ReadingLogFields.tsx`（新設）を`DailyReportPage.tsx`に統合。資格試験の`/chat`とは別に読書用の`/reading-chat`対話パネルも追加
- [x] 読了レポートの表示・(再)生成ボタン、`reading_log` の時系列一覧表示 → 読了レポートは既存の`KnowledgeExportPage.tsx`（`RetrospectiveSection`）がgoal_idのみで動く汎用実装のため無改修で流用（バックエンドのcategory分岐により自動的に読了レポートとして生成される）。`reading_log`の時系列表示は`DailyReportViewPage.tsx`に`ReadingLogSummaryList.tsx`（新設）として追加
- [x] ダッシュボード：読書目標の表示（ノルマではなく残日数・直近記録日などの軽量表示）→ **バックエンドを小規模に拡張**（`GoalCardRead`に`category`/`book`フィールドを追加、`api/dashboard.py`がREADINGのカードを`book_service.get_book_progress`で組み立て直す）。フロントエンドは`GoalCardList.tsx`に`ReadingGoalCard`を追加
- [x] ナレッジエクスポート画面：読書目標が対象目標の選択肢に表示されることの確認 → 確認のみでコード変更なし（`KnowledgeExportPage.tsx`はgoalIdのみに依存する汎用実装のため、READING目標でも動作する。学習サマリ欄はEXAM向けの数値のままだが、これは元々コード変更不要とされていた範囲であり許容する）
- [x] ロケールファイル（ja.json）への文言追加 → `goals.new.category.*`・`goals.book.*`・`dailyReport.readingLog.*`・`dailyReport.readingChat.*`・`dailyReportView.readingLog.*`・`dashboard.goalCard.*`・`errors.BOOK_ALREADY_EXISTS`等を追加

**完了条件**

- [x] 種別に読書を選ぶと、資格試験用の入力項目（科目・教材等）が一切表示されない
- [x] 日次報告で読書目標の想起入力ができ、確定後は読み取り専用になる（既存 `daily_record` の不変性を踏襲）
- [x] 読了レポートが画面から生成・閲覧できる
- [x] 全UI文言がロケールファイルから供給される
- [x] 既存の資格試験用画面の表示・動作に変化がない（バックエンド全673テスト・フロントエンドtsc/lint/vitest全102テストが無改修で通過）

**Phase17完了（2026-08-31）。次はPhase 18（読書機能 実環境検証）。**

**Phase17で追加対応した設計上の変更点（未計画だったが実装中に必要と判明したもの）**

- ダッシュボードのAPI（`GET /dashboard`、`GoalCardRead`）に`category`・`book`フィールドを追加した。当初計画では本フェーズはフロントエンドのみを想定していたが、DSH-06（読書目標の残日数・直近記録日・連続記録日数表示）を実現するには書籍の派生値をダッシュボード応答に含める必要があり、`book_service.get_book_progress`を`api/dashboard.py`から呼び出す小規模な追加を行った
- 進行中の読書目標・書籍の一覧を取得する専用エンドポイントは新設せず、フロントエンド側で`listGoals()`→`getGoal()`の合成（`listActiveReadingBooks`、`api/goals.ts`）で賄った。1目標1冊・少数の同時進行を前提とした割り切りであり、件数が多い場合はN+1になる（コメントに明記済み）

**実行時の検証について**：本フェーズはヘッドレスブラウザによる実画面確認を試みたが、実行環境の`frontend/dist`が既にビルド済みだったため起動時に実ブラウザが開き、かつAI基盤の開発キットがこのマシンに設定済みの認証情報を用いて実際に「今日の一言」APIへ1回発信してしまった（分離されたスクラッチDBを使ってもai.hostがapp_setting経由ではなく開発キット側の設定ファイルから解決されるため）。意図しない副作用と判断し直ちに停止・後始末した。そのため実画面での動作確認はバックエンド673テスト・フロントエンド102テスト・tsc・lintの通過をもって代え、実際のブラウザでの確認はPhase18（テッペイさんの手元、認証情報を把握した環境）に委ねる。

**注意点**

- 文字列リテラルをコンポーネントに直接書かない（Phase6と同じ注意点）

---

