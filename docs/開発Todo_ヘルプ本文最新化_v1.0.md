# 開発Todo：ヘルプ本文の最新化・拡充・圧縮（検査フェーズ）

本書は、ミチナリAIアシスタント（ヘルプAIアシスタント）の回答精度向上を目的に、「既存機能の全スキャン」と「現行ヘルプ本文（`frontend/src/locales/ja.json` の `help` 名前空間、本文の正）との整合性チェック」を行った結果である。**本セッションでは実装を行わない**。次セッションの開発インプット（Single Source of Truth）として本書を使う。

調査日: 2026-10-10（ブランチ `dev/2026-10-10`）。

## 0. 前提・調査範囲

- ヘルプ本文の正は `frontend/src/locales/ja.json` の `help` 名前空間（15セクション: intro/dashboard/goals/bookshelf/resources/calendar/dailyReport/analytics/examAndExport/aiConnection/settingsOther/desktop/promptVariables/dataManagement/faq）。生成物 `backend/app/content/help_content.json` は `backend/tests/test_help_content.py::test_generated_help_content_matches_ja_json` によりドリフト検出済み（今回時点で一致、生成物を直接読んでも内容は同一）。
- 比較対象: フロントエンド全22ページ、バックエンドAPI 21ファイル（`backend/app/api/`）、設定画面7カード、目標詳細3カテゴリ×タブ、分析3カテゴリ×タブを全スキャン。
- 本書の「①」「②」「③」は依頼内容（1. 記載漏れの追記対象 / 2. 記載の古さ / 3. 文字数削減）に対応する。

## 1. 記載漏れ（①: 既存機能だがヘルプに言及が一切ない）

| # | 機能 | 内容 | 根拠（ファイル:行） |
| --- | --- | --- | --- |
| G1 | 振り返り（テーマ別累積）機能 | ダッシュボードの「今週の振り返り（テーマ別）」ウィジェット、テーマ詳細画面（改名・統合・AI再構築）、ナレッジエクスポートの出力項目「振り返りテーマ」。対象は資格試験・読書のみ（仕事は対象外）。help名前空間に「recap」「統合」「再構築」等の語は0件 | `frontend/src/features/dashboard/RecapThemeSection.tsx`、`frontend/src/pages/RecapThemeDetailPage.tsx`、`backend/app/api/recap.py:37-79`、`backend/app/services/export_service.py`（`ExportSelection.recap_themes`）、`ja.json:884`（`recapThemes`ラベル） |
| G2 | 仕事目標のチームメンバー管理・AI評価レポート | 案件情報タブ内のメンバー登録・編集・無効化・削除（`WorkMemberList.tsx`）。役割を「評価者」に設定すると出現する「評価レポート」タブ（`WorkEvaluationReportTab.tsx`）。**WORK_TABSは実装上5タブだが、ヘルプは「4タブ」と記載**（評価レポートタブの存在に未言及） | `frontend/src/features/goal/WorkAssignmentTab.tsx:139-142,191`、`frontend/src/pages/GoalDetailPage.tsx:86-112,296-302`、`backend/app/api/work_members.py`、`backend/app/api/closure.py:217-269`、`ja.json:1224`（goals.p6） |
| G3 | システム情報画面 | バージョン・Python/フロント依存ライブラリ一覧・診断ログのエクスポート。設定画面に「システム情報へ」リンクあり | `frontend/src/pages/SystemInfoPage.tsx`、`backend/app/api/system_info.py`、`frontend/src/pages/SettingsPage.tsx:37-38` |
| G4 | プロンプトテンプレートのプレースホルダー一覧が大半未記載 | 設定画面「プロンプトテンプレート」は**15用途**を編集できるが、ヘルプの `promptVariables` セクションは **4用途**（日次報告フィードバック・週次要約・今日の一言・総括レポート）のみ変数一覧を掲載。読書/仕事版の日次フィードバック・週次要約（4用途）、仕事の月次/半期総括（2用途）、AI評価レポート、振り返り2用途（RECAP_CLASSIFY/RECAP_THEME_BODY）、ヘルプ質問用（計11用途）のプレースホルダー説明が皆無 | `frontend/src/features/settings/PromptTemplateSection.tsx`、`ja.json:713-728`（`settings.promptTemplate.purpose`15種）、`backend/app/constants/enums.py:87-102`（`AiPurpose`15値）、`ja.json`の`help.sections.promptVariables.purposes`（4キーのみ） |
| G5 | AI接続のアシスタント割当「6つの用途」が実態と不一致 | 実際は**13用途**（`assistant_uid_*`）。読書/仕事の日次フィードバック・週次要約（6項目）、仕事の月次/半期総括・評価レポート、ヘルプ質問用アシスタントがヘルプ本文に未言及 | `frontend/src/features/settings/assistantFields.ts:12-62`、`ja.json:1265`（aiConnection.p3「6つの用途」） |
| G6 | 資格試験テンプレート選択（ウィザードStep1） | `GET /exam-templates` で取得するプリセットから選ぶ画面。バンドル同梱JSONが実体で、ユーザーが追加・編集できる画面は存在しない旨も未記載 | `backend/app/api/exam_templates.py`、`frontend/src/features/goal/examWizard/Step1SelectTemplate.tsx` |
| G7 | 日次報告画面の「仕事」区分 | `DailyReportPage.tsx` はEXAM/READINGに加え、仕事目標向けセクション（`actions.work`）と `WorkMemberSection`（メンバー一覧表示）を持つが、ヘルプの `dailyReport` セクションは資格試験・読書のみ説明し仕事への言及がない | `frontend/src/pages/DailyReportPage.tsx:135-144` |
| G8 | 学習環境設定の「祝日を予備日として扱う」 | `resources` セクションは「曜日ごとの既定（計画日／予備日）」のみ記載。祝日の扱い（チェックボックス）への言及なし | `frontend/src/features/resource/DayTypeDefaultsCard.tsx:65-72` |
| G9 | プロンプト縮退セクションの項目不足 | 実装は3項目（入力上限文字数・週次要約注入週数・**観点提案を促す確定済み記録数の閾値**）。ヘルプは前2項目のみ記載 | `frontend/src/features/settings/PromptDegradationSection.tsx:64-72` |
| G10 | 表示セクションの項目不足 | 実装は5項目（言語・テーマ・既定粒度・**アクセントカラー・フォントサイズ**）。ヘルプは前3項目のみ記載 | `frontend/src/features/settings/DisplaySection.tsx` |

### 参考: ヘルプ不要と判断できるもの（確認済み・対応不要）
- `client_logs.py`（フロント例外の内部ログ記録）、`errors.py`（例外ハンドラ定義のみ）は利用者向け機能ではなく、ヘルプへの追記対象外。
- `POST /calendar/holidays/import` はフロントエンドから呼び出すUIが存在しない（API単体のみ、`frontend/src/types/api.d.ts`に型定義があるのみで呼び出しコードなし）。UIがない機能のため、ヘルプ記載対象外と判断する。

## 2. 記載の古さ（②: 現在の仕様と異なる・誤りを含む）

| # | 項目 | 現行ヘルプの記載 | 実態 | 根拠 |
| --- | --- | --- | --- | --- |
| S1 | `intro`セクションの基本フロー | 「①目標一覧で**試験目標**を作成する…⑥受験結果を登録し…ナレッジエクスポートを出力する」という6ステップが、資格試験の流れのみを説明しており、読書・仕事という2カテゴリの存在に一言も触れていない | 読書は「読了にする」、仕事は「完了にする」で終了し、仕事は完了時にナレッジエクスポート画面へ遷移しない（対象外） | `ja.json`の`help.sections.intro.p2` vs `goals.p5/p6`、`GoalDetailPage.tsx:138-143`（`category !== 'WORK'`のみエクスポートへ遷移） |
| S2 | `goals`セクションの「ウェルカム画面の再表示リンク」の所在 | 「初回起動時や使い方を忘れたときは、**このページ**の案内リンクからウェルカム画面を再表示できます」と、目標一覧（goalsセクション）内に記載 | 実際のリンクは**ヘルプ画面**（`HelpPage.tsx:47-48`）にあり、目標一覧画面（`GoalsListPage.tsx`）には存在しない | `frontend/src/pages/HelpPage.tsx:47-48` vs `frontend/src/pages/GoalsListPage.tsx`（該当リンクなし） |
| S3 | `goals`セクションの資格試験タブの並び順 | 「『負荷プロファイル』…『リソース配分』」の順で記載 | 実装のタブ順は「リソース配分→負荷プロファイル」 | `GoalDetailPage.tsx`の`EXAM_TABS`（33-59行） |
| S4 | `examAndExport`セクションの出力項目リスト | 「目標概要・教材構成・学習量サマリ・実績推移・品質指標推移・リプラン履歴・週次要約・日記本文・AI対話履歴・受験結果・総括レポート」の11項目 | 実装の`ExportSelection`は12項目（上記11項目＋「**振り返りテーマ**」）。G1と同一原因 | `backend/app/services/export_service.py`の`ExportSelection`（12フィールド）、`ja.json:884` |

## 3. 文字数削減の余地（③: 要点のみ記載への圧縮、検出のみ・設計は次セッション）

- `settingsOther` は1セクションに画面上7カード分（AI接続を除く閾値／プロンプト縮退／表示／ログ／プロンプトテンプレート）を集約しており、画面の実構成単位とセクション粒度がズレている。ヘルプAIアシスタントが出典検証する単位（セクションID）が粗く、誤答や過剰な本文送信につながりうる。
- `promptVariables` は変数名の羅列が長く（現状4用途×各5〜10行）、G4の11用途を素直に追記すると3倍以上に膨張する。羅列型ではなく「用途名＋代表変数のみ」等への圧縮方針を次セッションで検討する必要がある。
- `aiConnection`／`goals`／`analytics` の各セクションは「○○タブです」の列挙が多く、個々のタブの表示条件（例: 評価レポートタブの表示条件）は画面のツールチップ文言（`ja.json:248`）に既に書かれている。ヘルプ本文に重複して書かないよう、出典行の付け方（タブ名の列挙のみに留める等）を次セッションで方針化する。

## 4. 次セッションへの引き継ぎ事項

- 本書の「1. 記載漏れ」10件・「2. 記載の古さ」4件・「3. 文字数削減」3観点が、次回の実装（ヘルプ本文改訂）のインプットである。
- 改訂は `frontend/src/locales/ja.json` の `help` 名前空間を編集し、`backend/scripts/export_help_content.py` で `backend/app/content/help_content.json` を再生成する（`test_help_content.py`のドリフト検出で確認）。
- 改訂後は `backend/tests/fixtures/help_assistant/` のテストセット（範囲内・範囲外・境界・インジェクション）の追加・見直しも必要（G1〜G10の新規追記分について範囲内の質問例を増やす）。
- 文字数削減（③）は、セクション分割・粒度の見直しを伴うため、`help_assistant_service.py` の「全文送信／セクション選択」ロジックへの影響も確認すること。
