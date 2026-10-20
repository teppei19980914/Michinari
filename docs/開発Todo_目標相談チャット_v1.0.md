#  開発Todo：目標相談チャット（S09、資格目標・1問1答・根拠つき）

本書は、資格目標の詳細画面から利用者が自由に質問し、蓄積した記録を根拠にAIが答える「目標相談チャット」の開発作業の正（Single Source of Truth）である。S04〜S08と同じ改修シリーズとして扱い、実装フェーズ分割計画書への新規Phase追加は行わない（U18）。対象は資格目標（`GoalCategory.EXAM`）のみ。読書・仕事は S10 で扱う。

既存の「ヘルプAIアシスタント」（`docs/開発Todo_ヘルプAIアシスタント_v1.0.md`、以下「ヘルプ」）と同じ仕組み（質問ごとの使い捨てチャット、禁止語、nonce、山括弧全角化、出典検証、`MarkdownText`表示）を最大限流用し、開発コストを下げる。ただし流用元はヘルプ専用の設定・プロンプトであり、デグレ・横展開漏れが起きやすい箇所（共通エンジンの戻り値拡張、EXAM専用ガード）には特に注意する。

## 0. 決定事項（2026-10-20 時点で確定）

| # | 決定 | 値 |
| --- | --- | --- |
| U1 | 使用アシスタント | ヘルプと同じ（GPT-5 mini（高速）`c9e542e1-a324-46d5-a02e-fe6bfaebf85a`、ナレッジなし）を流用。設定キーは新設 `ai.assistant_uid.goal_consultation` |
| U2 | 画面入口 | 目標詳細画面（`GoalDetailPage.tsx`）のEXAM専用タブ「目標相談」を常設（ヘルプの全画面浮動ボタンとは別系統、視覚的な混同を避ける） |
| U3 | 質問上限 | 300字（ヘルプと同じ）。設定キー `ai.goal_consultation_question_max_chars` |
| U4 | 回答上限 | 新設定キー `ai.goal_consultation_answer_max_chars`（既定値はヘルプの`ai.help_answer_max_chars`=2000字と同水準。具体的な初期値は§6で確定） |
| U5 | 固定文言 | 目標相談向けに言い換えた新規文言。根拠なし：「記録からはまだ判断できません。日々の記録を増やすと、より具体的な回答ができる可能性があります。」／回答不可：「この質問には回答できません。別の聞き方でお試しください。」（最終文言は§6で確定） |
| U6 | 命名案 | `ai.assistant_uid.goal_consultation`／`ai.goal_consultation_folder_name`（既定値「ミチナリ_目標相談」）／`ai.goal_consultation_question_max_chars`／`ai.goal_consultation_answer_max_chars`／`AiPurpose.GOAL_CONSULTATION`／`ConversationScope.GOAL_CONSULTATION` |
| U7 | 対象の限定 | 資格目標（`GoalCategory.EXAM`）のみ。API層・画面層の両方でガードする（タブを出さない＋APIはドメイン例外→HTTPエラー） |
| U8 | 1問1答方式 | ヘルプと同じ使い捨てチャット（作成→送信→削除→一覧で削除確認）。`scope_key`は`uuid4().hex`で毎回新規 |
| U9 | 禁止語 | 既存の`ai_forbidden_term`をそのまま共有（カテゴリ区別なし、CODING_RULES.md DRYの原則） |
| U10 | 根拠検証 | 回答末尾に`[記録: YYYY-MM-DD]`または`[要約: YYYY-MM-DD〜YYYY-MM-DD]`を書かせ、プロンプトに実際に含めた日付・週のみ実在として採用する |
| U11 | 根拠からの遷移 | 日付根拠（`[記録: ...]`）は`ROUTES.dailyReportView(date)`（`/records/:date/view`）へのリンクを付ける。週次要約根拠（`[要約: ...]`）は週単位の閲覧画面が無いためリンクなし（出典表記のみ） |
| U12 | 回答の構成 | プロンプトの指示文で「記録から言えること」と「一般的な助言（記録の外の知識）」を分けて書かせる |
| U13 | ナレッジ未使用 | type:systemでナレッジを持たないアシスタントを使う（U1と同じ結論。NewtonX利用ナレッジ3.3） |
| U14 | AI未接続時 | 既存の`AiUnconfiguredNotice`導線をそのまま使う |
| U15 | 直列化 | 質疑応答全体を専用`_REQUEST_LOCK`（`threading.Lock`）で直列化（ヘルプと同じ方式）。AI送信区間自体は既存の`serialize_writes()`／`send_and_log`をそのまま使う |
| U16 | 相談履歴の保存 | MVPでは保存しない。画面はコンポーネントstateのみ（1問1答）、`ai_log`（`AiPurpose.GOAL_CONSULTATION`）にのみ記録。永続化はS10 |
| U17 | 回答状態の表現 | `GoalConsultationAnswerStatus`（`ANSWERED`/`NOT_FOUND`/`UNAVAILABLE`）を`HelpAnswerStatus`と同形で新設する。ドメインが異なる値を共用すると、将来一方だけ値を増やす際に無関係な用途まで分岐が増える（既存のAiPurpose/ConversationScopeも用途ごとに値を分けている既存パターンを踏襲） |
| U18 | フェーズ番号 | 付与しない。S06「修正時の要約再生成」・S07「長期レポート」・S08「要約原則の範囲」と同じく、実装フェーズ分割計画書（`02_フェーズ一覧.md`）への新規Phase追記は行わず、本Todoを正とする |
| U19 | 版 | `pyproject.toml`は変更しない（リリース手順で入力） |
| U20 | 共通エンジンの拡張方針 | `app/ai/prompt_builder.py`の`build_with_degradable_entries`は、各段階（`DegradableEntryStage`）で最終的に生き残った`DatedLogEntry`一覧を返さない（戻り値`BuildResult`には無い）。出典検証には「プロンプトに実際に含めた日付・週」の集合が必要なため、`BuildResult`（frozen dataclass、57〜60行目）へ既定値`None`の追加フィールド`included_entries: dict[str, list[DatedLogEntry]] | None = None`を末尾に加えて`build_with_degradable_entries`から返すよう拡張する。全`BuildResult(...)`の構築はキーワード引数のみ（T-01で確認済み）のため既存呼び出し元は無改修で影響を受けない。全呼び出し元の既存テストが変更前と同じ結果になることを回帰テストで保証する |

## 1. 影響範囲（フルスキャンの結果）

### 1.1 バックエンド

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| 列挙 | `app/constants/enums.py`：`AiPurpose`・`ConversationScope`（各+1値）、新規`GoalConsultationAnswerStatus` | 値の追加（非ネイティブ列挙のためDB変更不要） |
| 設定キー | `app/constants/app_setting_keys.py` | 4キー追加（`AI_ASSISTANT_UID_GOAL_CONSULTATION`・`AI_GOAL_CONSULTATION_FOLDER_NAME`・`AI_GOAL_CONSULTATION_QUESTION_MAX_CHARS`・`AI_GOAL_CONSULTATION_ANSWER_MAX_CHARS`。`AI_ASSISTANT_UID_HELP`等（51〜54行目）の直後に追加） |
| 初期データ | `app/init/seed_data.py`（`INITIAL_APP_SETTINGS`・`INITIAL_PROMPT_TEMPLATES`） | 4設定値・プロンプト本文1件の追加。既存DBにも不足分のみ投入される |
| プロンプト文面 | `app/init/prompt_texts_common.py` | `GOAL_CONSULTATION`定数を新設（`HELP_ASSISTANT`定数93〜123行と同じ区切り・nonce・山括弧全角化の書式。「記録から言えること」と「一般的な助言」を分ける指示、出典形式`[記録: ...]`/`[要約: ...]`を追加） |
| AI基盤（共通エンジン拡張） | `app/ai/prompt_builder.py`の`BuildResult`・`build_with_degradable_entries`（251〜296行） | U20のとおり、生き残ったエントリ一覧を返す拡張。既存5箇所の呼び出し元（§1.4）への回帰テストを追加 |
| AI基盤（変更なし・再利用） | `app/ai/client.py`（`delete_chat`・`chat_listed_in_folder`等）、`app/ai/conversation.py`（`ensure_conversation`）、`app/ai/orchestration.py`（`send_and_log`・`load_template_body`・`get_max_prompt_chars`） | 変更なし。ヘルプと同じ呼び方で再利用する |
| 過去記録の組み立て（再利用、再実装しない） | `app/services/ai_context_common.py`の`build_past_record_entries`・`resolve_weekly_compressed_period`・`build_weekly_compressed_stages`、`app/services/ai_context_exam.py`の`build_recent_study_entries` | 変更なし。資格試験の日次報告フィードバックと同じ呼び方（`daily_feedback_service.py:127-135`参照）で、`goal.start_date`〜「今日」までの全期間を渡す |
| 目標概要等の組み立て（再利用、再実装しない） | `app/services/ai_context_exam.py`の`build_goal_summary`・`build_material_summary_text`・`build_quality_trend_text`・`build_replan_history_text` | 変更なし。`retrospective_service._build_exam_context`（90〜124行）と同じ呼び方を転用 |
| 新規サービス | `app/services/goal_consultation_service.py` | 追加（`help_assistant_service.py`と同型：入力検証・禁止語・本文組み立て・送信・出典検証・後始末・直列化。対象カテゴリ(EXAM)ガードを追加） |
| 新規API | `app/api/goal_consultation.py`、`app/schemas/goal_consultation.py`、`app/main.py`（登録） | 追加（`POST /goals/{goal_id}/consultation/questions`、`GET /goals/{goal_id}/consultation/limits`。ドメイン例外→既存のエラー変換） |
| サービス | `app/services/settings_service.py`（`AiConnectionSettings`・`_update_ai_connection`・組み立て関数、3か所）、`app/schemas/setting.py`（2クラス） | 新設定の配線（ヘルプの`assistant_uid_help`と同数の変更点） |
| マイグレーション | なし | 新規テーブル無し、enumはStrEnum（非ネイティブ）のためDBスキーマ変更不要 |
| テスト | `backend/tests/test_goal_consultation_service.py`、`test_api_goal_consultation.py`、既存の`test_prompt_builder.py`（`build_with_degradable_entries`回帰）、既存のシード・設定・プロンプト件数テスト | 追加・既存テストの影響確認 |

### 1.2 フロントエンド

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| 目標詳細画面 | `src/pages/GoalDetailPage.tsx`：`EXAM_TABS`配列（33行目付近）へ`goalConsultation`タブ追加、`TabKey`型union拡張、EXAM専用レンダー分岐（363行目付近の`goal.category === 'WORK'`ブロックと対になる`'EXAM'`ブロック）に追加 | 変更 |
| 機能 | `src/features/goalConsultation/`（新規：`GoalConsultationTab.tsx`、`GoalConsultationAnswer.tsx`、`goalConsultationLogic.ts`、`useGoalConsultation.ts`） | 追加（ヘルプの`features/helpAssistant/`と同じ役割分担） |
| API層 | `src/api/goalConsultation.ts`（新規）、`src/types/api.d.ts`（`npm run generate:api-types`で再生成、手書きしない） | 追加 |
| 設定画面 | `src/features/settings/assistantFields.ts`の`ASSISTANT_FIELDS`（12〜62行）へ`assistant_uid_goal_consultation`を追加（型の網羅性チェック69〜75行がコンパイルエラーで漏れを検出する） | 追加 |
| 文言 | `src/locales/ja.json`／`en.json`：`goalConsultation.*`（タブ内文言・固定文言）、`goals.detail.tabs.goalConsultation`・`tabTooltips.goalConsultation`、`settings.aiConnection.assistant.goalConsultation` | 追加（両言語同時、`localeKeyUsage.test.ts`が片方欠落を検出する） |
| 定数 | `src/constants/queryKeys.ts` | 追加の要否は実装時に判断 |

### 1.3 ドキュメント

| 文書 | 変更 |
| --- | --- |
| `docs/要件定義書_ミチナリ_v1.1.md` | 新節（6.13ヘルプの次、6.14想定）R-104〜、改訂履歴 |
| `docs/仕様書_ミチナリ_v1.1.md` | 機能一覧表、目標詳細画面の仕様（タブ追加）、8.1のAI-15、設定項目、改訂履歴 |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1.md` | 処理フロー、`GOAL_CONSULTATION`プロンプト、入力・出力検証、`build_with_degradable_entries`拡張の記述更新、脅威モデル（STRIDE）、改訂履歴 |
| `docs/設計書_データ構造編_ミチナリ_v1.1.md` | 設定キー4件の追加、改訂履歴（新テーブルなし） |
| `docs/実装フェーズ分割計画書_ミチナリ_v1.1.md` | 変更なし（U18）。本Todoが正である旨のみ、該当するなら「追加スコープ」節に一言リンクを追記するかは実装時判断 |
| `docs/OPERATIONS.md`（`OPERATIONS/`配下） | 「目標相談チャットの運用」セクション新設（`ヘルプAIアシスタントの運用.md`と同型。禁止語がヘルプと共有であることを明記、フォルダの手動削除） |

### 1.4 既存機能への横展開（同じ問題の有無を確認）

| 項目 | 状況 | 対応 |
| --- | --- | --- |
| `build_with_degradable_entries`の戻り値拡張（U20） | T-01で確定：5ファイル・6箇所（`reading_feedback_service.py:164`、`retrospective_service.py:203`、`work_feedback_service.py:167`、`work_evaluation_service.py:91`、`work_report_service.py:307,428`）。全て`BuildResult(...)`をキーワード引数で構築しており位置引数依存は無い | 戻り値は追加フィールド（既定`None`）のみで既存の`text`/`prompt_chars`/`was_truncated`/`exhausted`は変更しない。6箇所全ての既存テストが無変更で通ることを確認する |
| EXAM専用ガードの実装漏れ | `GoalDetailPage.tsx`のコメント（354行目付近）に「タブ構成には追加したのに描画側へ反映し忘れ、読書目標でタブは出るが中身が空白になった」実例が記録されている | 同じ事故を起こさないよう、タブ追加とレンダー分岐追加を同一コミット内で行い、READING/WORK目標では「目標相談」タブ自体を出さないことを描画テストで固定する |
| 禁止語テーブルの共有 | ヘルプ用に投入した禁止語がそのまま目標相談にも適用される（カテゴリ区別なし） | 意図した挙動（U9）。目標相談特有の禁止語が必要になった場合は別件として扱う（§7） |
| テンプレート注入対策（`_substitute`の1回パス処理） | ヘルプ導入時（Phase43 B-02）に既に全用途向けへ修正済み | 変更不要。新規`GOAL_CONSULTATION`テンプレートもこの既存の安全な実装を使う |
| 応答の表示（生HTML未解釈） | `MarkdownText`は既存のまま | 変更なし。回帰テストで担保 |

## 2. 現状のベースライン（開発前、2026-10-20）

- バックエンド：`ruff check .` 合格。`pytest`（カバレッジ計測つき）1,886件合格、1 warning（320.77秒）。カバレッジ総計99%（`weekly_summary_service.py`68%・`ai_context_common.py`84%は本機能と無関係の既存ギャップ、他は100%）。
- フロントエンド：`npm run lint`（oxlint）0件、`npx tsc -b`0件、`npm run test`（vitest）1,318件合格、カバレッジ100%（文・分岐・関数・行）。
- 既存の失敗：なし。

## 3. 作業Todo

凡例：`[ ]` 未着手、`[x]` 完了。各項目の完了条件は「テストが通ること」と「カバレッジ100%（例外処理を除く）」。

### 3.1 事前確認

- [x] T-01 `build_with_degradable_entries`の既存呼び出し元を`grep`で確定し、戻り値拡張の影響範囲表（§1.4）を実装前に確定する（結果：5ファイル・6箇所、全て`BuildResult(...)`はキーワード引数構築のため位置引数依存なし）
- [ ] T-02 `ai_context_exam.build_material_summary_text`（総括レポート用の簡易集計）を目標相談の「教材の状態」に使うか、`build_material_status_entries`（日次報告用、締切近い順）を使うか最終確認（仮決定：前者。§6未決事項参照）

### 3.2 文書改訂（U18・1.3）

- [ ] D-01 要件定義書：新節、改訂履歴
- [ ] D-02 仕様書：機能一覧、目標詳細画面仕様、AI-15、設定、改訂履歴
- [ ] D-03 設計書（ロジック・プロンプト編）：処理フロー、プロンプト、検証、`build_with_degradable_entries`拡張の記述、STRIDE、改訂履歴
- [ ] D-04 設計書（データ構造編）：設定キー、改訂履歴
- [ ] D-05 OPERATIONS.md：「目標相談チャットの運用」セクション新設

### 3.3 バックエンド実装

- [ ] B-01 列挙・設定キーの追加（`AiPurpose.GOAL_CONSULTATION`、`ConversationScope.GOAL_CONSULTATION`、`GoalConsultationAnswerStatus`、設定キー4件）
- [x] B-02 `app/ai/prompt_builder.py`：`BuildResult`へ`included_entries`フィールド追加、`build_with_degradable_entries`が生き残ったエントリを返すよう拡張（U20）。既存呼び出し元（T-01で確定）の既存テストが無変更で通ることを確認する回帰テストを追加（2026-10-20：`test_ai_prompt_builder.py`29件合格〈新規4件含む〉、5ファイル・6箇所の呼び出し元テスト〈`test_reading_feedback_service.py`等〉116件合格、ruff合格）
- [ ] B-03 シード：アシスタント既定値・フォルダ名・質問上限・回答上限（`INITIAL_APP_SETTINGS`）、プロンプト本文（`INITIAL_PROMPT_TEMPLATES[AiPurpose.GOAL_CONSULTATION]`）
- [ ] B-04 `prompt_texts_common.py`：`GOAL_CONSULTATION`定数（区切り・nonce・山括弧全角化、「記録から言えること」/「一般的な助言」の分離指示、出典形式`[記録: ...]`/`[要約: ...]`）
- [ ] B-05 `goal_consultation_service.py`：入力検証（`sanitize_question`相当、300字）、禁止語判定（`_contains_forbidden_term`相当、`ai_forbidden_term`共有）、対象カテゴリガード（EXAM以外は`ValidationError`）、過去記録・目標概要・教材・品質指標・リプラン履歴の組み立て（既存`build_*`の呼び出しのみ）、質問ごとのチャット送信、出典検証（日付・週の実在チェック、B-02の`included_entries`を使う）、後始末、直列化（`_REQUEST_LOCK`）
- [ ] B-06 API：`POST /goals/{goal_id}/consultation/questions`、`GET /goals/{goal_id}/consultation/limits`、エラーはドメイン例外→既存のエラー変換
- [ ] B-07 設定の配線：`settings_service.py`（3か所）・`schemas/setting.py`（2クラス）
- [ ] B-08 セキュリティテスト：区切り偽装、`{{...}}`注入、禁止語の正規化回避（全角・空白・大小）、出典の偽装（プロンプトに含めていない日付・週の捏造）、生HTMLの出力、資格以外の目標でのAPI直叩き拒否

### 3.4 フロントエンド実装

- [ ] F-01 `api/goalConsultation.ts`、型の生成し直し（`npm run generate:api-types`）
- [ ] F-02 `features/goalConsultation/`の純粋関数（入力検証、状態→文言の対応）とテスト
- [ ] F-03 `GoalConsultationTab.tsx`（送信中の入力無効化、免責文常時表示、`AiUnconfiguredNotice`導線）、`GoalConsultationAnswer.tsx`（`MarkdownText`描画、出典一覧、日付根拠は`ROUTES.dailyReportView(date)`へのリンク）と描画テスト（XSS回帰）
- [ ] F-04 `GoalDetailPage.tsx`：`EXAM_TABS`へタブ追加、レンダー分岐追加。READING/WORK目標でタブが出ないことの描画テスト
- [ ] F-05 設定画面：`assistantFields.ts`の追加、関連フィクスチャ更新
- [ ] F-06 `ja.json`/`en.json`：`goalConsultation.*`、タブ文言、設定ラベル
- [ ] F-07 `npm run lint`（0件）・`tsc -b`（0件）・`npm run test`（カバレッジ100%）

### 3.5 検証

- [ ] V-01 ruff・pytest・vitest（新規機能のカバレッジ100%。全体の最終実行を§2のベースラインと比較）
- [ ] V-02 実機テスト（テストセット、§4）：範囲内・範囲外・境界・インジェクション・資格以外での拒否
- [ ] V-03 フルスキャンの再確認（横展開：§1.4の各項目が対応済みであることの再確認）

## 4. テスト計画

- 根拠の検証：実在する日付・実在する週、プロンプトに含めていない日付・週（偽の出典）、根拠なしの3パターン
- 禁止語・区切りの偽造・全角や空白の挿入・テンプレート展開の要求：送信されない、または構造が崩れないこと（ヘルプの試行12件と同じ観点を目標相談向けに作り直す）
- 資格以外の目標（READING/WORK）では使えないこと（API直叩き・画面のタブ非表示の両方）
- 上限超過時に最も古い記録（週次要約→生ログの順、既存の縮退順）から外れ、質問文・指示文・目標概要等の固定変数は残ること
- 回答構成（「記録から言えること」/「一般的な助言」の分離）が指示通りに出力されること（実機検証、合否は目視）
- `build_with_degradable_entries`の戻り値拡張が既存5用途（§1.4）の挙動を変えないことの回帰テスト

## 5. 脅威モデル（STRIDE）

| 観点 | 脅威 | 対策 |
| --- | --- | --- |
| Spoofing | 利用者が区切り・nonceを偽造し指示文を上書きする | nonceによる区切り、`<` `>` の全角化（ヘルプと同じ二重防御） |
| Tampering | 利用者が`{{...}}`を使ってテンプレート変数を偽装する | `_substitute`の1回パス処理（既存の修正済み実装を再利用） |
| Repudiation | 質問・回答の記録が残らず、後から確認できない | `ai_log`（`AiPurpose.GOAL_CONSULTATION`）へ記録（既存の仕組みをそのまま使う） |
| Information Disclosure | 他目標・他利用者の記録が誤って混入する／出典が捏造されプロンプトに無い情報を見せかける | `goal_id`で厳密に絞った既存の`build_*`関数のみを使う。出典はプロンプトに実際に含めた日付・週のみ採用（U10） |
| Denial of Service | 長大な質問・記録で応答が打ち切られる、または処理が重なり書き込みロックで他機能が失敗する | 質問300字上限、既存の段階的縮退（週次要約→生ログ）、`_REQUEST_LOCK`による直列化、AI送信区間は既存`serialize_writes()` |
| Elevation of Privilege | READING/WORK目標の利用者がAPIを直接叩いて目標相談機能を使う | サービス層でEXAM以外を`ValidationError`として拒否（画面のタブ非表示は補助的対策に過ぎない） |

## 6. 未決事項

- U4の回答上限（`ai.goal_consultation_answer_max_chars`）の具体的な初期値（2000字のままでよいか、記録量が多い分長めにするか）
- U5の固定文言の最終的な文面（ドラフトのみ確定。実装時に過剰拒否率等の実機検証結果を見て調整する可能性がある）
- T-02（教材の状態の組み立て方：`build_material_summary_text` vs `build_material_status_entries`）
- 設定画面での「目標相談」用フォルダ名・質問上限・回答上限の表示場所（ヘルプの該当設定項目と同じ区画に並べるか、実装時に既存のUIを確認して決める）

## 7. 別件

- 読書・仕事目標への目標相談チャットの展開（S10で検討）
- 相談履歴の永続化・画面への履歴表示（S10で検討）
- 禁止語の管理画面（ヘルプ導入時から仕様上未実装のまま。本改修でも対象外）
