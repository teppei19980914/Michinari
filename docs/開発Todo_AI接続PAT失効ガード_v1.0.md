# 開発Todo：AI接続（PAT）失効時のガード・利用者案内強化

**ステータス: 未着手（本書は計画のみ。コード変更はまだ行っていない）**

## 0. 背景（2026-10-14 実機調査で判明した事象）

NewtonXのPersonal Access Token（PAT）が利用者の操作（NewtonX Web版で「トークンを再生成」）により実質的に失効した状態で、ミチナリが「今日の一言」「ヘルプAIアシスタント」等のAI機能を呼び出すと、以下の連鎖で**利用者に原因が伝わらない汎用エラー（HTTP 502 / 画面上は「時間をおいて再試行してください」）**になっていた。

```
NewtonX側でPATが失効
  → ローカルの認証状態チェック（is_authenticated）は「認証済み」のまま変化なし（/ai/status=200）
  → 実際のAPI呼び出し（フォルダ一覧取得）で401
  → NewtonX ADKの自動再認証も401のまま失敗
  → ADKが401を AuthenticationError ではなく汎用の APIError として投げる
  → ミチナリ側が AI_ERROR(502) に分類（本来は AI_AUTH_REQUIRED(401) であるべき事象）
  → 画面には「時間をおいて再試行してください」のみ表示され、
    利用者は「PATを再生成すべき」と気づけない
```

利用者が偶然NewtonX Web版で「トークンを再生成」したところ解消した（原因の事後確認）。恒久対応として、利用者より以下2点の対応要否確認があった。

1. AI機能（一言・日次報告・ヘルプ等）の呼び出しに必ず「PAT有効性検証」を挟み、事象を未然にガードする。
2. 有効性が失われている場合、「何が起きたか」「設定画面での再生成手順」を画面に案内する。

本書は、上記2点の実施前提として行った**全ソースコードのフルスキャンによる影響範囲の確定**と、それを踏まえた対応方針・作業項目を記録する。

## 1. 重要な前提（ADK実装コードで確認した制約。CLAUDE.md 情報源の信頼性ルール：実装済みソースコードを優先）

- `myvenv/Lib/site-packages/newtonx_adk/config.py` に **PATの有効期限を保持・照会する仕組みは存在しない**。NewtonX Web版の管理画面にのみ有効期限が表示され、ADK/ミチナリ側から事前に「あと何日で切れるか」を取得する公式な手段はない。
  → したがって「有効期限の事前検証」は技術的に不可能であり、実現できるのは**「実際に通信してみて401が返るかどうかで事後的に検知する」**設計に限られる。利用者への回答・以降の文言は「有効期限検証」ではなく「**接続状態（疎通）の検証**」と呼ぶのが正確（0節の表現は是正する）。
- [`newtonx_adk/auth.py:375-405`](../myvenv/Lib/site-packages/newtonx_adk/auth.py) `AuthManager.is_authenticated()` は、PAT文字列が空でないか／ローカルにキャッシュ済みトークン・Cookieがあるかだけを見るローカル専用判定であり、**サーバ側へ疎通確認しない**。
- [`newtonx_adk/client.py:824-838`](../myvenv/Lib/site-packages/newtonx_adk/client.py) `get_model_status()` は、`/models/status`・`/system/models` の両方が非2xxでも**例外を投げず空辞書 `{}` を返す**（401とモデル未提供を区別できない）。
- [`newtonx_adk/client.py:414-423`](../myvenv/Lib/site-packages/newtonx_adk/client.py) `get_folders()`・他の大半のメソッドは、ADK内部の自動再認証後もなお失敗した場合、ステータスコードによらず**常に汎用の `APIError`** を送出する（`AuthenticationError` にはならない）。
- [`backend/app/ai/auth.py:52-78`](../backend/app/ai/auth.py) `register_pat()` のdocstringには、**上記の `get_model_status()` の不確実性が既に文書化**されており、PAT登録時の疎通確認には意図的に `get_assistants()`（非2xxで確実に例外を送出する）を使っている。しかし `get_status()`（`GET /ai/status` の実体、日常の認証状態表示に使われる）は `get_model_status()` を使っており、**この既知の制約が横展開されていない**。
- [`frontend/src/locales/ja.json:1434`](../frontend/src/locales/ja.json) のFAQには「認証状態の『認証済み』表示はPATが設定されていることのみを確認したもので、実際にAI基盤へ接続できるかどうかとは別です」と**既に明記されている**。つまり今回の事象は未知のバグではなく、開発チームが認識しつつ未対応だった既知のギャップである。

## 2. 影響範囲（フルスキャン結果）

### 2.1 根本原因の一元化ポイント（ここを直せば全経路に効く）

| ファイル | 関数 | 問題 |
| --- | --- | --- |
| `backend/app/ai/client.py:102-119` | `_translate_error` | ADKの `APIError` を一律 `AiError`（502）に変換している。自動再認証後もなお401だったケースを判別していないため、`AiAuthRequiredError`（401、再認証導線あり）になるべきものが `AiError` になる |
| `backend/app/ai/auth.py:36-49` | `get_status` | `get_model_status()`（非2xxで握りつぶされる）の成否を「認証済みかどうか」に反映していない。`get_assistants()` 等、確実に例外を送出する方式への統一が必要（`register_pat` と同じ考え方） |

この2箇所は**全てのAI機能が共通して通る経路**（`ai_conversation.ensure_conversation` → `ai_client.create_chat_in_folder_by_name` 等）の入口にあり、CODING_RULES.md①DRYの原則に沿えば、呼び出し側（10サービス）を個別に直すのではなく、まずここを直すのが最優先かつ最小の変更で最大の効果が見込める。

### 2.2 AI基盤を呼び出す全経路（`ai_conversation.ensure_conversation` / `ai_orchestration.send_and_log` の呼び出し元）

`grep` による全文検索で、以下10サービス・14呼び出し箇所を確認した（他に漏れがないことを `ensure_conversation(` の定義ファイルと突き合わせて確認済み）。

| # | サービス | 入口API | 発火契機 | 既存の事前ガード | 失敗時の現状挙動 |
| --- | --- | --- | --- | --- | --- |
| 1 | `daily_message_service.py` | `GET /daily-message` | 画面表示時（自動） | `is_authenticated()` あり（ローカル判定のみ、今回のケースは素通り） | `TodayMessage.tsx` が `isError` を**意図的に握りつぶして何も表示しない**設計（補助表示のため、2026-09時点の既存方針）。※新規の恒久失敗を無言で隠す副作用に注意（§4 D参照） |
| 2 | `help_assistant_service.py` | `POST /help-assistant/questions` | 利用者が質問送信 | `is_authenticated()` あり（同上） | 画面にエラー表示あり。`AI_AUTH_REQUIRED` 専用の案内文言（`helpAssistant.authRequired`）が既に実装済みだが、今回は誤分類によりコード側の汎用文言（`helpAssistant.error`）に落ちていた |
| 3 | `daily_feedback_service.py` | `POST /records/{date}/chat` | 日次記録の対話送信 | なし | 例外がそのままAPI層へ伝播し `apiErrorMessage` の汎用文言（Toast） |
| 4 | `reading_feedback_service.py` | `POST /records/{date}/reading-chat` | 読書記録の対話送信 | なし | 同上 |
| 5 | `work_feedback_service.py` | `POST /records/{date}/work-chat` | 仕事記録の対話送信 | なし | 同上 |
| 6 | `recap_generation_service.py` | `POST /recap/...`（`rebuild_theme`） | 振り返りテーマの再生成操作 | なし | 同上 |
| 7 | `retrospective_service.py` | `POST /closure/...`（目標クローズ時の振り返り生成） | 目標クローズ操作 | なし | 同上 |
| 8 | `work_report_service.py` | `POST /closure/...`（月次報告書生成・2箇所） | 月次/半期報告書生成操作 | なし | 同上 |
| 9 | `work_evaluation_service.py` | `POST /closure/...`（評価レポート生成） | 評価レポート生成操作 | なし | 同上 |
| 10 | `weekly_summary_service.py` | ①起動時バックグラウンド（`main.py` `run_retroactive_generation`）／②データエクスポート時の匿名化再生成（`export_service_common.py`） | ①アプリ起動時（利用者操作なし）／②エクスポート操作 | なし | ①**ログにのみ記録され、利用者へは一切通知されない**（今回の実機ログで確認）。②要確認（`export_progress` の失敗時UIを未調査） |

### 2.3 フロントエンドのエラー表示基盤（既存・DRY）

- `frontend/src/api/client.ts` の `ApiError.localizedMessage` が、エラーコード→`locales/ja.json` の `errors.<code>` へ一元変換する仕組みを**既に持っている**（`errors.AI_AUTH_REQUIRED` = 「AIとの接続が切れています。設定画面で接続を確認してください」）。
- `help_assistant` 機能のみ、コード別の文言分岐（`helpAssistantLogic.ts` `errorMessageKey`）を独自に持つ（§2.2 の2行目）。
- 上記2.2の3〜9（日次/読書/仕事フィードバック、振り返り、報告書、評価レポート）は、**§2.1 を直せば自動的に正しい `AI_AUTH_REQUIRED` 汎用文言が出るようになる**（個別のフロント改修は不要）。ただし文言強化（§4 E）は別途検討。
- `daily_message_service`（#1）は意図的なサイレント失敗設計のため、§2.1だけでは「利用者への案内」にはならない。案内するなら明示的な設計変更が要る（§4 D参照、要相違確認）。

### 2.4 設定画面・ドキュメント

| ファイル | 現状 |
| --- | --- |
| `frontend/src/features/settings/AiAuthStatusCard.tsx` | 「認証状態」は `authenticated` のbool値のみ表示。`model_status` が空のときは何も表示されないため、接続が壊れていても一見「認証済み」としか見えない |
| `frontend/src/locales/ja.json:1434`（FAQ a2） | 「認証済み表示はPATが設定されていることのみの確認」と既に明記。ただし再生成手順への導線はない |
| `frontend/src/locales/ja.json:1435-1436`（FAQ q3/a3） | 「AI連携でエラーが発生しました」の原因として、PAT失効・再生成手順への言及が**ない**（更新要） |
| ヘルプ本文（`help.*` 名前空間、設定画面セクション） | PAT失効時の対処（NewtonX Web版での再生成手順）の記載なし |

## 3. ユーザー提案の確認結果（相違点の指摘）

> 1. 一言取得や日次報告、ヘルプなどNewtonXを使う機能には必ず「PAT有効期限検証機能」を挟む

おおむね方向性は合っているが、2点補足したい。

- 「有効期限検証」は技術的に不可能（§1参照）。実現できるのは「通信してみて401かどうかで判定する**疎通検証**」。
- 「全機能の呼び出しに**毎回**挟む」方式（都度のヘルスチェックAPI呼び出し）は、呼び出しのたびに追加の通信が発生し、レイテンシ増・NewtonX側の呼び出し回数増（CODING_RULES.mdパフォーマンス観点）になる。代替として、
  - (a) `GET /ai/status` の判定精度を上げて**定期的な気づきの機会**にする（§2.1 `get_status`修正）
  - (b) 実際の利用時に401が出たらその場で正しく`AI_AUTH_REQUIRED`として扱う（§2.1 `_translate_error`修正）
  - の組み合わせで、追加の専用ヘルスチェック呼び出しを増やさずに同等の効果を狙える設計を提案したい。「挟む」＝専用の事前チェック呼び出しを新設する方式にするか、この(a)(b)方式にするかは要相談（§5 未決事項1）。

> 2. 有効期限が切れていたら、画面上に「どんなことが起きて」「再生成手順」をメッセージ表示する

方向性は合っている。既存の `errors.AI_AUTH_REQUIRED` 文言・`helpAssistant.authRequired` 文言を土台に、再生成手順（NewtonX Web版 > アカウントメニュー > アクセストークン > 再生成）への具体的な導線を加える方針で対応したい。ただし§2.2の「#1 今日の一言」はサイレント失敗が意図的仕様のため、ここだけは画面表示するかどうかの方針判断が必要（§5 未決事項2）。

## 4. 対応方針（案。実装はまだ行わない）

| 項目 | 内容 | 優先度 |
| --- | --- | --- |
| A | `app/ai/client.py` `_translate_error`：自動再認証後もなお401のケースを `AiAuthRequiredError` に分類する | 最優先（全14箇所に効く一元修正） |
| B | `app/ai/auth.py` `get_status`：`get_model_status()` ではなく確実に例外を出す方式（`get_assistants()` 等）で疎通確認し、`authenticated` の判定精度を上げる | 最優先（Aと対） |
| C | `daily_message_service` / `help_assistant_service`：事前の `is_authenticated()` に加え、実行時に`AiAuthRequiredError`を捕捉した場合の扱いを明確化（#1は現状のフォールバック維持 or 変更、#2は既存の`authRequired`分岐がAで正しく機能する想定） | 高 |
| D | #3〜#9（フィードバック・振り返り・報告書・評価レポート）：Aの修正で自動的に正しい文言が出る。追加改修は文言強化のみ | 中 |
| E | 文言強化：`errors.AI_AUTH_REQUIRED`・`helpAssistant.authRequired`・FAQ（q3/a3）・設定画面に、具体的な再生成手順（NewtonX Web版の操作）を追記 | 高（ユーザー要望2の本体） |
| F | `weekly_summary_service` の起動時バックグラウンド失敗：サイレントのままでよいか、週次要約画面側で気づけるようにするか方針決定 | 要相談（§5 未決事項3） |
| G | `export_service_common.py` の匿名化再生成時のAI失敗時UI挙動を調査 | 調査要 |

## 5. 未決事項（ユーザー確認が必要）

1. 「PAT疎通検証を挟む」の実現方式：都度の専用ヘルスチェック呼び出しを新設する方式か、`/ai/status`の精度向上＋実利用時の401検知の組み合わせ方式か。
2. 「今日の一言」（#1）は現状「取得できなければ静かに何も表示しない」という意図的な設計（`TodayMessage.tsx`コメント）。PAT失効時も同じ扱いでよいか、それとも「AI接続が切れています」等の案内を出すよう設計変更するか。
3. `weekly_summary_service` の起動時バックグラウンド生成失敗（現状ログのみ）を、画面上で気づけるようにする必要があるか。
4. 再生成手順の案内は、エラーメッセージの文言強化（テキストのみ）で足りるか、設定画面への直接リンクやボタン等のUI導線まで必要か。

## 6. 作業手順（Todo、未着手）

- [ ] T-01 §4 A・Bの対応方針についてユーザー承認を得る（§5 未決事項1〜4の回答を含む）
- [ ] T-02 `app/ai/client.py` `_translate_error` の401判定ロジック追加 + 単体テスト（`test_ai_client.py`）
- [ ] T-03 `app/ai/auth.py` `get_status` の疎通確認方式変更 + 単体テスト（`test_ai_auth.py`）
- [ ] T-04 `daily_message_service` / `help_assistant_service` の実行時フォールバック見直し（T-01の決定に従う）+ テスト更新
- [ ] T-05 `errors.AI_AUTH_REQUIRED`・`helpAssistant.authRequired` の文言強化（再生成手順の追記）
- [ ] T-06 FAQ（q3/a3）・ヘルプ本文・設定画面文言の更新
- [ ] T-07 `weekly_summary_service` 起動時失敗の可視化要否に応じた対応（T-01の決定に従う）
- [ ] T-08 `export_service_common.py` の匿名化再生成時のAI失敗時UI挙動の調査・必要なら対応
- [ ] T-09 横展開チェック：§2.2の10サービス全てで同一パターンの回帰テスト追加（例：ADKが401のAPIErrorを投げるケースのモック）
- [ ] T-10 ドキュメント更新（`OPERATIONS.md`・`SPECIFICATION.md`・`CODING_RULES.md`該当箇所、改訂履歴）
- [ ] T-11 全体テスト（`pytest`・`vitest`）、カバレッジ確認

## 7. 完了条件（案）

- [ ] PATが失効した状態（ADKの自動再認証後もなお401）で、§2.2の全経路が `AI_AUTH_REQUIRED` として正しく扱われること（テストで再現・確認）
- [ ] `GET /ai/status` が、実際には疎通できない状態を `authenticated=false` として報告すること
- [ ] 利用者が再生成手順を画面上の文言から辿れること
- [ ] 既存のテスト（バックエンド・フロントエンド）が全て通ること、新規分岐にテストが追加されていること
