### Phase 23：仕事フロントエンド

| 項目 | 内容 |
| --- | --- |
| 目的 | 仕事目標の作成・記録・閲覧をUIで可能にする |
| 投入文書 | CLAUDE.md、運用設計ルール、仕様書（Phase19で反映した仕事関連節） |

**実装対象**

- [x] 目標作成フォームの種別選択に「仕事」を追加。選択に応じた入力項目の出し分け → `GoalsListPage.tsx`の`GOAL_CATEGORIES`に`WORK`を追加
- [x] 目標詳細画面：仕事目標用のタブ構成（基本情報＋案件情報の簡略構成、月次報告タブ・半期評価タブ）→ `GoalDetailPage.tsx`に`WORK_TABS`を追加、新設`WorkAssignmentTab.tsx`が案件情報の登録・編集を、新設`WorkReportTab.tsx`が月次報告・半期評価の生成・閲覧を担う
- [x] 日次報告画面：アクティブな仕事目標がある場合の入力欄分岐（業務記録の自由記述）→ `WorkLogFields.tsx`（新設）を`DailyReportPage.tsx`に統合。資格試験の`/chat`・読書の`/reading-chat`とは別に仕事用の`/work-chat`対話パネルも追加
- [x] 月次報告・半期評価の表示・(再)生成ボタン、対象期間の選択、`work_log`の時系列一覧表示 → `WorkReportTab.tsx`、`DailyReportViewPage.tsx`に`WorkLogSummaryList.tsx`（新設）
- [x] 月次報告・半期評価のレビュー用フォーム（要件定義書R-82・R-83）：`target_goal_text`・`business_summary`・`achievement_score`（選択式）・`achievement_reflection`・`next_goal_text`・`report_notes`（月次報告のみ）を編集可能な入力欄として表示し、「保存」で`PATCH`を呼び出す → `WorkReportTab.tsx`に統合
- [x] 「Markdownをダウンロード」ボタン：保存済みの`body`をブラウザでファイルダウンロードする（新規バックエンドエンドポイントは設けない。フロントエンドでBlob生成） → `WorkReportTab.tsx`。`DataManagementPage.tsx`と共通の`downloadBlob`ユーティリティを新設し重複を回避（CLAUDE.md DRYの原則）
- [x] ダッシュボード：仕事目標の表示（ノルマではなく経過日数・直近記録日・連続記録日数・直近の月次報告有無の軽量表示）に加え、月次報告タブへ直接遷移するボタンを追加 → `GoalCardList.tsx`に`WorkGoalCard`を追加。今日の一言が仕事目標にも表示されることを確認（読書は非表示のまま）
- [x] ナレッジエクスポート画面：仕事目標が対象目標の選択肢に表示され、複数期間の月次報告・半期評価が一覧表示されることの確認 → `KnowledgeExportPage.tsx`にWORK分岐を追加。実装過程で`export_service.py`がWORK目標に一切対応していなかった設計不足（`RetrospectiveSection`がWORKに対して恒久拒否となった`generate_retrospective`を呼び出しクラッシュする経路）を発見し、バックエンドに`_build_work_export_data`等を追加して解消
- [x] ロケールファイル（ja.json）への文言追加 → `goals.new.category.*`・`goals.workAssignment.*`・`goals.workReport.*`・`dailyReport.workLog.*`・`dailyReport.workChat.*`・`dailyReportView.workLog.*`・`dailyReportView.workChatHistory.*`・`dashboard.goalCard.*`・`knowledgeExport.*`の仕事向けキー・`errors.WORK_ASSIGNMENT_ALREADY_EXISTS`を追加
- [x] 目標一覧（SC-02）での種別表示（種別バッジ等）の詳細デザインを決定する（未決事項S-10の解消）→ S-08（読書）と同じテキストラベル方式を踏襲し一部解消（詳細は仕様書S-10参照）。色付きバッジは見送り

**完了条件**

- [x] 種別に仕事を選ぶと、資格試験用の入力項目（科目・教材等）が一切表示されない
- [x] 日次報告で仕事目標の業務記録入力ができ、確定後は読み取り専用になる
- [x] 月次報告・半期評価が画面から生成・閲覧でき、過去の期間も選択して閲覧できる
- [x] 全UI文言がロケールファイルから供給される
- [x] 既存の資格試験用・読書用画面の表示・動作に変化がない（バックエンド・フロントエンド双方の既存テストが無改修で通過）

**注意点**

- 文字列リテラルをコンポーネントに直接書かない
- 実行環境の制約でヘッドレスブラウザによる実画面確認が困難な場合は、Phase17と同様に自動テストで代替し、実画面確認はPhase24に委ねる

**Phase23完了（2026-09-05）。**API層（`api/goals.ts`・`api/closure.ts`・`api/records.ts`）に案件情報・月次報告・半期評価・work-chat用の型・関数を追加。`WorkAssignmentTab.tsx`・`WorkReportTab.tsx`・`WorkLogFields.tsx`・`WorkLogSummaryList.tsx`・`workLogForm.ts`（新設、`readingLogForm.ts`と対のユニットテスト`workLogForm.test.ts`を含む）を新設し、`GoalDetailPage.tsx`・`DailyReportPage.tsx`・`DailyReportViewPage.tsx`・`GoalCardList.tsx`・`CloseGoalModal.tsx`・`KnowledgeExportPage.tsx`にWORK分岐を統合した。実装過程で2件の設計不足・不具合を発見し合わせて修正：(1) `export_service.py`がWORK目標に一切対応しておらず、ナレッジエクスポート画面から総括レポート生成を呼び出すと`generate_retrospective`のWORK恒久拒否ガード（Phase22実装）によりクラッシュする経路があったため、`_build_work_export_data`・`_render_work_markdown`等をバックエンドに追加、(2) ナレッジエクスポートの概要欄が案件名（`goal.name`、必須）ではなく取引先呼称（`work_assignment.client_name`、任意項目でNULL可）を表示しており、取引先呼称が未入力の案件では概要が空欄化していたため、`_build_work_assignment`に`goal.name`を含めるよう修正。バックエンド全886テスト・カバレッジ100%・ruff検査通過、フロントエンド全126テスト・`tsc -b`・oxlint（既存の無関係な警告2件を除き0件）を確認済み。ヘッドレスブラウザでの実画面確認は実行環境の制約により見送り、かわりに独立したSQLiteデータベースを用いた別ポートのバックエンドインスタンス上で実APIを用いたエンドツーエンドのスモークテスト（目標作成→案件情報登録→着手→日次業務記録→ダッシュボード反映→月次報告の手動シード（PATCH）→クローズ→ナレッジエクスポートプレビュー）を実施し、既存の本番データベース・利用中セッションには一切影響を与えないことを確認したうえで実施した。次はPhase 24（仕事機能 実環境検証、テッペイさんの手元で実施）に進む。

---

