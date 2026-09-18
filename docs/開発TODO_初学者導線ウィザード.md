# 開発TODO：初学者導線（ウェルカム画面・簡易作成・資格ウィザード）

作成日: 2026-09-17（2026-09-18復元）
対象: 非エンジニア向け初回起動導線の追加（ウェルカム画面／読書・仕事の簡易作成／資格テンプレート＆ウィザード／上級設定の折りたたみ）
前提: 本ドキュメント作成時点ではソースコードは一切変更していない（調査・計画のみ）。実装は本ドキュメントに沿って進める。

## 0. 確定した設計方針（前提の再掲）

- 目標一覧画面(SC-02)の「新規目標作成」は EXAM/READING/WORK すべて新UIに統一する（旧3項目モーダルは廃止）。EXAM→資格ウィザード、READING/WORK→簡易1画面フォーム。
- ウィザードStep4で既存スロットがある場合は、簡易入力の代わりに既存のリソース配分UI相当を埋め込み表示し、配分合計>0分でないと次へ進めない。
- スロット自動生成は**フロントエンドで時刻を計算し、既存の`POST /resources/slots`をそのまま2回呼ぶ**方式とする（バックエンドに新規エンドポイントを作らない。DRY・シンプルさ優先）。
- 資格テンプレートは6件（ITパスポート／基本情報／応用情報／情報処理安全確保支援士／ネットワークスペシャリスト／データベーススペシャリスト）。科目構成は令和8年度のCBT名称（科目A-1/A-2/B-1/B-2等）、合格基準60%（ITパスポート分野別のみ30%）。**情報源は資格対策専門サイトの複数一致であり、IPA公式試験要綱PDFでの最終確認を推奨**（画面文言に「要確認」注記を出す）。
- 初回起動判定はDBの全goal行数（DRAFT/CLOSED/ARCHIVED含む）が0件かどうかで都度判定。永続フラグは持たない。
- DBスキーマ変更なし。既存の目標詳細画面(GoalDetailPage/SC-03)は編集経路として維持する。

---

## 1. バックエンド

### 1.1 資格テンプレート機能（新規）✅2026-09-18実装済み
- [x] `backend/app/templates/exams/{it_passport,fe,ap,sc,nw,db}.json` 新規作成（6件）
- [x] `backend/app/schemas/exam_template.py` 新規作成（`ExamTemplateSubject`/`ExamTemplateMaterial`/`ExamTemplateRead`）
- [x] `backend/app/services/exam_template_service.py` 新規作成（`list_exam_templates(directory=None)`。不正ファイルは警告ログを出して読み飛ばし、他の正常なテンプレートは読み込む）
- [x] `backend/app/api/exam_templates.py` 新規作成：`GET /exam-templates`
- [x] `backend/app/main.py`：import（`errors`と`export`の間）・`include_router`（`goals_router`直後）を追加
- [x] `backend/app/constants/bundle.py`：`EXAM_TEMPLATES_DIR_NAME`追加
- [x] `backend/scripts/build_package.py`：`EXAM_TEMPLATES_SOURCE_DIR`定義＋`add_data`へ追記（`backend/tests/test_build_package.py`に同梱確認テストも追加済み）
- [x] テスト: `backend/tests/test_exam_template_service.py`（正常読込／構文エラー1件のみ読み飛ばし／スキーマ不一致読み飛ばし／不正1件+正常1件混在／空・不存在ディレクトリ）
- [x] テスト: `backend/tests/test_api_exam_templates.py`
- [x] `pytest --cov-fail-under=100`：1396件全通過・カバレッジ100%を確認済み。`ruff check .`も全通過
- 実装中の判明事項：「Phase37」は既にデスクトップ常駐・通知機能で使用済みだったため、本機能は**Phase38**とする（docstring・TODO内の記載を修正済み）

### 1.2 ウィザードからのAPI呼び出し（バックエンド変更なし、確認のみ）
- [ ] 既存エンドポイントをそのまま利用できることを再確認：`POST /goals` → `POST /goals/{id}/subjects`（科目数分） → `POST /goals/{id}/materials`（教材数分） → `PUT /goals/{id}/slot-allocations` → `POST /goals/{id}/activate`
- [ ] 途中で失敗した場合、目標はDRAFTのまま`GoalsListPage`に残り、`GoalDetailPage`から手動続行できることを確認（フロント側で「ウィザードが失敗しても目標自体は消えない」旨のエラーメッセージ設計に反映）

### 1.3 読書・仕事の簡易作成（バックエンド変更なし）
- [ ] `POST /goals`(category=READING) → `POST /goals/{id}/book` → `POST /goals/{id}/activate`
- [ ] `POST /goals`(category=WORK) → `POST /goals/{id}/work-assignment` → `POST /goals/{id}/activate`
- [ ] READING/WORKは`activate_goal`（`backend/app/services/goal_service.py:364-407`）でリソース配分必須チェックが無いことを再確認済み（対応不要）

---

## 2. フロントエンド

### 2.1 ルーティング ✅2026-09-18実装済み
- [x] `frontend/src/constants/routes.ts`：`goalNewExam: '/goals/new/exam'`と`welcome: '/welcome'`を追加
- [x] `frontend/src/App.tsx`：新ルート2件を追加
- [x] 設計変更（ユーザ指示）：ウェルカム画面は独立ルート`/welcome`として実装。`DashboardPage.tsx`は「目標0件なら`/welcome`へ`<Navigate replace>`」の分岐のみ持つ

### 2.2 ウェルカム画面 ✅2026-09-18実装済み
- [x] `frontend/src/pages/WelcomePage.tsx` 新規作成（3カード、資格カードに「設定に5分かかります」、「あとで」でダッシュボードへ）
- [x] `frontend/src/pages/DashboardPage.tsx`：目標0件時のリダイレクト＋`location.state.showFirstRecordBanner`によるバナー表示
- [x] `frontend/src/pages/HelpPage.tsx`：「ウェルカム画面をもう一度見る」リンクを追加
- [x] `WelcomePage.test.tsx`／`DashboardPage.test.tsx`（追加分）／`HelpPage.test.tsx`：全て新規作成し通過確認済み

### 2.3 読書・仕事の簡易作成 ✅2026-09-18実装済み
- [x] `frontend/src/features/goal/QuickCreateGoalModal.tsx` 新規作成。送信時`createGoal`→`createBook`/`createWorkAssignment`→`activateGoal`
  - 開始日は`GET /records/today`（`getToday`）から取得（クライアント側の論理日判断禁止のため。`new Date()`は使わない）
  - バックエンド必須項目（総ページ数・読了目標日・想定業務内容）のうち簡易フォームで未入力のものは`quickCreateGoalDefaults.ts`で暫定値を補う（総ページ数→1、読了目標日→開始日+90日、想定業務内容→案件名）
- [x] `QuickCreateGoalModal.test.tsx`／`quickCreateGoalDefaults.test.ts` 新規
- [x] `dashboard.firstRecordBanner`：`DashboardPage.tsx`で`location.state`経由のバナー表示＋テスト

### 2.4 資格ウィザード ✅2026-09-18実装済み
- [x] `frontend/src/pages/ExamGoalWizardPage.tsx`（描画のみ。状態・API呼び出しは`useExamGoalWizard`フックへ集約）
- [x] `frontend/src/features/goal/examWizard/Step1SelectTemplate.tsx`（テンプレート一覧取得・選択・「その他」手入力）
- [x] `frontend/src/features/goal/examWizard/Step2SubjectsAndDates.tsx`（当初案の「日付入力のみ」から、その他選択時に科目自体を追加できるよう統合。テンプレート選択時は科目が入った状態で日付のみ入力すれば足りる）
- [x] `frontend/src/features/goal/examWizard/Step3Materials.tsx`（教材の確認・追加・削除・編集、目安の免責文言表示）
- [x] `frontend/src/features/goal/examWizard/Step4TimeSlots.tsx`（スロット0件→簡易時間入力／スロットあり→`SlotAllocationTable`再利用の配分入力。抽出作業は不要だった）
- [x] `frontend/src/features/goal/examWizard/Step5Confirm.tsx`
- [x] `frontend/src/features/goal/examWizard/simpleTimeSlots.ts`（平日20:00〜/休日09:00〜、23:59クランプ）
- [x] `frontend/src/features/goal/examWizard/examWizardDrafts.ts`（下書き型・API payload組み立て）
- [x] `frontend/src/features/goal/examWizard/examWizardValidation.ts`（各ステップの「次へ」可否判定）
- [x] `frontend/src/features/goal/examWizard/examWizardSubmit.ts`（科目・教材の作り直し、スロット新規作成+配分の実処理）
- [x] `frontend/src/features/goal/examWizard/useExamGoalWizard.ts`（状態・クエリ・ステップ遷移ハンドラの統括フック）
- [x] `frontend/src/api/examTemplates.ts` 新規（`npm run generate:api-types`実行後に作成、型手書きなし）
- [x] `frontend/src/pages/GoalsListPage.tsx`：新規作成を`NewGoalEntryModal`に置換（EXAM→ウィザード遷移、READING/WORK→QuickCreateGoalModal）
- [x] 各コンポーネントの単体テスト（Step1〜5、drafts/validation/submit/simpleTimeSlots）＋`ExamGoalWizardPage.test.tsx`（一連の流れ・既存スロット分岐）＋`GoalsListPage.test.tsx`書き換え、全通過
- 実装中の判明事項：
  - `MaterialCreate`は`due_date_is_manual`/`required_environment`/`quality_metric_type`が必須項目（OpenAPI生成型）。ウィザードでは既定値（false/ANY/NONE）を明示送信し、締切は科目の受験日から自動導出させる
  - `resolveQuickBookDueDate`相当の日付演算で`new Date().toISOString()`をローカル時刻の`Date`と混在させるとタイムゾーンにより1日ずれるバグを発見・修正（`materialDueDate.ts`と同じUTC基準の組み立てに統一）
  - ⚠️**実機確認で発見**：ウィザードの簡易時間設定が生成するスロットの`environment`は元の要件案どおり「制約なし（ANY）」を指定すると`POST /resources/slots`が`VALIDATION_ERROR`で拒否する（`resource_service._validate_slot_fields`が`resource_slot.environment`にANYを許容しない設計のため。ANYは教材側の「必要環境を問わない」を表す値であり、スロット自体の性質を表す列とは意味が異なる）。`PC`（机上のみ）へ変更して是正した。モックのみのフロントエンドテストでは検知できず、`uv run python -m app.main`を隔離DB（`MICHINARI_DATABASE_URL`環境変数）で起動した実機確認で発見した

### 2.5 上級設定の折りたたみ ✅2026-09-18実装済み
- [x] `frontend/src/components/CollapsibleSection.tsx` 新規作成（既定閉、`title`/`hiddenTitle`をpropsで受け取りゼロハードコーディング。`common.action.showAdvanced`/`hideAdvanced`を新設）
- [x] `frontend/src/components/CollapsibleSection.test.tsx` 新規（4件）
- [x] `frontend/src/features/goal/LoadProfileTab.tsx`をCollapsibleSectionでラップ（既定閉）
- [x] `frontend/src/features/goal/MaterialFormFields.tsx`の`MaterialConditionFields`をCollapsibleSectionでラップ（既定閉）
- [x] `frontend/src/features/goal/LoadProfileTab.test.tsx`・`frontend/src/features/goal/MaterialsTab.test.tsx`を「先に展開操作を行う」形に修正（`renderExpandedTab`/`openAdvancedSection`ヘルパーを追加）
- [x] `frontend/src/pages/GoalDetailPage.test.tsx`：タブ切替のみを見るテストのため影響なしを確認（14件全通過）
- [x] `npm run lint`・`npm run test`（vitest）：926件全通過、カバレッジ100%（statements/branches/functions/lines）を確認済み

### 2.6 ロケール（ja.json）新規キー
- [ ] `welcome.*`（説明文・カード文言・あとでボタン）
- [ ] `goals.quickCreate.*`（読書/仕事簡易フォーム）
- [ ] `goals.examWizard.*`（ステップ見出し・ボタン・テンプレート免責文言「目安です。お使いの教材に合わせて変更してください」「時刻は目安です」「要確認：令和8年度試験制度改定に伴う暫定値です」）
- [ ] `goals.materials.advancedSettingsLabel` / `goals.loadProfile.advancedSettingsLabel`（「詳細設定を表示」等）
- [ ] `dashboard.firstRecordBanner`（「最初の記録を書いてみましょう」）
- [ ] ⚠️**`goals.new.category.*`は削除・改名しない**：`GoalsListPage.tsx`の`GoalCard`(117行目)と`frontend/src/features/record/GoalTabBar.tsx`(28行目、Dashboard/Calendar/Analytics/DailyReport等から共通利用)がカテゴリ日本語ラベルの正データとして参照している。`NewGoalModal`廃止で削除してよいのは`goals.new.title`/`categoryLabel`/`nameLabel*`/`startDateLabel`（モーダル固有キー）のみ
- [ ] `frontend/src/locales/ja.json:903`（`help.sections.goals.p1`）を新しい作成導線（ウェルカム画面／簡易フォーム／ウィザード）に合わせて改訂。現行文言は単一モーダル手順の説明で、かつ「仕事」カテゴリの記載が既に漏れている既存バグも同時に修正する

---

## 3. テスト・静的解析（実装後、コミット前に必須）
- [x] `cd backend && ruff check .`（全通過）
- [x] `cd backend && pytest --cov=app --cov-branch --cov-fail-under=100`（1396件、カバレッジ100%）
- [x] `cd frontend && npm run lint`（oxlint、max-lines-per-function/max-depth 0件維持を確認。実装中に2件新規発生→ヘルパー関数への切り出しで解消）
- [x] `cd frontend && npm run test`（vitest、1004件、カバレッジ100%）
- [x] `cd frontend && npx tsc -b`（型チェック。生成型の必須プロパティ不足など3件修正）
- [x] `cd frontend && npx vite build`（ビルド健全性確認）
- [x] `docker build .`：⚠️本プロジェクトに`Dockerfile`は存在しない（配布方式はPyInstallerによるWindows実行ファイル、`backend/scripts/build_package.py`）。CLAUDE.mdのコミット前チェック項目は汎用テンプレートの記載であり本プロジェクトには適用されない。実質的なデプロイゲート（`pytest`・`tsc -b`・`npm test`、`build_package.run_tests()`が実行するのと同じ3点）は全て通過済み
- [x] 横展開チェック：`NewGoalModal`削除に伴う参照箇所を全文検索し、`GoalCard`（117行目）と`GoalTabBar.tsx`（28行目）が`goals.new.category.*`を再利用していることを確認。当該名前空間は削除せず維持。`QuickCreateGoalModal`の利用箇所（WelcomePage・GoalsListPage）が他に無いかも確認済み
- [x] label-checker相当：新規追加した文言は全て`ja.json`経由（`goals.new.quickCreate.*`/`goals.examWizard.*`/`welcome.*`/`common.action.next`等）
- [x] 実機動作確認後の追加レビューで2件の不具合を発見・修正（詳細は2.4「実装中の判明事項」・4.1参照）：(1) スロット自動生成の`environment: 'ANY'`がバックエンドに拒否される、(2)`QuickCreateGoalModal`がキャンセル後の再オープン・カテゴリ切替時に前回の入力値を保持したまま残る（`key`未指定でインスタンスが使い回されるため）。(2)は`key={quickCreateCategory ?? 'closed'}`をWelcomePage・GoalsListPage双方に追加して解消し、回帰テストを追加した

---

## 4. ドキュメント更新 ✅2026-09-18実装済み
- [x] `docs/仕様書_ミチナリ_v1.1.md`：改訂履歴1.1改29追加。SC-16（ウェルカム画面）・SC-17（資格モード作成ウィザード）を画面一覧・6.1.1・6.1.2に新設。6.2に上級設定折りたたみの説明を追記
- [x] `docs/設計書_データ構造編_ミチナリ_v1.1.md`：改訂履歴1.1改23追加。`GET /exam-templates`をエンドポイント一覧に追加。8章ディレクトリ構成に`templates/exams/`を追記
- [x] `docs/実装フェーズ分割計画書_ミチナリ_v1.1.md`：Phase38として新規セクション追加（Phase37は既存のデスクトップ常駐機能で使用済みのため回避）
- [x] `README.md`：「使いはじめる」節にウェルカム画面の案内を追記
- [x] `docs/OPERATIONS.md`：「資格テンプレートの追加・編集」節を新設（JSON構造・追加手順）

## 4.1 実機確認 ✅2026-09-18実施済み

`chromium-cli`等のブラウザ自動操作ツールが本環境に無いため、画面のスクリーンショットによる確認は実施していない。代わりに、隔離した一時DB（`MICHINARI_DATABASE_URL`環境変数で`backend/data/`の実データベースとは別のSQLiteファイルを指定）で実際のバックエンド（`uv run python -m app.main`）を起動し、フロントエンドの各コンポーネントが呼ぶのと**全く同じAPIシーケンス**をcurlで実行して検証した（利用者の実データは一切変更していない）。

- 目標0件（ウェルカム画面が出る条件）を確認
- `GET /exam-templates`が6件返ることを確認
- 資格ウィザードの全ステップ相当（`POST /goals`→科目2件→教材→スロット作成→配分→`activate`）を実行し、目標がACTIVEになること、教材の締切が科目の受験日から自動導出されること（2026-10-31）を確認
- 読書の簡易作成相当（`POST /goals`→`POST /goals/{id}/book`→`activate`）を実行し、`resolveQuickBookDueDate`の暫定値（開始日+90日）が正しく送信され目標がACTIVEになることを確認
- 仕事の簡易作成相当（`POST /goals`→`POST /goals/{id}/work-assignment`→`activate`）を実行し目標がACTIVEになることを確認

**この実機確認で発見した不具合**（上記2.4参照）：スロット自動生成の`environment`に要件どおり`ANY`（制約なし）を指定すると`VALIDATION_ERROR`で拒否される。モックのみのフロントエンドテストでは検知できず、実際のバックエンドに繋いで初めて判明した。`PC`へ修正済み。

## 4.2 追加レビューで発見した不具合 ✅2026-09-18修正済み

実機確認後、もう一段のコードレビューで`QuickCreateGoalModal`の状態管理バグを発見した。WelcomePage・GoalsListPageのいずれも、読書/仕事の簡易作成モーダルを`open`の真偽値だけで開閉し、コンポーネント自体は常にマウントされたまま`category` propだけが変わる実装だったため、①キャンセル後に再度開いても前回の入力が残る、②読書で入力→キャンセル→仕事を選ぶと、読書用に入力した文字列が仕事のフォームに残る、という2つの経路で入力漏れが発生していた（`QuickCreateGoalModal`自身は`onSuccess`時にしか内部stateをクリアしないため）。`<QuickCreateGoalModal key={quickCreateCategory ?? 'closed'} .../>`とし、開閉・カテゴリ切替のたびに別インスタンスとして作り直すよう両画面を修正し、回帰テストを追加した（`WelcomePage.test.tsx`・`GoalsListPage.test.tsx`）。

## 4.3 未実施（次回セッションへの引き継ぎ）
- [ ] ブラウザでの目視確認（画面レイアウト・CSS崩れ等）。本環境に`chromium-cli`等のブラウザ自動操作ツールが無いため、今回はAPIシーケンスの実機確認（4.1）のみで代替した
- [ ] `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1.md`：本開発はAI連携ロジックに変更が無いため対象外と判断（要再確認）

---

## 5. 実装順序（推奨）

1. バックエンド：資格テンプレート（1.1）→ テスト → 動作確認（`GET /exam-templates`が6件返すこと）
2. フロントエンド：CollapsibleSection（2.5、独立性が高く先に作れる）→ LoadProfileTab/MaterialFormFieldsへ適用
3. フロントエンド：QuickCreateGoalModal（2.3、資格ウィザードより単純）→ GoalsListPage組み込み
4. フロントエンド：ウェルカム画面（2.2）→ QuickCreateGoalModal・後述ウィザード導線と接続
5. フロントエンド：資格ウィザード（2.4、最も工数大。ステップ単位で分割実装・分割テスト）
6. GoalsListPageの新規作成導線を最終形に差し替え（2.4末尾）
7. ロケール整備（各ステップと並行、最後に全体grep漏れ確認）
8. テスト・静的解析一式（3章）→ ドキュメント更新（4章）→ コミット前チェック（CLAUDE.md 6項目）

---

## 6. 未確定・実装中に判断が割れやすい点（メモ、いずれも軽微・後戻りコスト低のため未確定のまま進める）

- ITパスポートの合格基準はIRT採点で他5試験と性質が異なる（4科目構成:総合60%+3分野各30%）。`passing_score_type`は他試験同様PERCENTAGEで表現可能だが、画面上「総合評価」と「分野別評価」の区別が利用者に伝わる科目名にする（例:「総合評価」「ストラテジ系（分野別)」等）
- ⚠️`resolveByGoalCategory`（goalCategoryVariant.ts）は`NewGoalModal`専用ではなく、`frontend/src/pages/AnalyticsPage.tsx`(8,85行目)と`frontend/src/pages/GoalDetailPage.tsx`(22,226行目)からも使われている共有ロジック。**削除・シグネチャ変更は禁止**。QuickCreateGoalModal・ExamGoalWizardで同様のラベル切替が必要な場合は、この関数をそのまま呼び出して利用する
- ウィザード離脱時のDRAFT目標が目標一覧に「中途半端な状態」で残る点は仕様上許容するが、一覧画面での見え方（DRAFTバッジ等）が十分分かりやすいか実装後に確認
