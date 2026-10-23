# 開発Todo：目標相談チャット（S10、読書・仕事への展開／質問例ボタン／相談履歴の保存）

本書はS09（`docs/開発Todo_目標相談チャット_v1.0.md`、完了・mainマージ済み）を引き継ぐ改訂版である。S09と同じ改修シリーズとして扱い、実装フェーズ分割計画書への新規Phase追加は行わない（S09のU18を継承）。v1.0は完了記録として残し、本書(v1.1)を以後の正（Single Source of Truth）とする。

対象：目標相談チャットを資格目標（EXAM）専用から読書（READING）・仕事（WORK）へ展開し、質問例ボタン・相談履歴の永続化を追加する。

## 0. 決定事項

| # | 決定 | 値 | 根拠 |
| --- | --- | --- | --- |
| V1 | 対象カテゴリ | EXAM・READING・WORKの全3種別。資格限定ガード（`_require_exam_goal`）は撤廃し、`GoalDetailPage.tsx`の`READING_TABS`・`WORK_TABS`にも`goalConsultation`タブを追加する | 要件1 |
| V2 | AiPurpose／ConversationScope | 既存`GOAL_CONSULTATION`（EXAM専用のまま、名称変更しない）はそのまま使い、`GOAL_CONSULTATION_READING`・`GOAL_CONSULTATION_WORK`を新設する。`DAILY_FEEDBACK`→`DAILY_FEEDBACK_READING`/`_WORK`、`GOAL_RETROSPECTIVE`→`_READING`/`_WORK_MONTHLY`/`_SEMIANNUAL`と同じ命名・分岐の前例に合わせる（既存`GOAL_CONSULTATION`の名称変更は不要な破壊的変更になるため避ける） | CODING_RULES.md①DRY（既存命名規則の再利用） |
| V3 | プロンプトテンプレート | `prompt_texts_common.py`に`GOAL_CONSULTATION_READING`・`GOAL_CONSULTATION_WORK`を新設（既存`GOAL_CONSULTATION`は無変更）。読書は「# 本の情報」`{{book_summary}}`・「# 読書の指標」`{{reading_metrics}}`、仕事は「# 案件の概要」`{{work_summary}}`・「# 進み具合」`{{work_progress}}`を持つ。品質指標の推移・リプラン履歴（`{{quality_trend}}`/`{{replan_history}}`）はEXAM専用の概念（教材の`PlanBaseline`前提）のため読書・仕事には設けない | §1.1フルスキャン（ai_context_reading.py／ai_context_work.pyにはbaseline/品質指標の概念が無い） |
| V4 | 使用アシスタント・設定キー | S09の4設定キー（`ai.assistant_uid.goal_consultation`等）をそのまま3カテゴリ共通で使う。カテゴリ別の新規設定キーは追加しない（アシスタント自体はナレッジを持たず内容に依存しないため） | CODING_RULES.md②ゼロハードコーディング対象外・DRY（設定キーの不要な増殖を避ける） |
| V5 | サービス層の分割 | `goal_consultation_service.py`を`_common.py`（直列化・質問検証・送信・解釈・永続化などカテゴリ非依存の処理）と`_exam.py`／`_reading.py`／`_work.py`（カテゴリ別の変数組み立て・テンプレート選択）に分割する。`ai_context_common/_exam/_reading/_work`・`record_service_*`・`export_service_*`と同じ分割方式 | CODING_RULES.md置き場所ルール（複数カテゴリを1ファイルで扱う場合の分割規則） |
| V6 | 相談履歴の保存先 | 既存`chat_message`は使わず、新規テーブル`goal_consultation_log`を作る（下記「比較」参照） | 要件3 |
| V7 | 相談履歴APIの形 | `GET /goals/{goal_id}/consultation/history`（一覧、全件を`created_at`昇順で返す。件数は実運用上少数のためページングは設けない＝YAGNI）、`DELETE /goals/{goal_id}/consultation/history/{log_id}`（1件削除、確認モーダルを設ける）。一覧が質問・回答本文・根拠・状態を全て含むため、個別取得（詳細）APIは設けない | 要件3 |
| V8 | 相談履歴の保存タイミング | ANSWERED・UNAVAILABLEの両方を保存する（禁止語等で拒否した場合も含む）。既存`ai_log`（用途別、`log.retention_days`で自動削除・goal_id無し）とは別の目的（運用監視 vs 利用者向け恒久履歴）であり重複ではない。保存は`serialize_writes()`で直列化する（既存の「AI通信とトランザクション」方針を継承） | 要件3・CODING_RULES.md「AI通信とトランザクション」 |
| V9 | EXAM専用ガードの撤廃に伴うSTRIDE更新 | S09のElevation of Privilege行（READING/WORK利用者のAPI直叩き拒否）は本改修で前提自体が変わるため撤廃し、§5に差分を記載する | §5 |
| V10 | 版 | `pyproject.toml`は変更しない（S09 U19を継承） | S09 U19 |
| V11 | チームメンバー情報の相談入力への利用（確認事項①、2026-10-22利用者確認） | 含める。`ai_context_work.build_evaluation_member_summary_text`相当の呼び出しで`characteristics`を含めてよい。`consent_confirmed_at`は保存時点検証のため追加の同意チェックは不要（§1.4） | 利用者確認済み |
| V12 | 質問例ボタンの文言（確認事項②、2026-10-22利用者確認） | 依頼文の初期案のまま確定。資格「苦手な分野はどこ？」「このペースで間に合う？」「次に重点を置く分野は？」、読書「前に読んだ本とのつながりは？」「この本で学んだことを3行で」、仕事「今月の成果を上司向けに3行で」「最近の課題の傾向は？」 | 利用者確認済み |
| V13 | 相談履歴のナレッジエクスポート対象化（確認事項③、2026-10-22利用者確認） | 対象にしない。`export_service_exam/_reading/_work.py`への相談履歴抽出は実装しない（バックアップ／全データエクスポート・インポートは新規テーブルでも汎用機構により自動的に対象のまま、本決定の影響を受けない） | 利用者確認済み |
| V14 | recapのテーマ分類を使った関連記録の優先送付（確認事項④、2026-10-22利用者確認） | MVPでは入れない。既存の週次要約→生ログの段階的縮退のみとする。将来必要になれば別件として着手する | 利用者確認済み |

### 比較：相談履歴の保存先（V6の根拠）

| 観点 | `chat_message`を使う場合 | 新規テーブル（`goal_consultation_log`）を作る場合 |
| --- | --- | --- |
| `daily_record_id` | NOT NULLのため、日付を問わないアドホックな1問1答を無理に「今日のdaily_record」へ紐付ける必要がある。目標相談は同日に何度でも送れるため、1日に多数のchat_messageが積み上がり、日次報告対話（`DAILY_FEEDBACK`）と同じ`sequence`空間を共有してしまう | goal_idのみに紐付ければ良く、日付の制約を受けない |
| 根拠（日付・週）の保存 | `content`列（文字列）しか無く、検証済みの構造化データ（`cited_dates`/`cited_weeks`）を別途持てない。再掲時に再度パースし直す必要がある | 専用列として持てる（区切り文字列で十分、JSON列の前例は本アプリに無いため導入しない） |
| 目標削除時の連鎖削除 | `goal_id`に`ondelete="CASCADE"`済みのため追加対応は不要 | 新規に`ondelete="CASCADE"`を設定するだけで同等に対応可能 |
| バックアップ・全データエクスポート/インポート | 既存テーブルのため自動的に対象（`backup_service.py`は`Base.metadata`から動的に全テーブルを扱うため、新規テーブルでも対応不要という点は同条件） | 同上（新規テーブルでも無改修で対象になる） |
| ナレッジエクスポート（匿名化含む） | `export_service_exam._build_ai_dialogue`は`purpose`で厳密に絞り込む設計のため、新用途を含めるかどうかは新規テーブルと同様に明示的な実装判断が必要（確認事項③） | 同上 |
| 既存機能への影響 | `chat_message`は日次報告フィードバック対話・分析タブ「成長記述」等、既存の複数機能が前提にしている構造（1日1レコード・role単位）。目標相談の形（1問1答・構造化根拠）を押し込むと、既存機能側の想定（「日次報告の対話」）との混同・デグレのリスクがある | 既存機能に影響しない |

**結論**：新規テーブル`goal_consultation_log`を採用する（V6）。列は`id`・`goal_id`（FK `goal.id` ON DELETE CASCADE、インデックス）・`question`（Text）・`status`（既存Enum`GoalConsultationAnswerStatus`を再利用、native_enum=False）・`answer_body`（Text、UNAVAILABLE時は空文字）・`cited_dates`（Text、nullable、ISO日付をスペース区切り、空なら根拠なし）・`cited_weeks`（Text、nullable、`start~end`形式をスペース区切り）・`created_at`（`CreatedAtMixin`）。新規`create_table`のみのマイグレーションのため、既存データに対する安全性テスト（CODING_RULES.md）は対象外。

## 1. 影響範囲（フルスキャンの結果）

### 1.1 バックエンド

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| 列挙 | `app/constants/enums.py`：`AiPurpose`・`ConversationScope`に`GOAL_CONSULTATION_READING`・`GOAL_CONSULTATION_WORK`を追加（既存`GOAL_CONSULTATION`は無変更） | 値の追加 |
| モデル | `app/models/`に`GoalConsultationLog`新設（ファイルは`app/models/goal.py`末尾、またはgoal関連の新規`app/models/goal_consultation.py`。既存`daily_message`等の1目標1アクティビティ系モデルの配置に揃える。実装時に既存ファイルの肥大度を見て判断） | 新規テーブル |
| マイグレーション | `backend/alembic/versions/`に`create_table`のみの新規リビジョン追加 | 追加 |
| プロンプト文面 | `app/init/prompt_texts_common.py`：`GOAL_CONSULTATION_READING`・`GOAL_CONSULTATION_WORK`定数を新設（V3） | 追加 |
| 初期データ | `app/init/seed_data.py`の`INITIAL_PROMPT_TEMPLATES`に2用途分追加。既存4設定キーは変更なし（V4） | 追加 |
| サービス | `app/services/goal_consultation_service_common.py`（新設、既存`goal_consultation_service.py`から直列化・検証・送信・解釈・履歴保存を移動）、`_exam.py`／`_reading.py`／`_work.py`（新設、カテゴリ別の変数組み立て・テンプレート選択・purpose選択） | 分割（V5） |
| サービス（履歴） | `app/services/goal_consultation_log_service.py`（新設：一覧取得・削除。`goal_consultation_service_common.py`から呼ばれる保存処理とは責務を分ける） | 追加 |
| API | `app/api/goal_consultation.py`：`_require_exam_goal`相当のガードを撤廃。`GET /goals/{goal_id}/consultation/history`・`DELETE /goals/{goal_id}/consultation/history/{log_id}`を追加 | 変更・追加 |
| スキーマ | `app/schemas/goal_consultation.py`：履歴一覧・削除用のRead/Requestモデル追加 | 追加 |
| 目標削除の連鎖 | `app/services/goal_service.py`の`delete_goal`系：`goal_consultation_log`はDB側`ondelete="CASCADE"`で対応済みのためPython側の明示的削除は不要（`chat_message`と同じ扱い）。ただし削除順序・既存のテスト（`test_goal_service.py`の削除系）に新テーブルの残存チェックを追加する | 確認・テスト追加 |
| データ管理（バックアップ／全データエクスポート・インポート） | `backup_service.py`は無改修で対象に入る（§0比較参照）。`test_backup_service.py`の全データエクスポート/インポートの往復テストに新テーブルが含まれることを確認するテストケースを追加 | 確認・テスト追加 |
| ナレッジエクスポート（匿名化含む） | 対象にしない（V13）。`export_service_exam.py`・`export_service_reading.py`・`export_service_work.py`は無改修 | 対応不要（決定済み） |
| 横展開（既存のEXAM専用実装） | `goal_consultation_service.py`全体（`_require_exam_goal`・EXAM専用の変数組み立て）、API層のドメイン例外、OPERATIONS.mdの「対象は資格目標のみ」記述 | 変更 |
| テスト | `backend/tests/test_goal_consultation_service.py`の分割対応（`_exam`/`_reading`/`_work`/`_common`）、`test_goal_consultation_log_service.py`（新規）、`test_api_goal_consultation.py`（履歴API・3カテゴリ分の質問API）、`test_goal_service.py`（削除連鎖）、`test_backup_service.py`（新テーブルの往復） | 追加・変更 |

### 1.2 フロントエンド

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| 目標詳細画面 | `GoalDetailPage.tsx`：`READING_TABS`・`WORK_TABS`に`goalConsultation`タブを追加。`activeTab === 'goalConsultation'`の描画分岐はカテゴリ非依存のため変更不要だが、タブ追加漏れが起きないことを描画テストで固定する（S09開発Todoに記録された「タブは出るが中身が空白」実例の再発防止パターンを継承） | 変更 |
| 機能 | `features/goalConsultation/GoalConsultationTab.tsx`：質問例ボタン（要件2）、`goal.category`を受け取るprop追加、相談履歴タブ内セクション（一覧・削除ボタン） | 変更 |
| 機能（新規） | `features/goalConsultation/GoalConsultationHistory.tsx`（新設：履歴一覧の描画・削除確認モーダル）、`goalConsultationLogic.ts`に質問例ボタンの文言キー解決・削除確認の純粋関数を追加 | 追加・変更 |
| API層 | `api/goalConsultation.ts`：履歴一覧・削除の関数追加。`types/api.d.ts`は`npm run generate:api-types`で再生成（手書きしない） | 変更 |
| フック | `useGoalConsultation.ts`：`useGoalConsultationHistory`・`useDeleteGoalConsultationLog`を追加 | 追加 |
| 文言 | `ja.json`／`en.json`：質問例ボタンの文言（カテゴリ別）、`goals.detail.tabTooltips.goalConsultationReading`／`goalConsultationWork`（既存`basicInfoReading`/`basicInfoWork`と同じ命名パターン）、履歴セクションの文言（一覧見出し・削除確認・空状態） | 追加 |
| 定数 | `constants/queryKeys.ts`：履歴一覧のキャッシュキー追加の要否を実装時に判断 | 要否判断 |

### 1.3 ドキュメント

| 文書 | 変更 |
| --- | --- |
| `docs/要件定義書_ミチナリ_v1.1.md` | 6.14の対象カテゴリ拡大・R-111〜（質問例・履歴）、改訂履歴 |
| `docs/仕様書_ミチナリ_v1.1.md` | 目標詳細画面（READING/WORKタブ追加）、8.1 AI-15の対象拡大、履歴のCRUD仕様、改訂履歴 |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1.md` | 24章（目標相談）の対象拡大・プロンプト2件追加・サービス分割構成、脅威モデル差分、改訂履歴 |
| `docs/設計書_データ構造編_ミチナリ_v1.1.md` | `goal_consultation_log`テーブル定義、改訂履歴 |
| `docs/OPERATIONS/目標相談チャットの運用.md` | 「対象は資格目標のみ」の記述を削除、履歴の永続化・削除手順を追記 |
| `docs/実装フェーズ分割計画書_ミチナリ_v1.1.md` | 変更なし（S09 U18を継承） |

### 1.4 既存機能への横展開（同じ問題の有無を確認）

| 項目 | 状況 | 対応 |
| --- | --- | --- |
| EXAM専用ガードの撤廃漏れ | `_require_exam_goal`相当のチェックをサービス層・画面タブ出し分けの両方から除去する必要がある（S09で「タブ非表示＋サービス層拒否」の二重防御として実装されたため、撤廃も両方で行う） | B-xxで両方を確認するテストを追加（READING/WORKでタブが出ること・APIが受理すること） |
| `build_with_degradable_entries`の戻り値拡張（S09 U20） | 読書・仕事向けの新しい呼び出しが6箇所目として追加されるが、拡張自体はS09で完了済みのため影響なし | 既存の回帰テストにreading/work向け呼び出しを追加する形で網羅 |
| 禁止語テーブルの共有 | 変更なし（カテゴリ区別なしの既存仕様を継続） | 対応不要 |
| `question_safety`／`discard_conversation`の共通化（S09で抽出済み） | 読書・仕事でも同じ関数を呼ぶだけで済む | 対応不要（再利用のみ） |
| 仕事目標のチームメンバー情報（`characteristics`）をAI入力に使う既存前例 | `ai_context_work.build_evaluation_member_summary_text`（評価レポート）が既に同じ情報をAIへ送信している。`consent_confirmed_at`は保存時点でのみ検証され（`work_member_service._apply_characteristics`）、以後`characteristics`が非NULLであることが同意済みの不変条件となっているため、目標相談で読み取る場合も追加の同意チェックは不要 | 確認事項①の判断材料として記載 |

## 2. 現状のベースライン（開発前、2026-10-22）

- バックエンド：`ruff check .` 合格。`pytest --cov`　1,937件合格、2 warnings（248.82秒）、カバレッジ総計98%（既存の無関係なギャップのみ、S09完了時と同水準）。
- フロントエンド：`npm run lint`（oxlint）0件、`npx tsc -b`0件、`npm run test`（vitest）1,338件合格、カバレッジ100%（文・分岐・関数・行）。
- 既存の失敗：なし。S09完了時の記録（v1.0 §2・V-01）と一致しており、本書着手時点でのドリフトは無い。

## 3. 作業Todo

凡例：`[ ]` 未着手、`[x]` 完了。各項目の完了条件は「テストが通ること」と「カバレッジ100%（例外処理を除く）」。確認事項①〜④はT-01で解消済み（§0 V11〜V14）。

### 3.1 事前確認

- [x] T-01 確認事項①〜④（§6）をAskUserQuestionで確認する（2026-10-22、全項目利用者確認済み。結果はV11〜V14）
- [x] T-02 `GoalConsultationLog`モデルの配置ファイルを確定する（既存`models/goal.py`に追記。`GoalStatusHistory`と同じ単純なログ型テーブルの前例に合わせた）

### 3.2 文書改訂

- [x] D-01 要件定義書：6.14の対象拡大（R-104改訂）・R-111・R-112を新設、改訂履歴（1.1改46）
- [x] D-02 仕様書：6.2（SC-03、目標相談タブをEXAM限定から全種別へ、質問例ボタン・相談履歴セクション）、8.1（AI-16・AI-17新設）・8.5、改訂履歴（1.1改58）
- [x] D-03 設計書（ロジック・プロンプト編）：24章を全面改訂（サービス分割構成・カテゴリ別プロンプト・24.6相談履歴の保存・24.7脅威モデル差分）、25章にL-18を新設、改訂履歴（1.1改53）
- [x] D-04 設計書（データ構造編）：5.3に`goal_consultation_log`を新設、改訂履歴（1.1改50）
- [x] D-05 OPERATIONS.md：「目標相談チャットの運用」更新（対象拡大・質問例ボタン・相談履歴の運用）

### 3.3 バックエンド実装

- [x] B-01 列挙：`AiPurpose`・`ConversationScope`に`GOAL_CONSULTATION_READING`・`GOAL_CONSULTATION_WORK`を追加
- [x] B-02 モデル・マイグレーション：`GoalConsultationLog`新設（`models/goal.py`）、Alembicリビジョン`0f15de420a01`追加
- [x] B-03 プロンプト・シード：`prompt_texts_reading.GOAL_CONSULTATION_READING`・`prompt_texts_work.GOAL_CONSULTATION_WORK`を新設（既存`GOAL_CONSULTATION`は`prompt_texts_common.py`→`prompt_texts_exam.py`へ移動、配置ルール統一）、シード投入
- [x] B-04 サービス分割：`goal_consultation_service_common.py`／`_exam.py`／`_reading.py`／`_work.py`へ分割完了。既存21件のテストはカテゴリ分岐を外した以外無改修で通過を確認
- [x] B-05 履歴サービス：`goal_consultation_log_service.py`（保存・一覧・削除）、`goal_consultation_service_common.py`から`_save_log`経由で接続
- [x] B-06 API：EXAM専用ガード撤廃、`GET`/`DELETE` `/goals/{goal_id}/consultation/history` を追加
- [x] B-07 目標削除の連鎖：`test_goal_service.py::test_delete_goal_cascades_removes_goal_consultation_log`を追加
- [x] B-08 データ管理：`test_backup_service.py`に新テーブルを含む往復確認（空テーブル・行の往復・1.1/1.2互換インポート）を追加、`DATA_SCHEMA_VERSION`を1.2→1.3へ更新
- [x] B-09 セキュリティテスト：読書・仕事それぞれの区切り偽装・禁止語・フォールバック文言、他目標の履歴へのアクセス不可（`goal_id`絞り込み、404）、削除APIの認可境界を追加

### 3.4 フロントエンド実装

- [x] F-01 型の再生成（`.venv/Scripts/python.exe scripts/export_openapi.py` → `npx openapi-typescript`）
- [x] F-02 `GoalDetailPage.tsx`：READING_TABS・WORK_TABSへタブ追加。描画分岐がEXAM専用ブロック内に残っていた実装漏れを修正し、カテゴリ非依存の位置へ移動。3カテゴリとも中身が空白にならないことを描画テストで固定
- [x] F-03 質問例ボタン：確認事項②の確定文言で実装（`questionExampleKeys`、カテゴリ別の表示切り替え）
- [x] F-04 相談履歴：`GoalConsultationHistory.tsx`（一覧・削除UI、`window.confirm`による確認、空状態・読み込み中の表示）
- [x] F-05 文言：`ja.json`/`en.json`に質問例・履歴セクション・カテゴリ別タブツールチップを追加
- [x] F-06 `npm run lint`・`tsc -b`・`npm run test` 全て合格

### 3.5 検証

- [x] V-01 ruff・pytest・vitest（ベースライン比較、2026-10-23実施）。バックエンド：ruff合格、pytest 1,962件合格（ベースライン1,937件から+25件）、カバレッジ100%（ベースライン98%から向上）。フロントエンド：lint 0件、tsc 0件、vitest 1,348件合格（ベースライン1,338件から+10件）、カバレッジ100%
- [ ] V-02 実機テスト（一時DB、実NewtonX）：読書・仕事それぞれでT1〜T4相当（S09 V-02参照）、履歴の保存・一覧・削除、目標削除時の連鎖削除。2026-10-23、別セッションが同じブランチで並行作業中（`exam_results`関連の未コミット変更）であることが判明し、利用者の判断で一旦保留（§7別件参照）
- [x] V-03 フルスキャンの再確認（§1.4の横展開項目）：EXAM専用ガードの撤廃漏れ（サービス層・画面タブ出し分けの両方で確認済み、F-02のテストで固定）、`build_with_degradable_entries`の戻り値拡張（S09で完了済み、影響なし）、禁止語テーブルの共有（意図した挙動のまま）、`question_safety`/`discard_conversation`の共通化（そのまま再利用）、仕事目標のチームメンバー情報利用の前例（確認済み、V11根拠）
- [x] V-04 `create_table`のみのマイグレーション（既存データへの影響なし、CODING_RULES.mdの除外対象）。`test_migration_schema.py::test_upgrade_head_creates_all_tables`が新テーブルを含めて合格することを確認済み（V-01のpytest全体に含まれる）

## 4. テスト計画

- 3カテゴリ（EXAM/READING/WORK）それぞれで質問→回答の往復、根拠検証（実在・偽の出典・根拠なし）
- READING/WORKでの質問例ボタンの表示文言・クリック時の入力欄への反映
- 相談履歴：保存（ANSWERED/UNAVAILABLE両方）→一覧取得→削除→削除確認、他goal_idの履歴が混入しないこと
- 目標削除時に`goal_consultation_log`が連鎖削除されること（カテゴリ3種とも）
- バックアップ・全データエクスポート/インポートの往復に新テーブルが含まれること
- サービス分割（B-04）前後で既存テストの結果が変わらないこと（回帰）

## 5. 脅威モデル（STRIDE）の差分

| 観点 | S09時点 | 本改修での変更 |
| --- | --- | --- |
| Elevation of Privilege | 「READING/WORK目標の利用者がAPIを直接叩いて目標相談機能を使う」を脅威として掲げ、サービス層で`ValidationError`拒否 | 前提が変わり3カテゴリとも正規に利用可能になるため本項は撤廃。代わりに「他目標（他goal_id）の相談履歴への不正アクセス」を追加し、`goal_id`絞り込み＋削除APIの認可境界テスト（B-10）で対策する |
| Information Disclosure | 他目標の記録混入・出典捏造 | 変更なし。追加で「相談履歴一覧に他目標の履歴が混入する」を明記し、`goal_consultation_log.goal_id`絞り込みで対策（既存のbuild_*関数のgoal_id絞り込みと同じ考え方） |
| Repudiation | `ai_log`のみで記録、retentionで消える | `goal_consultation_log`による恒久的な記録に強化（V8）。ただし利用者自身が削除可能（要件3）なため、削除は「見返さなくなった履歴を消す」利用者機能であり、不正な証拠隠滅の脅威ではない（単一利用者アプリ、要件定義書前提） |
| Tampering／Spoofing | nonce・全角化等 | 変更なし（カテゴリに依存しない既存対策を継続） |
| Denial of Service | 質問上限・直列化 | 変更なし |

## 6. 未決事項

確認事項①〜④（2026-10-22、AskUserQuestionで全項目利用者確認済み）は解消済み。結果は§0 V11〜V14に記録。本書着手時点で他の未決事項は無い。

## 7. 別件

- 禁止語の管理画面（S09から継続、未着手）
- 相談履歴の検索・絞り込み（件数が増えた場合の将来課題。MVPはページング無しの全件表示）
- V-02（実機検証）：2026-10-23、同じ`dev/2026-10-22`ブランチで別セッションが並行作業中（`exam_results`を日次報告フィードバックへ追加する未コミット変更。本改修とは無関係）であることが判明し、利用者の判断で実施を一旦保留した。コードの実装・テスト（V-01でモック通信により確認済み）は完了しており、残るのは実のNewtonXへの通信確認のみ

---

**実装完了（2026-10-23）**：§3の全項目が`[x]`（V-02を除く）。バックエンド・フロントエンドともテスト合格・カバレッジ100%（V-01参照）。ドキュメント（要件定義書・仕様書・設計書2冊・OPERATIONS.md）は本Todoの内容と一致。V-02（実NewtonXでの実機検証）のみ、別セッションの並行作業を踏まえて利用者の判断で保留中。
