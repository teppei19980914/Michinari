# 開発Todo：添付ファイル機能（学習・業務資料のAIフィードバック活用）

**本書の位置づけ**：設計・開発計画の作成から実装まで完了（2026-10-25）。実装フェーズ分割計画書（`実装フェーズ分割計画書_ミチナリ_v1.1.md`）への新規Phase追加は行わなかった（S09〜S11と同じ改修シリーズとして、本開発Todo文書のみで管理。利用者確認済み）。実装結果は§8参照。

対象：資格試験の過去問・解答例・講評、ユーザー自身の記述式回答、仕事の関連ドキュメント等を、利用者が共通プールに登録（PDF→テキスト変換して保存）し、日次報告・目標相談チャットのAIフィードバック生成時に複数選択して参照できるようにする。

**目的**：ユーザーが選択した添付ファイルの内容に沿って、その問題・その人に特化した回答（記述式問題の採点を含む）が得られること。出力の形式（採点表等）はミチナリ側で固定テンプレート化せず、ユーザーが都度の質問・指示で自由に求める（A11）。

## 0. 決定事項（AskUserQuestionで確認済み、2026-10-25）

| # | 決定 | 値 | 根拠・理由 |
| --- | --- | --- | --- |
| A1 | 対応付け方法 | ユーザーが日次報告・目標相談チャットの入力時に、登録済みファイルから複数選択する（AIによる自動判定は行わない） | 誤判定（別目標のファイルを誤って参照する等）のリスクを避ける。添付対象は過去問に限らず、ユーザー自身の回答結果・業務ドキュメント等も想定するため、用途が広く自動判定に向かない |
| A2 | 保存粒度 | ファイル単位でまるごとテキスト化して保存する。ファイル名と連番（登録順の一意なシーケンス）をキーとする | 過去問に限らず多様なファイルを想定するため、問題単位の構造化（年度・問題番号等への分解）はスコープが広すぎる。MVPではファイル単位が最小実装 |
| A3 | 対応ファイル形式 | MVPはPDFのみ。他形式（docx/txt等）は順次拡充 | IPA公式配布物等はPDFが主。スコープを絞ることで抽出処理・検証パターンを最小化 |
| A4 | OCR要否 | MVPでは画像解析を行わない。PDFのテキスト情報のみを対象とする。画像解析は順次拡充 | 図表・手書き風の設問等、画像のみでテキスト抽出できないページは対象外（登録時に警告） |
| A5 | 全体のプロンプト文字数上限 | `ai.max_prompt_chars`（既定30,000字）を引き上げる方向で検討する（例: 50,000字程度。実測上限は5万〜10万字の間、[[newtonx_api_verified_behavior]]参照） | 複数ファイルを選択してもすぐに送信中止にならないようにする。既存ドキュメント（16.5）にも「閾値30,000字は暫定であり実測に基づいて調整する」と明記済み |
| A6 | 添付ファイル文字数の縮退時の扱い | 既存の段階的縮退（週次要約→生ログの除外等）の対象外とし、当日入力と同等に扱う | ユーザーが明示的に選んだファイルが黒子で削られる事態を避ける。上限超過時は既存の`DailyFeedbackPromptTooLongError`相当の挙動（送信中止）に合流させる |
| A7 | 1ファイルあたりの抽出文字数上限 | 中程度（例: 20,000字前後）。登録（アップロード）時にバリデーションする | IPA過去問1冊や業務ドキュメント1件を想定した上限。大きすぎるファイルは登録時点で拒否し、送信時の破綻を防ぐ |
| A8 | 管理単位 | goal（目標）に紐づけない、利用者共通プール | 同一ファイル（例: 社内規定、複数資格で共通の基礎知識資料）を複数の目標で使う際に、ファイル実体が目標ごとに重複することを避ける（ユーザー要望、2026-10-25） |
| A9 | 管理画面の配置 | 目標一覧画面の近くに配置する | 共通プールに登録したファイルを目標間で共有できることを、UI上の配置でも表現する（設定画面は目標から離れるため避ける） |
| A10 | 保持上限 | 件数上限を設ける（具体値は§6で検討） | 一覧の見やすさとサーバ容量の両方を抑える |
| A11 | 出力フォーマットの扱い | 固定テンプレート化しない。ユーザーが目標相談チャット・日次報告の自由記述（質問・コメント等）で都度指示を入力する | 本機能の本質は「添付ファイルに沿ったその人独自のフィードバックが得られること」であり、採点表・判定基準等の出力形式を強制することではない（ユーザー確認、2026-10-25）。これにより専用の採点プロンプトテンプレートは不要となり、**既存の目標相談チャット（自由質問＋AI応答）に「添付ファイルの複数選択」を追加するだけ**で実現できると判断する |
| A12 | 問題文等の添付要否 | アプリ側で必須化しない。ユーザーが利用シーンに応じて必要なファイルを選ぶ | 過去問の問題文のように「このケースでは実質必須」なファイルもあるが、添付ファイルの用途は過去問に限らず多様（A1）であり、一律の必須バリデーションはそぐわない |

## 1. 技術的な前提（調査済み事項の要約）

- NewtonX ADK（`myvenv/Lib/site-packages/newtonx_adk/client.py`）には、アシスタント全体へのナレッジ登録API（`add_assistant_knowledge`）とは別に、チャット単位のドキュメントアップロードAPI（`upload_document`, `send_message(document_ids=...)`）がソース上存在する。本機能ではいずれも**使用しない**（A2の通りアプリ側でテキスト化して保存し、既存のプロンプト全文注入方式に統合する）。アシスタント全体へのナレッジ登録を使わない理由は既存設計（`16_AI連携の実装仕様.md` 16.3「アシスタントへのナレッジ登録は行わない」）と同じく、他者と共有されうるアシスタントに個人・組織のデータを混在させないため。
- 入力文字数の実測上限は5万〜10万字の間（[[newtonx_api_verified_behavior]]、2026-10-04実機検証）。公式な上限値はコード・資料に無い。
- 既存の文字数管理の仕組み（`app/ai/prompt_builder.build_with_degradable_entries`、16.5章）をそのまま拡張する前提で設計する（新規の縮退ロジックは作らない、CODING_RULES.md①DRY）。
- 著作権・利用規約（IPA公式PDF等の二次利用・AIへの投入が規約上どう扱われるか）は**未確認**。実装着手前にIPA公式サイトの利用規約を確認する（CLAUDE.md 情報源の信頼性ルール）。

## 2. データモデル案（設計段階の案、未実装）

### 2.1 新規テーブル `attachment`（共通プール、goal_id を持たない）

| 列 | 型 | 備考 |
| --- | --- | --- |
| id | Integer PK | 登録順の連番（A2の「シーケンス」） |
| file_name | String | 元のファイル名（表示用） |
| extracted_text | Text | PDFから抽出したテキスト全文 |
| char_count | Integer | 抽出テキストの文字数。アップロード時に1回だけ確定する不変値であり、CLAUDE.mdが禁止する「日次ノルマ・残量・現在周回」のような可変集計値ではないため、保存してよいと判断（都度算出ルールの対象外） |
| status | Enum | `OK` / `EXTRACTION_FAILED`（テキスト抽出不可）等 |
| created_at | DateTime | |

### 2.2 中間テーブル（利用のたびに紐付け）

- `chat_message_attachment`（`chat_message_id` FK, `attachment_id` FK）— 日次報告のAI対話（`ChatMessage`）に添付ファイルを紐づける
- `goal_consultation_log_attachment`（`goal_consultation_log_id` FK, `attachment_id` FK）— 目標相談チャットの質問（`GoalConsultationLog`）に添付ファイルを紐づける

この2系統に分けるのは、既存のAI対話が日次報告側は`ChatMessage`（`daily_record_id`＋`goal_id`＋`purpose`、[record.py:234](../backend/app/models/record.py#L234)）、相談チャット側は`GoalConsultationLog`（質問単位）という別モデルで管理されているため（調査済み、2026-10-25）。

### 2.3 削除時の扱い（未決、§6）

`attachment`が複数の`chat_message`/`goal_consultation_log`から参照されている状態で削除依頼が来た場合の扱い（物理削除／参照がある限り削除不可／参照ごと削除)は未決定。

## 3. 画面（設計段階の案、未実装）

- 目標一覧画面の近くに「添付ファイル管理」の導線を新設し、一覧・アップロード・削除を行う（A9）。
- 日次報告・目標相談チャットの入力画面側は「登録済みファイルからの複数選択」のみを提供する（その場でのアップロードは行わない、§6で再確認）。
- 選択中ファイルの合計文字数をリアルタイム表示し、全体の送信上限に近い／超えている場合は警告・送信ブロックを行う（事前ガード。サーバ側でも同じ検証を行い、クライアント側の検証だけに頼らない）。

## 4. プロンプトへの注入方法（設計段階の案）

- 既存のNewtonX利用ナレッジ.mdの区切り方式（1リクエスト共用のnonce）に倣い、新規区切りブロック `<<<ATTACHMENTS-{{nonce}}>>>...<<<END-ATTACHMENTS-{{nonce}}>>>` をテンプレートに追加する。
- 添付ファイルのテキストにも、既存の安全対策（山括弧の全角化、禁止語照合、区切り偽造防止）を適用する。ユーザー自身がアップロードする自由記述（回答結果等）にも悪意ある指示文が混入しうるため、質問文と同等の防御が必要（CLAUDE.mdセキュリティチェック・injection-reviewer相当の観点）。
- 添付ファイルはA6の通り縮退対象外とし、既存の「当日の入力を切り詰めない」設計（16.5）と同列に扱う。合計が上限を超える場合は送信を中止し、ユーザーに選択を減らすよう促す（既存`DailyFeedbackPromptTooLongError`と同様のパターンを横展開）。
- **出力フォーマットの固定テンプレート化は行わない（A11）**。既存の目標相談チャット用プロンプトテンプレート（`GOAL_CONSULTATION`系、`app/init/prompt_texts_*.py`）に、添付ファイルの区切りブロックと「添付ファイルの内容を踏まえて回答すること」という指示を追加する程度の変更で足り、専用の採点用テンプレートは新設しない。日次報告フィードバック側（`DAILY_FEEDBACK`系）に同様の添付ファイル参照を広げるかはL4で検討する。
- 出典表示（AIが回答の根拠とした添付ファイルを示す方法）の具体的なUI/フォーマットは実装時に別途検討する。

## 5. ファイル要件（MVP、設計段階の案）

| 項目 | 案 | 状態 |
| --- | --- | --- |
| 対応形式 | PDFのみ | 確定（A3） |
| OCR | 無し（テキスト抽出のみ） | 確定（A4） |
| 1ファイルあたり抽出後文字数上限 | 20,000字前後 | 確定（A7、既定値は`app_setting`で外部化） |
| アップロード時のPDFサイズ上限 | 要検討（案: 20MB程度） | 未決（§6） |
| 保持件数上限 | 設ける | 確定（A10、具体値は§6で検討） |
| 空テキスト（画像のみ等）の扱い | 登録を拒否しエラー表示 | 案（§6で確認） |

## 6. 未決事項（実装着手前に確認・検討が必要）

| # | 論点 | 備考 |
| --- | --- | --- |
| L1 | アップロード時のPDFサイズ上限の具体値 | 案: 20MB。IPA公式配布物の実サイズ感から妥当性を検証 |
| L2 | 保持件数上限の具体値 | 案: 50件程度 |
| L3 | 添付ファイルが複数の記録・会話から参照されている場合の削除方針 | §2.3 |
| L4 | 相談チャットの会話（`goal_consultation_conversation`）単位との関係 | 質問ごとに選び直すか、会話中は選択を保持するか |
| L5 | 日次報告側で添付ファイルをどの操作単位に紐づけるか | 実績入力の都度／日記入力時／確定操作時のいずれか |
| L6 | 日次報告・相談チャット画面でのその場アップロードを許容するか | §3「導線は一本化」（[[user_product_design_motto]]）との整合を要確認 |
| L7 | IPA等、公式過去問PDFの二次利用・AI投入に関する利用規約 | 未確認。CLAUDE.md情報源ルールに基づき実装着手前に公式サイトで確認 |
| L8 | `app_setting`への外部化キー一覧の確定 | `ai.attachment_max_file_chars`・`ai.attachment_max_count`・`ai.attachment_max_pdf_size_mb`等、命名は既存`ai.*`パターンに合わせる |

## 7. 今後の進め方（実施済み）

§6の未決事項（L1〜L8）は、実装計画段階（Plan agentによる検討、利用者確認）で以下のように解消した。

| # | 解消結果 |
| --- | --- |
| L1 | アップロード時のPDFサイズ上限は20MB（`ai.attachment_max_upload_size_mb`既定20）に確定 |
| L2 | 保持件数上限は50件（`ai.attachment_max_count`既定50）に確定 |
| L3 | 添付ファイルの削除は常に許可する。中間テーブル（`chat_message_attachment`・`goal_consultation_log_attachment`）の行のみCASCADE削除し、参照元の対話・質問本体は残る |
| L4 | 相談チャットでの選択はDBに永続化せず、画面のローカルstateで保持する。同一会話を表示中は選択を保持し、会話を切り替えたらリセットする |
| L5 | 日次報告側は、その回の呼び出しで作られるChatMessage（USER発言があればUSER行、無ければASSISTANT行）に添付リンクを紐づける |
| L6 | 日次報告・相談チャット画面でのその場アップロードは許容しない（登録済みファイルからの選択のみ） |
| L7 | IPA等の公式過去問PDFの二次利用規約確認は、利用者自身の責任とする（技術実装の対象外） |
| L8 | `app_setting`キーは`ai.attachment_max_file_chars`・`ai.attachment_max_count`・`ai.attachment_max_upload_size_mb`の3つに確定 |

## 8. 実装結果（2026-10-25完了）

### 8.1 バックエンド

- モデル：`app/models/attachment.py`（`Attachment`・`ChatMessageAttachment`・`GoalConsultationLogAttachment`）
- マイグレーション：`c02c4e8b1cf1`（3テーブル新設）・`2ceb7aa212fc`（`ai.max_prompt_chars`既定値引き上げ、既存環境は値一致ヒューリスティックで更新）・`0ab58c423373`（6テンプレートへATTACHMENTS区切り追加）
- サービス：`app/services/attachment_service.py`（`register`・`list_all`・`delete`・`get_many_or_raise`・`build_attachment_block`。PDFテキスト抽出は`pypdf`を使用）
- API：`app/api/attachment.py`（`POST/GET /attachments`・`DELETE /attachments/{id}`・`GET /attachments/limits`）、スキーマ：`app/schemas/attachment.py`
- 既存サービスへの統合：`goal_consultation_service_common.py`（`ask`・`_answer_locked`・`_save_log`に`attachment_ids`追加）、`daily_feedback_service.py`／`reading_feedback_service.py`／`work_feedback_service.py`（`send_*`に`attachment_ids`追加、添付ブロック専用nonceを新規生成）
- プロンプトテンプレート：`prompt_texts_exam.py`／`_reading.py`／`_work.py`の6定数に`{{attachments}}`・ATTACHMENTS区切りを追加
- `app/ai/prompt_builder.py`：`DailyFeedbackContext`に`attachments`・`nonce`フィールドを追加（既存5呼び出し元はデフォルト値で後方互換）
- `backup_service.py`：`DATA_SCHEMA_VERSION`を1.4→1.5へ更新
- 新規依存：`pypdf`（`pyproject.toml`）

### 8.2 フロントエンド

- API：`frontend/src/api/attachment.ts`
- 部品：`frontend/src/features/attachment/`（`AttachmentPicker.tsx`・`useAttachment.ts`・`attachmentLogic.ts`）
- 画面：`frontend/src/pages/AttachmentManagementPage.tsx`（新規、ルート`/attachments`）、`GoalsListPage.tsx`に導線を追加
- 既存画面への統合：`GoalConsultationTab.tsx`（質問入力欄に`AttachmentPicker`を追加）、`ChatPanel.tsx`（日次報告の対話に`AttachmentPicker`を追加、`useCategoryChat.ts`・`useDailyReportActions.ts`を経由）
- 文言：`ja.json`／`en.json`に`attachment.*`を追加

### 8.3 実装中に見つけた問題と対応

- **区切り偽造の全角化漏れ**（セキュリティ上の欠陥、テストで検出・即修正）：`attachment_service.build_attachment_block`の初期実装は禁止語の再照合のみを行い、山括弧の全角化（`question_safety.DELIMITER_REPLACEMENTS`）を適用していなかった。添付ファイルのテキストに`<<<END-ATTACHMENTS-...>>>`を埋め込むと区切りを偽造できる状態だったため、ファイル名・本文の両方に全角化を適用するよう修正した。
- React Queryの`mutationFn`に関数を直接渡すと、バージョンによって第2引数（`MutationFunctionContext`）が渡り、呼び出し元が1引数だけを期待していると不整合になる。既存コード（`DataManagementPage.tsx`の`importDataFile`）と同じく、`mutationFn: (file: File) => uploadAttachment(file)`の形でラップした。
- **実装完了後の多層レビュー（dry-reviewer・style-reviewer・label-checker・injection-reviewer・dependency-reviewer）で検出し、追加で修正した事項**（2026-10-25）：
  - [HIGH] `attachment_ids`に同じ有効なIDを多数回指定するだけで、選択ファイルの連結テキストを増幅できた（プロンプト肥大化によるDoS）。`attachment_service.get_many_or_raise`で重複除去（`dict.fromkeys`）と選択件数の上限チェック（`ai.attachment_max_count`）を追加した。
  - [HIGH→DRY] `daily_feedback_service.py`・`reading_feedback_service.py`・`work_feedback_service.py`で、ChatMessage往復の保存＋添付ファイル利用リンク付けの約30行がほぼ完全一致で3回重複していた。`record_service_common.append_feedback_turn`へ共通化し、3サービスから呼び出す形にした。
  - [MEDIUM] `POST /attachments`が`async def`のままPDFパース（CPU負荷の高い同期処理）を直接呼んでおり、イベントループを占有して他のリクエストを止めうる状態だった。同期`def`へ変更し、既存の同期ハンドラ（`records.py`等）と同じくスレッドプールへ自動退避されるようにした。
  - [MEDIUM] 禁止語の照合が`extracted_text`のみに適用され、`file_name`（利用者が自由に指定できる）には適用されていなかった。登録時・送信直前の両方でファイル名も照合するようにした。
  - [MEDIUM] `pypdf.PdfReader`の例外捕捉が`PdfReadError`／`ValueError`のみで、壊れたPDF構造が引き起こす他の例外（`RecursionError`等）が未捕捉だった。`except Exception`へ広げ、`ValidationError`に変換するようにした。
  - [LOW] `tests/pdf_helpers.py`内でxref構築ロジックが2関数に重複していたため、`_assemble_pdf`へ共通化。同ファイルに`register_attachment`ヘルパーを追加し、複数のテストファイルで重複していた1行ラッパーを統一した。
  - 未使用のロケールキー（`attachment.uploadError`・`attachment.deleteError`）をja.json/en.jsonから削除した。
  - サービス層の内部DTO`AttachmentRead`（dataclass）がAPI層のPydanticスキーマ`AttachmentRead`と同名だったため、既存命名慣習（`Entry`接尾語）に合わせ`AttachmentEntry`へリネームした。

### 8.4 テスト・検証

- バックエンド：2051件合格、カバレッジ100%（`pytest --cov`）。新規：`test_attachment_service.py`・`test_api_attachment.py`、既存ファイルへの追加：`test_goal_consultation_service_exam.py`・`test_daily_feedback_service.py`・`test_reading_feedback_service.py`・`test_work_feedback_service.py`・`test_backup_service.py`・`test_migration_prompt.py`・`test_seed_data.py`・`test_settings_service.py`・`test_help_assistant_service.py`
- フロントエンド：1381件合格、カバレッジ100%（`npm run test`）。新規：`attachmentLogic.test.ts`・`AttachmentPicker.test.tsx`・`AttachmentManagementPage.test.tsx`
- `ruff check .`・`npx tsc -b`・`npm run lint`いずれも合格
