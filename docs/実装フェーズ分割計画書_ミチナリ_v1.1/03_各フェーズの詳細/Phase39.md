### Phase 39：仕事目標のチームメンバー管理・評価者ロール・AI評価レポート

| 項目 | 内容 |
| --- | --- |
| 目的 | 仕事目標（案件）にチームメンバーを登録し、評価者ロールの利用者がメンバーの特徴・日々の業務記録・AIフィードバック履歴をもとにAI評価レポートを生成・レビュー・保存できるようにする |
| 投入文書 | CLAUDE.md、docs/CODING_RULES.md、docs/OPERATIONS.md、docs/要件定義書_ミチナリ_v1.1.md（6.11節、R-93〜R-96）、docs/仕様書_ミチナリ_v1.1.md（6.2・6.5・8.1・8.9.1節）、docs/設計書_データ構造編_ミチナリ_v1.1.md（5.1・5.3・5.6・6.2・6.3節）、docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1.md（17.13・22.7節） |

**背景**

利用者から「部下・メンバーの人となりを考慮した現場目線のフィードバック・評価を行いたい」との要望を受けた。本アプリはこれまで一貫して利用者本人のデータのみを扱う設計（単独利用前提）であったため、着手前に技術検証を実施し、第三者PIIの同意ゲート・入力データの技術的制約（`ai_log`が保持期間90日で自動削除されるため`chat_message`を参照する必要があること）・既存`goal_retrospective`との非親和性（グレインの相違）を確認したうえで設計を確定した。

**実装対象**

- バックエンド：新規テーブル`work_member`・`work_evaluation_report`、`work_assignment.role`列（Alembicマイグレーション`6f0e82a9c518`）。新規enum`WorkMemberGender`・`WorkEvaluationRole`、`AiPurpose`/`ConversationScope`への`EVALUATION_REPORT_WORK`追加。新規例外`ConsentRequiredError`・`WorkMemberHasEvaluationReportsError`。新規サービス`work_member_service.py`（同意ゲート・CRUD）・`work_evaluation_service.py`（生成・編集・履歴）、`ai_context_service.py`へ`build_evaluation_member_summary_text`・`build_evaluation_feedback_history_entries`を追加。新規API`work_members.py`、`goals.py`・`closure.py`への追加エンドポイント。プロンプト本文（`prompt_texts.EVALUATION_REPORT_WORK`）・seed_data（新規app_setting・prompt_template）
- フロントエンド：`WorkMemberList`・`WorkMemberForm`・`WorkMemberFormFields`（同意チェックボックスの活性化・リセット制御）、`WorkEvaluationReportTab`とその子（`WorkEvaluationGenerateCard`・`WorkEvaluationReviewCard`・`WorkEvaluationHistoryList`、1関数100行の上限のため分割）、日次報告画面用`WorkMemberSection`。`WorkAssignmentTab`への役割セレクト追加、`GoalDetailPage`の評価レポートタブの動的表示（role=EVALUATORのみ）。`api/goals.ts`・`api/closure.ts`・`queryKeys.ts`の拡張、`openapi-typescript`による型再生成
- ドキュメント：要件定義書R-93〜R-96、仕様書6.2・6.5・8.1・8.9.1、設計書データ構造編5.1・5.3・5.6・6.2・6.3、設計書ロジック・プロンプト編17.13・22.7を更新

**設計判断（技術検証・ヒアリングで確定した論点）**

- メンバー登録・編集は役割を問わず全ての利用者が行える（評価用ボタン・タブのみ役割で制御、要件定義書R-93・R-95）
- 日次報告の単位は目標（案件）単位のまま変更しない。メンバー別の日次記録は導入しない（`work_log`のスキーマ変更なし）
- 評価レポートは生成→人がレビュー・修正→保存の流れとし、月次報告・半期評価と同じ安全弁を設ける（実在の人物の人事評価に使われるため）
- 同意確認の対象は`characteristics`（特徴・性格）のみ。`gender`は対象外（要件定義書に明示的な範囲確定として記載）
- 評価レポートは`goal_retrospective`を流用せず新規テーブルとする（グレインの相違）。構造化パース（`_parse_sections`）は不要と判断し採用しない

**完了条件**

- 仕事目標の案件情報タブでチームメンバーを登録・編集・無効化・削除できる
- 特徴・性格を同意チェックなしで保存しようとするとサーバ側で拒否される（`CONSENT_REQUIRED`）
- 役割を評価者に設定した案件でのみ評価レポートタブが表示される
- メンバーを選択し考慮事項を入力して評価レポートを生成し、内容を確認・修正して保存・ダウンロードできる
- 目標詳細画面・日次報告画面のいずれでメンバーを編集しても、もう一方の画面に同じ内容が反映される

---

**Phase39完了（2026-09-23）。**

- バックエンド：新規テーブル2件・列1件（マイグレーション`6f0e82a9c518`、down_revision=`7f4f5e089f3a`、upgrade/downgradeとも動作確認済み）、新規サービス2ファイル、新規API1ファイル＋既存2ファイルへの追加。新規テストファイル4件（`test_work_member_service.py`・`test_work_evaluation_service.py`・`test_api_work_members.py`・`test_api_evaluation_report.py`）
- フロントエンド：新規コンポーネント8件（`WorkMemberList`・`WorkMemberForm`・`WorkMemberFormFields`・`WorkEvaluationReportTab`・`WorkEvaluationGenerateCard`・`WorkEvaluationReviewCard`・`WorkEvaluationHistoryList`・`WorkMemberSection`）、新規テストファイル5件。`openapi-typescript`による型再生成を実施
- 横展開チェックで、`test_api_errors.py`の全エラーコード・reasonにロケール文言があることを検証するテストが、新規追加した`CONSENT_REQUIRED`・`WORK_MEMBER_HAS_REPORTS`のロケール未追加を検出（`frontend/src/locales/ja.json`の`errors.*`・`errors.reasons.*`へ追加して解消）
- バックエンド1496テスト・新規コード100%カバレッジ（全体99%、既存分に起因する未達1行は本Phase対象外）、フロントエンド1113テスト・カバレッジ100%、`tsc --noEmit`・`ruff check`・oxlint（max-lines-per-function 0件、`WorkMemberForm`・`WorkEvaluationReportTab`はコンポーネント分割で解消）通過

---

