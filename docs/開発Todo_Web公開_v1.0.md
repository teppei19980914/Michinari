# 開発Todo：Web公開機能（MVP）v1.0

| 版 | 日付 | 内容 |
| --- | --- | --- |
| v1.0 | 2026-11-28 | 初版（調査・設計・開発Todo作成のみ。ソースコード変更なし） |
| v1.1 | 2026-11-28 | 単位1・単位2のソースコード実装を反映（状況・観点別レビュー結果・変更ファイル一覧を各単位の節に記載。本書自体の決定事項・データモデル・STRIDE分析は変更なし） |

本書はミチナリ v3.0.0「Web公開機能（MVP）」の実装前調査・設計・開発Todoである。本セッションでは
ソースコード・依存パッケージ・移行ファイルの変更は一切行っていない（調査結果とドキュメント作成のみ）。

## 0. 本書の位置づけと前提

### 0.1 読み込んだ文書（一次情報源）

- `CLAUDE.md`／`docs/CODING_RULES.md`／`docs/OPERATIONS.md`＋`docs/OPERATIONS/`配下全文書
- `docs/技術選定書_ミチナリ_v1.0.md`
- `docs/要件定義書_ミチナリ_v1.1.md`
- `docs/仕様書_ミチナリ_v1.1.md`＋分割フォルダ（`06_画面仕様/6.2_SC-03_目標詳細・編集.md`等）
- `docs/設計書_データ構造編_ミチナリ_v1.1/`配下（`02_技術構成.md`／`05_テーブル定義/5.2〜5.4・5.8`／`06_API設計.md`／`08_ディレクトリ構成.md`／`09_未決事項.md`）
- `docs/開発Todo_スケジュール・ガントチャート_v1.1.md`＋単位1〜4、`開発Todo_単語帳_v1.0.md`、`開発Todo_復習クイズ_v1.0.md`、`開発Todo_エラーのコード化_v1.0.md`（書式調査）
- `backend/app/`・`backend/tests/`・`frontend/src/`の該当ソース（4並列エージェントによるfile:line単位の調査。詳細は各章に引用）
- `argon2-cffi`公式ドキュメント（https://argon2-cffi.readthedocs.io/ ／ PyPI https://pypi.org/project/argon2-cffi 、2026-11時点最新25.1.0・Argon2idを既定とする一次情報源で確認済み）
- `keyring`（PyPI https://pypi.org/project/keyring ）のWindowsバックエンド挙動・PyInstaller同梱時の既知の不具合報告（Web検索、二次情報源。**本書D-19の判断に必要な一次ソース未検証**、単位4着手前に実機で要検証）

### 0.2 本書の構成

系統A（親文書＋単位分割型、`開発Todo_スケジュール・ガントチャート_v1.1.md`）の構成に倣い、決定事項（D-ID）・データモデル・STRIDE分析を先に固定し、単位1〜6の詳細を1ファイルにまとめる（分割ファイル化はしない。単位ごとの実装時に本書該当章を入力として進める）。

---

## 1. 目的とMVPの範囲

資格試験・読書等の目標でローカル（Windows）作成したガントチャート・単語帳・問題の一部を、本人がボタンで「公開」すると、インターネット経由でPC以外（スマホ等）から閲覧・回答できるようにする。複数人が使う前提とし、利用者ごとに公開先アカウントを分ける。

| 対象 | Web側でできること | Web側でできないこと |
| --- | --- | --- |
| ガントチャート | 閲覧のみ | 作成・編集（ローカルのみ） |
| 単語帳 | 閲覧のみ | 作成・追加・編集（ローカルのみ） |
| 問題（単語帳由来のみ） | 閲覧・回答（正誤・解説が返る） | 作成・追加・編集（ローカルのみ）、出題間隔の進行（MVPでは進めない） |

役割分担：サーバ（ホスティング・DB・ドメイン・TLS・秘密情報投入）の構築は利用者本人。Claude Codeはアプリ（ローカル公開機能＋Web公開サービスのコード）を開発し、サーバ構築者向け環境変数・構成・デプロイ手順を文書化する（付録A）。インフラ作成作業そのものは行わない。

---

## 2. 決定事項一覧（D-ID）

| ID | 決定事項 | 根拠・備考 |
| --- | --- | --- |
| D-01 | 公開対象はローカルの選択済みデータの**スナップショット（コピー）**のみ。日次報告・目標相談・`ai_log`・PAT・振り返り（テーマ）由来の問題は送らない | 利用者決定事項 |
| D-02 | Web側からNewtonXを一切呼ばない。問題はローカルで生成済みのものだけを公開。PATはPCの外に出さない | 利用者決定事項 |
| D-03 | 公開する問題は`quiz_question.vocab_card_id`が入っている行のみ。`theme_id`由来は対象外 | `app/models/quiz.py:28-31`のCHECK制約`ck_quiz_question_single_source`で両カラムは排他的（`(theme_id IS NOT NULL) <> (vocab_card_id IS NOT NULL)`）であることを確認済み。`vocab_card_id IS NOT NULL`で一意に絞り込める |
| D-04 | ガントは目標単位で公開対象を選ぶ。仕事目標は既定で対象外、選ぶと注意文を表示 | 利用者決定事項 |
| D-05 | 祝日の土日色分け算出は「同じロジックを二重実装しない」を最優先。調査の結果、**祝日の個別日付はサーバ提供（`GET /holidays`）、曜日（土日）判定と色分け合成（`computeDayTypeRuns`）はフロント側**（`frontend/src/features/schedule/scheduleGanttGeometry.ts:108-154`）。公開ビューアはこの関数群を再利用する前提で単位3を設計する | バックエンド・フロントエンド両エージェントの調査で一致 |
| D-06 | Webは閲覧・回答専用。Web上で内容を編集する機能は作らない（双方向同期なし） | 利用者決定事項 |
| D-07 | 正誤判定はpublish_serverで実施。回答前のレスポンスに正解番号・解説を含めない | 利用者決定事項。単位2のテストで情報漏洩チェックを必須化 |
| D-08 | Web回答はpublish_serverに履歴記録（一意ID・回答日時・元の問題ID）。ローカル取込は単位5（任意）。MVPではWeb上で出題間隔を進めない | 利用者決定事項 |
| D-09 | Webの「今日」はサーバが返す論理日を使う（クライアント側で論理日を判断しない） | CLAUDE.md規約。既存ローカルAPI`GET /records/today`と同じ設計思想をpublish_server側にも用意 |
| D-10 | ローカルから公開を止めると、サーバ上の該当データを削除する | 利用者決定事項 |
| D-11 | 共有リンクはMVP対象外。ただしテーブル設計だけ用意（公開物ごと・有効期限・取り消し・権限つき） | 利用者決定事項。3章データモデルで`share_link`テーブルを設計のみ先行させる |
| D-12 | 新規トップレベルディレクトリ`publish_server/`に配置 | **既存`CODING_RULES.md`置き場所ルール表には新規トップレベルディレクトリの言及なし（確認済み・要追記、単位1タスク）** |
| D-13 | 技術はPython 3.12 / FastAPI / SQLAlchemy 2.0 / Alembic、DBはPostgreSQLを初期案。接続先・秘密情報は環境変数 | 利用者決定事項 |
| D-14 | Web画面は既存frontendの部品（ガント表示・ロケール）を再利用できる構成で、別エントリとしてビルドしサーバが配信する | `frontend/vite.config.ts`は現状**単一エントリーのみ**（`build.rollupOptions.input`等のマルチページ設定が無いことを確認済み）。拡張または別configファイル新設が必要（単位3） |
| D-15 | DockerfileをWeb公開サービス専用に置いてよいかは**要確認**（10章） | CLAUDE.md「Dockerは使わない」はデスクトップ配布（PyInstaller前提）の既存ルールで、publish_serverはサーバ側コンポーネントで配布方式が異なる。ルールの上書きに相当するため利用者確認必須 |
| D-16 | Web公開アカウントは1人1つ。ローカルの「公開」画面で初回にID・パスワードを設定してアカウントを作る | 利用者決定事項 |
| D-17 | パスワードはArgon2idでハッシュ化。ログイン試行回数制限と一時ロックを入れる | `argon2-cffi`公式ドキュメントでArgon2idを既定とすることを確認済み（0.1節）。具体的な回数・ロック時間は要確認（7章） |
| D-18 | セッションはCookieにHttpOnly・Secure・SameSiteを付与。状態変更リクエストにCSRF対策。CSPを設定 | 利用者決定事項。具体的な実装ライブラリ・フラグ名は単位1着手時にFastAPI/Starlette公式ドキュメントで確認してから選定する（本セッションでは未検証、CLAUDE.md情報源信頼性ルール） |
| D-19 | ローカルアプリはパスワードを保存しない。公開用APIトークンはサーバ側（ローカルPC側）に保管し、ブラウザの記憶領域には置かない。保管方式は**要確認**（10章） | 既存のNewtonX PATは`newtonx_adk/config.py`の実装確認により`~/.newtonx/config.json`へ**平文**保存（暗号化なし、Windows資格情報マネージャー未使用）であることを確認済み。`設計書_データ構造編_ミチナリ_v1.1/05_テーブル定義/5.8_認証情報の保管.md`によれば**v1.0ではOS資格情報ストアへ保管する方針だったが、v1.1で開発キット一本化に変更**した経緯がある（二重管理による不整合を避けるため）。本機能はNewtonXとは無関係の独自トークンのため、同じ制約は無い。`keyring`+`pywin32`でWindows資格情報マネージャーを使う案を検討したが、PyInstaller配布時に`keyring.errors.NoKeyringError`が起きる既知の報告があり（二次情報源、一次ソース未検証）、かつ`pywin32`は現在未導入（`pywin32-ctypes`のみ導入済みを確認）。単位4着手前に実機検証が必須 |
| D-20 | 公開APIで受け取るデータにサイズ・件数・文字数の上限を設ける。値はpublish_server側設定に外部化 | 既存の`app_setting`は閾値外部化の既存パターン（`設計書_データ構造編_ミチナリ_v1.1/05_テーブル定義/5.2_設定・マスタ系.md`）だが、publish_serverはローカルDBと別プロセスのため**ローカル`app_setting`を直接参照できない**。publish_server側に同じ思想の設定機構（環境変数＋DBテーブル）を新設する（単位1）。初期値案は7章 |
| D-21 | すべての取得・回答処理をログイン中のアカウントに限定する（他人のIDを指定しても見えない） | 利用者決定事項。既存ローカルAPIは単一利用者前提で認可境界が無い（`06_API設計.md`6.4「既存エンドポイント全てが無認証」）ため、**publish_serverは既存コードに存在しない認可機構をゼロから設計する**必要がある |
| D-22 | バージョンはメジャーを上げて3.0.0として公開する | 利用者決定事項。`backend/pyproject.toml`（現在2.12.0）・`frontend/package.json`（現在0.0.0、要確認）を単位6で更新 |
| D-23 | publish_serverのDBは既存ローカルSQLiteと完全に別（別プロセス・別エンジン）。既存のSQLite `PRAGMA foreign_keys=ON`依存のCASCADE機構は引き継がず、PostgreSQL側で個別にON DELETE CASCADEを設計する | バックエンド調査で確認：既存`Goal`モデルは`vocab_deck`/`vocab_card`/`quiz_question`/`schedule_revision_proposal`へのORM relationshipが無く、カスケードはSQLite接続ごとの`PRAGMA foreign_keys=ON`（`app/database.py:73`）のみに依存する設計 |
| D-24 | publish_server側のエラーコード体系は、既存`app/api/errors.py`の`_STATUS_AND_CODE`パターン（ドメイン例外→HTTPステータス・コードへの一元変換）と同じ設計思想で、**別実装として**新設する（publish_serverは別ディレクトリ配置のため既存モジュールを直接importしない） | CODING_RULES.md「サービス層でのHTTP例外送出禁止」の方針をpublish_serverにも適用 |
| D-25 | 公開ビューアの画面文言は既存`frontend/src/locales/ja.json`の命名パターン（`<機能>.<画面>.<項目>`）に従い新規キー（`publish.*`等）を追加。`en.json`にも同時追加 | 既存命名規則（`CODING_RULES.md`「命名規則」表）の横展開 |
| D-26 | publish_server用APIにも`openapi-typescript`による型自動生成を適用する | 既存の`generate:api-types`スクリプト（`frontend/package.json:13-14`）と同じ仕組みをpublish_server用に新設 |
| D-27 | 目標の削除・アーカイブが公開済みデータに連動するかは要確認（既定は非連動＝利用者が明示的に「公開停止」する） | 7章「未確定事項」参照 |

---

## 3. データモデル設計（publish_server・新規）

スナップショット方式（D-01）に基づき、既存ローカルテーブルの列を参照しつつ、publish_server独自のテーブルとして設計する（下記は初期案。実装時にSQLAlchemy 2.0・Alembic・選定したPostgreSQLドライバの公式ドキュメントで構文を確認してから確定する＝本セッションでは未検証）。

| テーブル | 主な列 | 備考 |
| --- | --- | --- |
| `publish_account` | id(PK) / username(UNIQUE) / password_hash(Argon2id) / failed_login_count / locked_until / created_at / updated_at | 1アカウント=1利用者（D-16） |
| `publish_api_token` | id(PK) / account_id(FK→publish_account, CASCADE) / token_hash(SHA-256等) / created_at / revoked_at(NULL可) / last_used_at | 平文トークンは発行時のみ返す。保存はハッシュのみ |
| `publish_session` | id(PK, セッショントークンのハッシュ) / account_id(FK, CASCADE) / csrf_token / created_at / expires_at / last_seen_at | Cookieに入れる値はこのidに対応する乱数（D-18） |
| `published_gantt_snapshot` | id(PK) / account_id(FK, CASCADE) / local_goal_id / goal_name / items_json / columns_json / cells_json / published_at / updated_at | `schedule_item`/`schedule_column`/`schedule_cell`相当の内容をJSONでスナップショット。祝日データ自体は含めず、公開ビューア側で既存`GET /holidays`相当を叩く（D-05） |
| `published_vocab_deck` | id(PK) / account_id(FK, CASCADE) / local_deck_id / deck_name / cards_json / published_at / updated_at | `vocab_card`の`card_type`別フィールド流用規則（`backend/app/models/vocab.py:62-75`相当）を踏襲してJSON化 |
| `published_quiz_question` | id(PK) / account_id(FK, CASCADE) / local_question_id / vocab_deck_snapshot_id(FK) / question_text / choices_json / correct_choice_index / explanation / published_at | `correct_choice_index`・`explanation`は回答完了まで応答に含めない（D-07、API層で制御） |
| `quiz_answer_record` | id(PK, 一意ID) / account_id(FK, CASCADE) / question_id(FK→published_quiz_question) / chosen_index / is_correct / answered_at / client_answer_uuid(重複送信対策) | ローカル取込（単位5）時の照合キーとして`local_question_id`・`answered_at`を使う |
| `share_link`（**MVP範囲外・テーブル設計のみ**） | id(PK) / account_id(FK, CASCADE) / target_type(GANTT/VOCAB/QUIZ) / target_id / token_hash / expires_at(NULL可) / revoked_at(NULL可) / permission(VIEW/ANSWER) / created_at | D-11。実装（API・画面）は本MVPに含めない |

既存ローカルDB側の変更は**無い**（`app_setting`に公開サーバURL等の接続設定キーのみ追加。D-20の上限値はpublish_server側設定のため、ローカル`app_setting`には追加しない）。

---

## 4. API設計（概要）

| 区分 | エンドポイント（案） | 認証 | 備考 |
| --- | --- | --- | --- |
| ローカル→公開API | `PUT /api/v1/publish/gantt/{local_goal_id}` 等、種別ごとに差し替え（アップロード=全置換） | APIトークン（Bearer） | D-20の上限超過は400系＋専用コード |
| ローカル→公開API | `DELETE /api/v1/publish/{type}/{local_id}` | APIトークン | 公開停止（D-10）。該当データを即削除 |
| ブラウザ→一覧・閲覧 | `GET /api/v1/view/goals`、`GET /api/v1/view/gantt/{id}` 等 | セッションCookie | account_idで常にフィルタ（D-21） |
| ブラウザ→回答 | `POST /api/v1/view/quiz/{id}/answer` | セッションCookie＋CSRFトークン | 応答に`is_correct`・`explanation`を初めて含める（D-07） |
| 認証 | `POST /api/v1/auth/account`（作成）／`POST /api/v1/auth/login`／`POST /api/v1/auth/logout` | - / セッション | ログイン試行制限（D-17） |
| 今日の論理日 | `GET /api/v1/today` | セッションCookie | D-09。既存ローカルAPI`GET /records/today`と同じ設計思想 |
| ヘルスチェック | `GET /health` | 無し | 単位1 |

---

## 5. 脅威分析（STRIDE、`/threat-model`スキルに基づく）

対象：ローカル→公開API、ブラウザ→閲覧・回答API、アカウント作成、ログイン、トークン失効、公開停止。

| フロー | 脅威種別 | 具体的脅威 | 対策 | 対応方針 | 実装箇所（予定） |
| --- | --- | --- | --- | --- | --- |
| ローカル→公開API | S なりすまし | 漏洩したAPIトークンでの不正アップロード | トークンはハッシュ保存・失効可能、ログへ平文出力しない、TLS必須（サーバ構築者） | Mitigate | `publish_server/app/api/publish.py`／`token_service.py` |
| ローカル→公開API | T 改ざん | 通信経路上でのスナップショット改ざん（MITM） | TLS必須（Transfer：サーバ構築者）、サーバ側で受信後にスキーマ検証 | Mitigate/Transfer | デプロイ手順（付録A） |
| ローカル→公開API | D サービス停止 | 巨大ペイロード送信によるリソース枯渇 | サイズ・件数・文字数上限（D-20）、リクエストボディサイズ制限 | Mitigate | `publish_server/app/api/publish.py` |
| ローカル→公開API | I 情報漏洩 | `theme_id`由来の問題や機微な学習記録が誤って送信される | D-03のフィルタをクライアントだけでなくサーバ側でも二重検証（`vocab_card_id`必須チェック） | Mitigate | `publish_service.py` |
| ブラウザ→閲覧・回答API | S なりすまし | セッションCookie盗難によるハイジャック | HttpOnly/Secure/SameSite、TLS必須 | Mitigate | `publish_server/app/api/auth.py` |
| ブラウザ→閲覧・回答API | T 改ざん | CSRFによる意図しない回答送信・公開停止操作 | 状態変更リクエストにCSRFトークン必須 | Mitigate | 全POST/PUT/DELETEエンドポイント |
| ブラウザ→閲覧・回答API | I 情報漏洩 | 回答前レスポンスに正解番号・解説が含まれる設計ミス | 回答前後でレスポンススキーマを分離し、専用テストで固定（D-07） | Mitigate | `publish_server/app/schemas/quiz.py` |
| ブラウザ→閲覧・回答API | E 権限昇格 | 他アカウントのID推測による閲覧・回答 | 全クエリにaccount_idフィルタを必須化（D-21）。IDの推測困難性も検討 | Mitigate | `view_service.py`／`answer_service.py` |
| ブラウザ→閲覧・回答API | D サービス停止 | 大量回答リクエストによるDB肥大化 | レート制限、回答の冪等性制御（`client_answer_uuid`） | Mitigate | `answer_service.py` |
| アカウント作成 | S なりすまし | ユーザー名列挙攻撃 | 重複確認のレスポンスタイミング差を抑える | Mitigate | `account_service.py` |
| アカウント作成 | R 否認 | 作成記録が残らない | `created_at`記録（監査ログの拡充はMVP範囲外） | Accept | - |
| ログイン | S なりすまし | ブルートフォース・クレデンシャルスタッフィング | 試行回数制限＋一時ロック（D-17） | Mitigate | `account_service.py` |
| ログイン | I 情報漏洩 | エラーメッセージからユーザー存在有無が判別可能 | 「ユーザー名またはパスワードが正しくありません」に統一 | Mitigate | `api/auth.py` |
| トークン失効 | S なりすまし | 失効後もキャッシュされたトークンで操作継続 | 都度DBルックアップ（ハッシュ比較）、即時反映 | Mitigate | `token_service.py` |
| トークン失効 | R 否認 | 失効操作の記録が無い | `revoked_at`記録 | Mitigate | `token_service.py` |
| 公開停止 | T 改ざん | 停止操作後もデータが残存し復元されるリスク | 停止時に該当データを即時削除（D-10）、トランザクション境界を明確化 | Mitigate | `publish_service.py` |
| 公開停止 | D サービス停止 | 削除中の再公開によるレースコンディション | アカウント単位の直列化（既存ローカル`serialize_writes`パターンを参考に検討） | Mitigate | `publish_service.py` |
| 全体 | E 権限昇格 | publish_server DBの管理者権限とアプリ用接続権限の分離不足 | 最小権限のDBユーザーを使う（サーバ構築者の責務） | Transfer | 付録A |

---

## 6. 影響範囲表（既存コードへの影響）

### 6.1 CASCADE・既存削除経路（バックエンド調査結果の要約）

| 項目 | file:line | 内容 |
| --- | --- | --- |
| `Goal`モデル | `backend/app/models/goal.py:92-100` | `vocab_deck`/`vocab_card`/`quiz_question`/`schedule_revision_proposal`へのORM relationshipは無い。DB層CASCADEのみに依存 |
| スケジュール系CASCADE | `backend/app/models/schedule.py:39,57,81,99,102,117` | `goal_id`等すべて`ondelete="CASCADE"` |
| スケジュール改訂CASCADE | `backend/app/models/schedule_revision.py:40,70,73` | CASCADE設定済みだが、**goal削除時のカスケードを検証するテストが見当たらない**（リスク） |
| quiz排他制約 | `backend/app/models/quiz.py:28-31` | `ck_quiz_question_single_source`（D-03の根拠） |
| goal削除カスケードテスト | `backend/tests/test_goal_service.py:596-646` | vocab_deck/vocab_card/quiz_question/quiz_answer_logのカスケードを実機検証済み |
| スケジュールCASCADEテスト | `backend/tests/test_models_crud.py:609-657` | goal_schedule/schedule_item/schedule_column/schedule_cell/schedule_item_historyを検証済み |
| SQLite FK有効化 | `backend/app/database.py:73` | `PRAGMA foreign_keys = ON`を接続ごとに実行。これが無いと既存CASCADEは効かない（publish_server側はPostgreSQLのため直接の影響は無いが、**ローカル側で公開対象を読む際の接続もこの前提に乗っていることを確認する**） |
| 単語帳削除 | `backend/app/services/vocab_service.py:158-160,452-454` | `delete_deck`/`delete_card`はDB CASCADE依存のシンプルな削除 |
| カード編集時のクイズ削除 | `backend/app/api/vocab.py:282-288`、`backend/app/services/quiz_service.py:139-150` | カード内容変更時は`delete_questions_for_vocab_card`で旧クイズを削除 |
| クイズ「作り直す」 | `backend/app/services/quiz_generation_service.py:157-160`、`quiz_service.py:153-166` | `regenerate_for_theme`は未出題分のみ削除（`only_unanswered=True`） |
| テーマ再構築 | `backend/app/services/recap_generation_service.py:130-147` | `rebuild_theme`はquiz_questionを削除しない（本文のみ更新） |
| スケジュール改訂承認 | `backend/app/services/schedule_revision_service.py:608-760` | `decide()`がstale判定・不正日付判定を行い承認/却下を記録 |

### 6.2 バックアップ・エクスポート/インポート

- `backend/app/services/backup_service.py:180-186` `_ordered_table_names()` — `Base.metadata.sorted_tables`を動的取得（特定テーブルのハードコードなし）。公開対象9テーブルは自然に含まれる
- `import_all_data()`（232-266行）は全削除→全INSERTを単一トランザクションで実施。**新規に追加するpublish関連のローカル側テーブル（秘密情報を除く）をエクスポート対象に含めるかはD-27・7章で要確認**
- `backend/app/main.py:192-197` `upgrade_database_schema()`時の安全退避コピー（`create_safety_copy`）はSQLiteファイルコピー方式のため、**publish_server側PostgreSQLには直接関係しない**（別途`pg_dump`等が必要、付録A）

### 6.3 起動処理・設定・エラーコード・配布

| 項目 | file:line | 内容 |
| --- | --- | --- |
| 起動処理 | `backend/app/main.py:210-233,354-384` | `lifespan`→`bootstrap_database`。publish接続設定は既存の`run_all`初期データ投入と同じ仕組み（`app_setting`）に乗せられる |
| 設定API | `backend/app/api/settings.py:67-92` | `GET/PATCH /settings`。公開サーバURL等のローカル設定キーをここに追加 |
| エラーコード | `backend/app/api/errors.py:51-110` | `_STATUS_AND_CODE`。publish_server側は別実装（D-24） |
| client_logs | `backend/app/api/client_logs.py:24-46` | ログインジェクション対策済み（`_sanitize_single_line`）。publish_server側でも同様の対策が必要 |
| PyInstaller同梱 | `backend/Michinari.spec:8-9`、`backend/scripts/build_package.py` | 新規依存（例：D-19でpywin32を採用する場合）を追加する際は同梱設定の見直しが必要 |
| フロントエンドビルド | `backend/app/main.py:81-89`、`backend/app/constants/bundle.py`、`backend/scripts/build_package.py:566-568,602-603` | 単一`frontend_dist`前提。公開ビューア用の別ビルドを同梱する場合は定数・同梱パスの追加が必要（単位3・4） |

### 6.4 フロントエンド既存実装

| 項目 | file:line | 内容 |
| --- | --- | --- |
| 祝日・曜日判定 | `frontend/src/features/schedule/scheduleGanttGeometry.ts:108-154` | `computeDayTypeRuns()`。D-05で公開ビューアも再利用する前提 |
| openapi-typescript | `frontend/package.json:13-14` | `generate:api-types`。publish_server用に同様のスクリプトを新設（D-26） |
| ロケール構造 | `frontend/src/locales/ja.json`（vocab例:1879-1944行、quiz例:1863-1878行） | `<機能>.<画面>.<項目>`パターン（D-25） |
| Vite単一エントリー | `frontend/vite.config.ts`（全164行、複数エントリー設定なし） | D-14の根拠 |
| エラー表示共通化 | `frontend/src/api/client.ts:31-87` | `ApiError`/`apiErrorMessage`/`apiErrorDetail`。publish_server用クライアントも同じパターンを踏襲 |
| ブラウザ記憶領域 | 全文検索済み | 認証情報の書き込みは無し（表示設定のみ`localStorage`使用）。公開ビューアも同方針を踏襲 |

### 6.5 主なリスク（確認済み・要対応）

1. `schedule_revision_proposal`系のgoal削除カスケードにテストが無い（6.1参照）。ガント公開対象には影響するため、単位1〜4着手前に追加するか要検討
2. NewtonX PATが平文保存されている現状に対し、本機能の新規トークンは同じ轍を踏まない設計にする（D-19）
3. `quiz_question.explanation`等、AI生成の学習記録由来の内容が意図せず露出するリスク（D-03で`vocab_card_id`由来のみに限定することで対応済みだが、サーバ側二重検証が必要）
4. `vocab_card.card_type`による列の意味の違い（TERM/SITUATION）を公開APIが誤って解釈するリスク（既存`vocab_service`のロジックを参照・共有する）
5. 新規トップレベルディレクトリ`publish_server/`の置き場所ルールが`CODING_RULES.md`に未整備（単位1で追記）

---

## 7. 開発単位

各単位の実装時は、本書該当章（D-ID・データモデル・STRIDE・影響範囲表）を入力として進める。

### 単位1：Web公開サービスの基盤

**状況（2026-11-28 実装完了）**：下記の変更ファイル一覧どおり実装済み。`publish_server/`配下で
`uv run pytest --cov-fail-under=100`が82件全テスト合格・カバレッジ100%（行・分岐とも）、
`ruff format --check`／`ruff check`も通過。既存`backend/`は無変更で、`uv run pytest`が
2951件合格（既知の`test_desktop_tray`断続フレーク1件を除く、記憶`test_desktop_tray_intermittent_flake`
参照、本変更とは無関係）。単位2以降（公開API・閲覧/回答API等）は未着手。

**観点別レビュー（auth/injection/secret/dependency/dry/style/test-coverage-reviewer、2026-11-28
並列実行）の結果と対応**：

| 指摘元 | 重大度 | 内容 | 対応 |
| --- | --- | --- | --- |
| auth-reviewer | CRITICAL | ログインロック中（423 ACCOUNT_LOCKED）と不在ユーザー（401）で応答が区別でき、ユーザー名列挙のオラクルになっていた | 修正済み：ロック中も`InvalidCredentialsError`（401・INVALID_CREDENTIALS）に統一し、`AccountLockedError`自体を削除した |
| auth-reviewer | HIGH | ロック解除後も`failed_login_count`がリセットされず、15分おきに1回失敗を送るだけで対象アカウントを恒久的にロックし続けられた（永続DoS） | 修正済み：ロック期間が過ぎた時点でカウンタも解除する（`_release_expired_lock`） |
| auth-reviewer / secret-reviewer / test-coverage-reviewer | MEDIUM | CSRFトークンの比較が非定数時間（`!=`） | 修正済み：`secrets.compare_digest`に変更 |
| auth-reviewer | HIGH（受容） | アカウント作成APIがユーザー名重複を400で直接返すため列挙オラクルになる | **対応せず受容**：STRIDE分析5章「アカウント作成」の対策はタイミング平準化のみと明記されており、実装はこれに合致する。D-16によりこのAPIは主にローカルアプリ（単位4）から呼ばれる想定 |
| auth-reviewer | HIGH（保留） | ログイン・登録ともIPベースのレート制限が無い（アカウント単位ロックのみ） | **単位1では対応せず**：付録A・INFRASTRUCTURE.mdの前提どおり、Render等のリバースプロキシ層でのレート制限に委ねる方針とする。アプリ層追加（`slowapi`等）が必要か単位2着手前に要確認 |
| secret-reviewer | HIGH | `session_secret`が未使用の死んだ設定値で、存在しない`validate_for_production`をdocstringが参照 | 修正済み：セッション・CSRFとも署名不要（DB側ハッシュ照合のみ）な設計のため`session_secret`・`is_production_like`を削除。INFRASTRUCTURE.mdから該当環境変数を削除 |
| secret-reviewer | MEDIUM | 未分類例外ハンドラがDB接続例外の生メッセージ（接続情報を含みうる）をログに残す可能性 | 修正済み：`SQLAlchemyError`専用ハンドラを追加し、型名のみをログに残す（`exc_info`を使わない） |
| dry-reviewer | HIGH | `_hash_token`が`session_service.py`と`token_service.py`に同一実装で重複 | 修正済み：`app/services/token_hashing.py`へ共通化 |
| style-reviewer | MEDIUM | `validate_username`/`validate_password`/`create_session`にdocstringが無い、`_ph`という省略名 | 修正済み：docstring追加、`_ph`→`_password_hasher`に改名 |
| test-coverage-reviewer | HIGH | Unicode正規化（NFC/NFD）の相互変換が実際に同一パスワードとして扱われることが未検証 | 修正済み：NFC作成→NFDログイン・NFD作成→NFCログインの両方向テストを追加 |
| test-coverage-reviewer | MEDIUM | `ensure_utc`のaware分岐が統合テスト経由では実質到達しない可能性 | 修正済み：`ensure_utc`の両分岐を直接検証する単体テストを追加 |
| test-coverage-reviewer | LOW | ロック解除後の再試行許可がAPI層（Cookie発行まで）で未検証 | 修正済み：API経由のロック解除テストを追加 |
| （副次的発見） | — | テスト用DBのAlembic移行（`fileConfig`の`disable_existing_loggers`既定True）が全ロガーを無効化し、以後`caplog`が何も捕捉できなくなっていた（backend/app/desktop/logging_setup.pyの`preserve_logging_state`と同根の問題） | 修正済み：`tests/conftest.py`に同趣旨の退避処理を追加（テスト専用、publish_server独自実装） |

**概要**：構成、DB設計、移行、アカウント作成・ログイン・ログアウト、APIトークン、ヘルスチェック、セキュリティヘッダ。

**変更ファイル一覧（新規）**
- `publish_server/pyproject.toml`、`publish_server/app/main.py`（FastAPI app、lifespan、セキュリティヘッダ・CSPミドルウェア）
- `publish_server/app/database.py`（PostgreSQL接続、SQLAlchemy 2.0 engine/session）
- `publish_server/alembic/`（初期migration：`publish_account`/`publish_api_token`/`publish_session`/`share_link`）
- `publish_server/app/models/account.py,token.py,session.py,share_link.py`
- `publish_server/app/services/account_service.py`（アカウント作成、Argon2idハッシュ化、試行回数制限、ロック）
- `publish_server/app/services/token_service.py`（発行・失効・ハッシュ検証）
- `publish_server/app/api/auth.py`、`publish_server/app/api/health.py`、`publish_server/app/api/errors.py`（D-24）
- `publish_server/tests/`一式
- `docs/CODING_RULES.md`（新規トップレベルディレクトリの置き場所ルール追記、D-12）
- `docs/開発Todo_Web公開_v1.0.md`付録A→`docs/INFRASTRUCTURE.md`新規作成（骨子のみ、最終化は単位6）

**テスト観点**
- 正常系：アカウント作成→ログイン→セッションCookie発行→ログアウト。ヘルスチェック200
- 異常系：重複ユーザー名でのアカウント作成エラー、存在しないユーザー／誤パスワードでのログイン失敗
- 認可境界：（単位1ではセッションのアカウント間分離のみ確認。閲覧APIの境界は単位2）
- 不正入力：ユーザー名/パスワードへのSQLi・XSSペイロード、巨大文字列、Unicode正規化
- 認証突破試行：ログイン試行回数制限・ロック中の再試行拒否・ロック解除後の再試行許可、CSRFトークン無しの状態変更リクエスト拒否、セッションCookie属性（HttpOnly/Secure/SameSite）確認

**完了条件**：上記テスト全通過、カバレッジ100%（例外処理除く）、`ruff check`通過、依存追加時は`dependency-reviewer`でOSV上CRITICAL/HIGH無し

**デグレ確認項目**：既存`backend/`に対する変更が無く、既存`pytest`（backend）が全件通過すること

---

### 単位2：公開API・閲覧/回答API

**状況（2026-11-28 実装完了）**：下記の変更ファイル一覧どおり実装済み。`publish_server/`配下で
`uv run pytest --cov-fail-under=100`が140件全テスト合格・カバレッジ100%（行・分岐とも）、
`ruff format --check`／`ruff check`も通過。既存`backend/`は無変更（本単位の変更対象外）。

**概要**：スナップショットの受信・差し替え・公開停止と、閲覧・回答API（ガント・単語帳・問題）、サーバ側正誤判定、回答履歴記録。

**設計上の補足決定（本書の記述からの具体化）**
- アップロードは種別ごとにローカル側ID単位の`PUT`（`/publish/gantt/{local_goal_id}`／
  `/publish/vocab/{local_deck_id}`／`/publish/quiz/{local_deck_id}`）。ガント・単語帳は
  upsert（同一local_goal_id／local_deck_idで上書き、行は維持）。問題のみ、差し替え時に
  既存行を全削除してから再作成する（`published_quiz_question`は`sqlite_autoincrement=True`
  でrowid再利用を防止し、差し替え後は旧IDが必ず無効化される）
- 問題は単語帳デッキのスナップショット（`vocab_deck_snapshot_id`）に従属するため、単語帳が
  未公開の状態で問題だけをアップロードすると`VOCAB_DECK_NOT_PUBLISHED`（400）
- D-20の上限値（10章6節で確定済み）はpublish_server側設定として`PUBLISH_MAX_SNAPSHOT_BYTES`
  ／`PUBLISH_MAX_VOCAB_CARDS`／`PUBLISH_MAX_QUIZ_QUESTIONS`／`PUBLISH_MAX_FIELD_CHARS`の
  4環境変数に実装（`docs/INFRASTRUCTURE.md`反映済み）。文字数上限はpydantic
  `Field(max_length=...)`、件数・バイト数上限はサービス層で検証し、いずれも400＋専用コード
- 「今日」（D-09）はpublish_server側で新規に`PUBLISH_TODAY_BOUNDARY_HOUR`（既定0、UTC）を
  設定可能にした。ローカル側`app_setting`の境界時刻設定とは別管理（別プロセス・複数利用者
  共有のため）
- リクエストボディサイズの事前防御（413）は、FastAPI/Starlette一次サポートの`max_body_size`
  機構（`starlette.middleware.body_limit.RequestBodyLimitMiddleware`、`app/main.py`の
  `FastAPI(max_body_size=...)`）を使う。実際の受信バイト数で判定するため`Content-Length`
  ヘッダに依存せず、`Transfer-Encoding: chunked`でも迂回できない（自前のASGI実装を最初に
  試みたがFastAPI本体の例外変換と衝突したため撤回した経緯は`app/middleware/
  body_size_limit.py`のdocstring参照）。正確な上限判定・専用エラーコードは依然サービス層の
  `_check_snapshot_size`が担う

**観点別レビュー（auth/injection/secret/dependency/dry/style/test-coverage-reviewer、2026-11-28
並列実行）の結果と対応**：

| 指摘元 | 重大度 | 内容 | 対応 |
| --- | --- | --- | --- |
| auth-reviewer / injection-reviewer（参考指摘として一致） | MEDIUM | 回答の冪等性チェック（`client_answer_uuid`検索）が`account_id`でフィルタされておらず、他アカウントの値を知っていれば再送で判定結果を取得できるIDOR的経路になっていた（直後の`get_quiz_question`のフィルタで実害は無かったが間接防御に依存していた） | 修正済み：検索条件に`account_id`を追加。これにより他アカウントが同じ`client_answer_uuid`で新規回答すると一意制約違反になるため、`IntegrityError`を捕捉し専用の`DuplicateClientAnswerUuidError`（400・DUPLICATE_CLIENT_ANSWER_UUID）へ変換するハンドリングも追加 |
| dry-reviewer | HIGH | `upsert_vocab_deck`が既存の`_find_vocab_deck`ヘルパーを使わず同一クエリを重複記述（ヘルパー追加時の片手落ち） | 修正済み：`_find_vocab_deck`を使うよう統一 |
| dry-reviewer | MEDIUM | ガント側に`_find_gantt_snapshot`が無くvocab側と非対称、`view_service.py`の「id+account_idで検索→404」が3関数で同形重複 | 修正済み：`_find_gantt_snapshot`を追加。`view_service.py`に`_get_or_404`（PEP 695ジェネリック）を追加し3関数から利用 |
| dry-reviewer | LOW | 一覧取得2関数（ガント・単語帳）が同形重複、件数上限チェックが2箇所で同形 | 修正済み：`_list_by_account`／`_check_item_count`へ共通化 |
| secret-reviewer | MEDIUM | 新規env var（`PUBLISH_MAX_SNAPSHOT_BYTES`等5件）が`docs/INFRASTRUCTURE.md`の環境変数表に未反映 | 修正済み：同ファイルへ追記（v0.2） |
| style-reviewer | LOW | `_check_size`という関数名が「何のサイズか」を名前から読み取れない、コメント中の「同一goal_idで上書き」が実カラム名`local_goal_id`と表記不一致 | 修正済み：`_check_snapshot_size`に改名、コメント表記を`local_goal_id`に統一 |
| test-coverage-reviewer | MEDIUM | 単語帳の公開停止→問題へのカスケード削除を、サービス層の実経路（`publish_service.delete_vocab_deck`）を通してAPIレベルで検証するテストが無かった（既存はORM直接削除のカスケード検証のみ） | 修正済み：`test_answering_question_after_unpublish_vocab_cascades_to_quiz_is_rejected`を追加 |
| test-coverage-reviewer | LOW | 差し替え後の「旧問題ID無効化」のみ検証し、「新しい問題に正しく回答できる」ことの検証が無かった | 修正済み：`test_answering_newly_published_question_after_replace_succeeds`を追加 |
| injection-reviewer | MEDIUM | body_size_limit.pyの`Content-Length`前提チェックは`Transfer-Encoding: chunked`で迂回可能 | **修正済み**：自前のASGI `receive()`ラップ実装を撤回し、FastAPI/Starlette一次サポートの`max_body_size`機構（`starlette.middleware.body_limit.RequestBodyLimitMiddleware`、インストール済みパッケージのソースで確認済み一次情報源）へ切り替えた。実受信バイト数で判定するため`Content-Length`ヘッダに依存せず、迂回できない設計になる。（補足：自前実装を`HTTPException`サブクラス化して413を試みたが、FastAPI本体のボディ読込処理〈`fastapi/routing.py`〉が例外を一律400へ変換してしまい解消しなかったため、公式機構へ切り替えた経緯を`app/middleware/body_size_limit.py`のdocstringに記録） |
| auth-reviewer | HIGH（受容） | アカウント作成APIのユーザー名列挙オラクル（単位1で受容済み事項の再確認） | 単位1と同じ理由で対応せず（変更なし） |
| dependency-reviewer | — | 新規サードパーティ依存の追加なし（`pyproject.toml`/`uv.lock`はunit1から無変更） | 対応不要（OSVスキャンもCRITICAL/HIGH無しを確認済み、45パッケージ） |
| performance-reviewer | LOW | `view_service.py`の`_list_by_account`が`account_id`単独インデックスのみで`(account_id, updated_at, id)`の複合インデックスが無い | **対応せず・記録のみ**：1アカウントあたりの公開物は数十件程度想定（想定利用規模、開発Todo8章）のため現状無害。将来的な複合インデックス追加は任意検討事項とする |

**変更ファイル一覧（新規）**
- `publish_server/app/api/publish.py`（アップロード/差し替え/停止、APIトークン必須）
- `publish_server/app/api/view.py`（閲覧）、`publish_server/app/api/quiz_answer.py`（回答）、`publish_server/app/api/today.py`（D-09）
- `publish_server/app/models/snapshot_gantt.py,snapshot_vocab.py,snapshot_quiz.py,quiz_answer_record.py`
- `publish_server/app/services/publish_service.py,view_service.py,answer_service.py,calendar_service.py`
- `publish_server/app/schemas/gantt.py,vocab.py,quiz.py`
- `publish_server/app/middleware/body_size_limit.py`（D-20・STRIDE「巨大ペイロード」対策）
- `publish_server/alembic/versions/93c2ed255fee_*.py`（4テーブル新規追加）
- `publish_server/app/api/deps.py`（`get_account_from_api_token`追加）、`app/api/errors.py`・`app/services/exceptions.py`（新規ドメイン例外）、`app/config.py`（D-20・D-09の設定値）、`app/main.py`（ルーター登録）を変更
- `publish_server/tests/`一式（新規テストファイル6本＋既存3本への追加）
- `docs/INFRASTRUCTURE.md`（v0.2、D-20・D-09の環境変数を反映）

**テスト観点**
- 正常系：アップロード→差し替え（同一local_goal_id／local_deck_idで上書き）→閲覧→回答→正誤返却
- 異常系：不正なトークンでのアップロード拒否、サイズ/件数/文字数上限超過（D-20）、存在しない問題IDへの回答
- 認可境界：他アカウントのスナップショットへの閲覧拒否、他アカウントのquestion_idへの回答拒否
- 不正入力：JSON構造破損、選択肢インデックス範囲外値、SQLi/XSSペイロードを含む本文
- 認証突破試行：失効済みトークンでのアップロード拒否、未ログインでの閲覧/回答拒否
- **情報漏洩チェック（D-07必須）**：回答前レスポンスに`correct_choice_index`・`explanation`が含まれないことを固定するテスト
- 公開停止後に取得・回答できないこと（ガント・単語帳〈問題へのカスケードを含む〉・問題単独）
- 差し替え後に古い版の問題へ回答できないこと（かつ新しい版には正しく回答できること）

**完了条件**：上記テスト全通過（140件）、カバレッジ100%、`ruff check`／`ruff format --check`通過

**デグレ確認項目**：既存`backend/`に対する変更が無いこと（本単位は`publish_server/`のみ変更）。単位1のログイン・トークン機構に影響が無いこと（既存82件のテストを含め全140件が通過）

---

### 単位3：Web閲覧画面

**概要**：ログイン、公開物の一覧、ガント閲覧、単語帳閲覧、問題の回答と正誤表示、スマホ表示。

**変更ファイル一覧（新規・調査が必要）**
- 公開ビューア用フロントエンドの配置場所（`frontend/`内の別エントリ vs 新規パッケージ）を単位3着手時に調査・決定（D-14）
- `scheduleGanttGeometry.ts`等の既存ロジックの再利用方法（共有パッケージ化 or 複製、DRY原則との両立を検討。D-05）
- ログイン画面、公開物一覧、ガント閲覧、単語帳閲覧、問題回答画面、スマホ対応CSS
- `frontend/src/locales/ja.json,en.json`（`publish.*`キー追加、D-25）

**テスト観点**
- 正常系：ログイン→一覧→各閲覧→回答→正誤表示。スマホ幅での表示崩れ無し
- 異常系：ログイン失敗時のエラー表示、ネットワークエラー時の表示
- 認可境界：他アカウントの公開物URLを直接指定してもアクセス不可
- 不正入力：回答フォームへの不正値送信時のクライアント側検証
- 認証突破試行：ログイン画面でのブルートフォース試行時のロックアウト表示

**完了条件**：上記テスト全通過、既存`vitest`（frontend）に影響なし

**デグレ確認項目**：既存ガント/単語帳/クイズ画面（ローカル）の表示・動作が変わらないこと（既存テスト全件が通ること）

---

### 単位4：ローカルアプリ側

**概要**：公開サーバの設定、アカウント作成・接続・切断、公開対象の選択と確認画面、公開ボタン、最終公開日時と「未反映の変更あり」の表示、公開停止、通信エラーの扱い。

**変更ファイル一覧（新規・既存変更）**
- `backend/app/api/publish_settings.py`（新規：公開サーバ設定・アカウント作成・接続/切断API）
- `backend/app/services/publish_client_service.py`（新規：publish_serverへのHTTPクライアント）
- トークン保管実装（D-19の確認結果に応じて選定。実機検証を本単位の着手前提とする）
- `frontend/src/pages/PublishSettingsPage.tsx`、`frontend/src/features/publish/*`（新規）
- `frontend/src/locales/ja.json,en.json`（`publish.*`追加）
- `backend/app/constants/bundle.py`、`backend/scripts/build_package.py`、`backend/Michinari.spec`（新規依存を追加する場合の同梱設定見直し）

**テスト観点**
- 正常系：アカウント作成→接続確認→公開対象選択→公開→最終公開日時表示→再公開（差分検知で「未反映の変更あり」表示）→公開停止
- 異常系：publish_server到達不可時のエラー表示、トークン失効時の再認証要求
- 認可境界：他目標のデータを誤って公開対象に含めないことの確認
- 不正入力：公開サーバURL欄への不正値（SSRF対策：意図しない内部アドレス指定時の扱いを検討）
- 認証突破試行：トークン平文が`client_logs`・サーバログに出力されないことの確認（`secret-reviewer`観点）

**完了条件**：上記テスト全通過、**PyInstallerビルド後の実機でトークン保管方式が動作することを確認**（実機検証必須）

**デグレ確認項目**：既存設定画面・AI接続設定等への影響がないこと。既存`pytest`/`vitest`全件が通ること

---

### 単位5（任意）：Webでの回答履歴をローカルへ取り込み

**概要**：Webでの回答履歴をローカルへ取り込み、単語帳の成績と出題間隔に反映する。

**変更ファイル一覧**
- `backend/app/services/vocab_service.py`／`quiz_service.py`（取込時の成績・出題間隔反映処理）
- `backend/app/api/publish_import.py`（新規：publish_serverから回答履歴を取得して取り込むAPI）

**テスト観点**
- 正常系：重複取込防止（`client_answer_uuid`での冪等性）
- 異常系：通信失敗時のロールバック
- 不正入力：改ざんされた回答履歴データ

**完了条件**：既存の単語帳成績・出題間隔ロジックと整合すること

**デグレ確認項目**：既存のローカル出題間隔ロジック（`VocabAnswerLog`等）が壊れないこと

**実施するかは利用者確認事項（10章）**

---

### 単位6：横断の最終確認・ドキュメント更新・3.0.0リリース準備

**概要**：横断の最終確認、ドキュメントの更新、3.0.0のリリース準備。

**変更ファイル一覧**
- `README.md`、`docs/OPERATIONS.md`＋`docs/OPERATIONS/`該当節（特に`03_Git_ブランチ運用.md`へ新規ディレクトリの言及、`07_デプロイ/`へpublish_server用デプロイ手順追加）
- `docs/要件定義書_ミチナリ_v1.1.md`、`docs/仕様書_ミチナリ_v1.1.md`（＋分割フォルダ）、`docs/設計書_データ構造編_ミチナリ_v1.1.md`／`設計書_ロジック・プロンプト編_ミチナリ_v1.1.md`（＋分割フォルダ）
- `docs/技術選定書_ミチナリ_v1.0.md`、`docs/CODING_RULES.md`
- `docs/INFRASTRUCTURE.md`（新規、付録Aの内容を反映して最終化）
- `backend/pyproject.toml`・`frontend/package.json`のバージョンを3.0.0化

**テスト観点**
- 全体回帰：`backend`・`frontend`・`publish_server`それぞれの全テスト
- 配布パッケージビルド（`backend/tests/test_build_package.py`）

**完了条件**：全ドキュメント更新、`release.bat`実行可能な状態

**デグレ確認項目**：既存リリースフロー（`release.bat`→`scripts/release.py`）がpublish_server追加後も動作すること

---

## 8. 共通の注意事項

- 各単位着手前に、該当する`auth-reviewer`／`injection-reviewer`／`xss-reviewer`／`secret-reviewer`／`dependency-reviewer`を変更範囲に応じて並列起動する（CLAUDE.md「コミット前チェック」）
- `publish_server`は新規サブシステムのため、`style-reviewer`・`dry-reviewer`・`label-checker`も新規ファイル追加時に通常どおり起動する
- 本書で確認が必要と明記した箇所（D-15, D-19, 10章）は、該当単位着手前に利用者へ確認してから実装する

## 9. MVPの対象外（本書のスコープ外）

- 共有リンク機能（D-11、テーブル設計のみ先行）
- Web上での内容編集（D-06）
- Webでの出題間隔の進行（D-08、MVPでは進めない）
- 仕事目標のガント公開（既定で対象外。選択時は注意文のみ、D-04）

---

## 10. 未確定事項・要確認（一次ソース未検証を含む）

1. ~~**ホスティング先の候補**（PaaS／VPS等。本書では未確定）~~ → **2026-11-28 利用者確認済み：DBはSupabase（マネージドPostgreSQL）、publish_server本体はRender（Dockerfile不要のPython Native Environment、D-15のDocker要確認を回避）**。単位1はローカル開発・テストのみのため直接の実装影響はないが、`DATABASE_URL`形式（Supabase接続文字列）を前提に単位1のDB接続設定を書く
2. ~~**DBの種類**：PostgreSQL想定で進めてよいか（D-13）~~ → **2026-11-28 利用者確認済み：PostgreSQLで進める**
3. **Dockerfileの扱い**：publish_server専用に限って置いてよいか（D-15、CLAUDE.md既存ルールの例外扱いとなるため要確認）。単位1の変更ファイル一覧にDockerfileは含まれないため単位1に影響なし。単位4〜6着手前に確認
4. **ドメイン**：公開サーバの想定ドメイン・サブドメイン構成。単位1に影響なし。単位6着手前に確認
5. **公開用APIトークンの保管方式**（D-19）：`keyring`+`pywin32`（Windows資格情報マネージャー、PyInstaller配布時の`NoKeyringError`等の既知リスクあり・新規依存追加）か、別方式（例：DPAPI直接呼び出し）か。単位4着手前に実機検証が必要。単位1はpublish_server側のトークン**ハッシュ**保存のみで影響なし
6. ~~**上限値の初期値**（D-20）~~ → **2026-11-28 利用者確認済み：提案初期値のまま進める**

   | 項目 | 確定初期値 |
   | --- | --- |
   | スナップショット1件あたりの最大サイズ | 2MB（JSON化後） |
   | 単語帳カード数上限（公開1件あたり） | 500件 |
   | 問題数上限（公開1件あたり） | 1,000問 |
   | 1フィールドの文字数上限 | 2,000文字 |
   | ログイン試行回数制限 | 5回失敗で15分ロック |
   | APIトークン長 | 32バイト（256bit）乱数、保存はSHA-256ハッシュ |

7. **単位5（Web回答履歴のローカル取込）を実施するか**。単位1に影響なし。単位5着手前に確認
8. **目標の削除・アーカイブと公開済みデータの連動**（D-27）：既定は非連動（利用者が明示的に「公開停止」）で良いか。単位1に影響なし。単位2着手前に確認
9. **新規に追加するローカル側テーブル（公開設定等）をバックアップのエクスポート/インポート対象に含めるか**（6.2節。秘密情報であるトークンは対象外とする前提）。単位1に影響なし（単位1はローカル側テーブルを追加しない）。単位4着手前に確認

---

## 付録A：サーバ構築者向け文書の骨子（`docs/INFRASTRUCTURE.md`へ追記予定）

### 必要な環境変数（案）

| 変数名 | 用途 |
| --- | --- |
| `DATABASE_URL` | PostgreSQL接続文字列（例：`postgresql+psycopg://...`。ドライバは単位1実装時に公式ドキュメントで確認） |
| `SESSION_SECRET` | セッション署名・CSRFトークン生成用の秘密鍵 |
| `CORS_ALLOWED_ORIGINS` | 公開ビューアのオリジン |
| `CSP_*` | CSPヘッダ構成用（単位1で具体化） |
| `MAX_SNAPSHOT_BYTES`／`MAX_SNAPSHOT_ITEMS`／`MAX_FIELD_CHARS` | D-20の上限値 |
| `LOGIN_MAX_ATTEMPTS`／`LOGIN_LOCKOUT_MINUTES` | D-17 |
| `LOG_LEVEL` | ログレベル |

### DB

- PostgreSQL（バージョンは導入時に公式ドキュメントで確認）。Alembicでマイグレーション管理

### TLS前提

- publish_server自体はTLSを終端しない想定（前段のリバースプロキシ／PaaSのTLS終端に委ねる、Transfer）

### ログ

- パスワード・トークン平文をログへ出力しない（`client_logs`の`_sanitize_single_line`相当の対策を踏襲）

### バックアップ

- PostgreSQLの定期`pg_dump`。保持期間は要確認（既存ローカルDBの運用に揃えるか新規決定、10章）

### デプロイ手順（骨子）

1. PostgreSQL用意
2. 環境変数設定
3. Alembicマイグレーション実行（`alembic upgrade head`）
4. publish_server起動（ASGIサーバ、構成は単位1実装時に確定）
5. リバースプロキシ・TLS設定
6. ヘルスチェック確認（`GET /health`）
7. ドメイン・DNS設定

### 想定する無料枠の範囲

- 個人利用規模（数名〜数十名程度）を想定。具体的な推奨サービスはホスティング確定後（10章-1）に記載

---

## 付録B：一次情報源として確認したファイル一覧

- `docs/設計書_データ構造編_ミチナリ_v1.1/05_テーブル定義/5.2_設定・マスタ系.md,5.3_目標系.md,5.4_記録系.md,5.8_認証情報の保管.md`
- `docs/設計書_データ構造編_ミチナリ_v1.1/06_API設計.md,08_ディレクトリ構成.md,09_未決事項.md,02_技術構成.md`
- `docs/仕様書_ミチナリ_v1.1/06_画面仕様/6.2_SC-03_目標詳細・編集.md`
- `docs/CODING_RULES.md`、`docs/OPERATIONS/07_デプロイ/7.4_配布パッケージのビルド.md,7.5_DBマイグレーションを伴う配布パッケージの更新.md`
- `backend/app/models/goal.py,schedule.py,schedule_revision.py,vocab.py,quiz.py`
- `backend/app/services/goal_service.py,vocab_service.py,quiz_service.py,quiz_generation_service.py,recap_generation_service.py,schedule_revision_service.py,backup_service.py`
- `backend/app/api/errors.py,client_logs.py,settings.py`
- `backend/app/ai/auth.py`、`backend/.venv/Lib/site-packages/newtonx_adk/config.py`（第三者ライブラリの実ソース、PAT保管方式の一次確認）
- `backend/Michinari.spec`、`backend/scripts/build_package.py`、`backend/release.bat`
- `backend/tests/test_goal_service.py,test_models_crud.py`
- `frontend/src/features/schedule/scheduleGanttGeometry.ts`、`frontend/vite.config.ts`、`frontend/src/api/client.ts`、`frontend/package.json`
- `frontend/src/locales/ja.json`
- https://argon2-cffi.readthedocs.io/ ／ https://pypi.org/project/argon2-cffi （公式）
- `keyring`のPyInstaller互換性に関するWeb検索結果（二次情報源、要実機検証）
