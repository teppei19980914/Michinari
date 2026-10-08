# 開発Todo：エラーのコード化（バックエンドの日本語メッセージの解消）v1.0

ゼロハードコーディング（CODING_RULES.md ②）に従い、バックエンドのサービス層から日本語の文言を取り除く。文言は `frontend/src/locales/ja.json` に一元化する。

## 1. 現状（2026-10-07 計測）

| 項目 | 件数 |
| --- | --- |
| サービス層の `raise ...` で日本語を含む箇所 | 104（30ファイル） |
| うち多い順 | `goal_service` 16、`record_service` 14、`subject_service` 11、`resource_service` 8、`backup_service` 5、`calendar_service` 5、`material_service` 5 |
| テストで日本語の文言を直接確認している行 | 138 |

**既存の仕組み（流用する）**
- フロントエンドの `api/client.ts` は、エラーの `details[].reason` を `ja.json` の文言に変換する（`reasonMessage`）。`reason` が無い場合は `errors.<code>`、それも無ければ `errors.default`。
- 例外の `reason` はドメイン例外のクラス属性（`services/exceptions.py`）で持つ。
- つまり、**バックエンドは文言を持たず、`reason` のキーだけを返せばよい**。

## 2. 方針（実施前の調査で簡素化）

当初は全箇所に `reason` を付与する想定だったが、実装着手前に `app/api/errors.py` の
`_STATUS_AND_CODE` と `frontend/src/api/client.ts` の `apiErrorMessage()` を確認した結果、
**画面の文言は例外の型→`code`→`ja.json`の`errors.<code>`で既に一元化されており、
同じ`code`（例：`VALIDATION_ERROR`）を持つ例外はどこで `raise` されても同じ汎用文言を
表示する**ことが判明した（例外メッセージの個々の日本語は、そもそも画面には出ていなかった）。
そのため、`reason` を新設せずに済むものは次の方針へ簡素化した。

1. サービス層の例外の `message` は、技術者向けの英語の短い説明にする（ログと、画面の「詳細」欄に出る任意の技術的補足にのみ使われる。利用者向けの主文言ではない）。
2. 画面の主文言は、既存の例外の型→`code`→`ja.json`の`errors.<code>`で変わらず解決する（`reason` を増やさない）。
3. **既存の `reason` が付いている例外**（`MaterialHasStudyLogsError`・`WorkMemberHasEvaluationReportsError`）はそのまま流用する。今回の104箇所はいずれも新たな `reason` を必要としなかった（画面文言が元から`code`単位の汎用文言だったため）。
4. 今後、個別の画面文言が必要になった場合のみ、専用の `code` または `reason` を追加する（`CODING_RULES.md`②に追記済み）。
5. テストは、日本語の文言の一致ではなく、**例外の型・`code`・（ある場合は）`reason`** で確認する。

## 3. 作業手順（Todo）

- [x] E-01 対象の洗い出し：104箇所を抽出（`raise_inventory.txt`、スクラッチディレクトリ）。実施中に、`exceptions.py` 自身の `super().__init__()` 14箇所、複数行 `raise` 8箇所、モジュール定数（`_MSG_*`・`_ACTION_LABEL`）7箇所、`app/api/errors.py` のフォールバック文言3箇所の計32箇所を追加で検出し、合計136箇所を対象とした（横展開チェック）。
- [x] E-02 `reason` の命名規則の検討 → 不要と判断（2章参照。既存2件以外は新設しない）
- [x] E-03 `ja.json` への追加 → 不要（既存の `errors.<code>` を流用、画面文言は無変更）
- [x] E-04 例外メッセージ・モジュール定数を英語化（136箇所、30+ファイル）。`ruff check`/`ruff format --check` ともに合格
- [x] E-05 テストの書き換え：日本語の文言に依存するテストは2件のみ存在（`test_api_errors.py` の `INTERNAL_ERROR`・`DATABASE_BUSY` の `message` アサーション）。英語文言へ更新。サービス層のテストで日本語文言に依存するものは0件だった（`pytest.raises(..., match=...)`・`str(exc)`比較・`response.json()["error"]["message"] ==` を検索し確認）
- [x] E-06 フロントエンドのテスト・表示確認：`npx vitest run` で149ファイル1252件全て合格。画面文言は`code`→`ja.json`の既存経路のみを使うため無変更
- [x] E-07 `CODING_RULES.md`に、エラーの書き方（英語の技術的な説明＋既存の`code`/`reason`）を追記（②ゼロハードコーディング節）
- [x] E-08 全体テスト：バックエンド `pytest`（1796件）、フロントエンド `vitest`（1252件）とも全件合格。`label-checker`相当の検索（Japanese文字を含むraise/例外初期化/モジュール定数）で残存0件を確認

## 4. 完了条件

- [x] サービス層（`app/services`・`app/ai`）および `app/api/errors.py` に、日本語の `raise`／例外初期化／フォールバック文言が残っていないこと（検査：正規表現検索で0件、2026-10-08確認）。
- [x] 画面に出る文言が従来と同じであること（`code`→`ja.json`の経路を変更していないため不変。フロントエンド1252件のテストで確認）。
- [x] 全テストが通ること（バックエンド1796件・フロントエンド1252件）。カバレッジ計測は本変更では既存の仕組みをそのまま使用（メッセージ文字列の変更のみで分岐を追加していないため、新規テストは不要）。

**2026-10-08 完了**（バージョン2.0.0スコープ）。

## 5. 進め方の注意

- ファイル単位で小さく進め、ファイルごとにテストを通す（一度に全体を変えない）。
- `help_assistant_service.py` の3箇所（自作分）は、この計画の最初の例とする。
- 既存の利用者向けの画面の振る舞いを変えない（文言の差し替えのみ）。
