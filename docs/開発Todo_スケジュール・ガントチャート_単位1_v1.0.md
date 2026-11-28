# 開発Todo：スケジュール・ガントチャート機能 単位1（祝日基盤） v1.0

入力: `docs/開発Todo_スケジュール・ガントチャート_v1.1.md`（第1章・第2章 D-42〜D-47・第5章・第9章単位1・第15章）。

## 0. ベースライン（着手前に確認）

- main を origin/main へ fast-forward 済み（598c94c）。
- backend: `ruff check .` → All checks passed。`pytest` → 2704 passed, coverage 100%。
- frontend: `npm run lint`（oxlint, エラーなし）・`npm run build`（tsc -b + vite build, exit 0）・`npm test -- --run`（coverage 100%, exit 0）。
- 既知の未コミット残留（範囲外）: `backend/pyproject.toml`・`backend/uv.lock` に 2.11.0→2.12.0 のバージョン差分が残っている。これは本単位着手前に実行された `release.py`/`release.bat` の未完了（公開なし、タグ `ver2.12.0` は存在しない）の残骸で、`release.py` の `build()` が `dirty` 判定後に `write_version` で意図的に作業ツリーを変更する既存の仕様どおりの挙動である。本単位のコミットには含めない（個別ファイル指定でステージする）。

## 1. 脅威分析（STRIDE、簡易）

`/threat-model` スキルが本セッションで利用不可のため、手動でSTRIDE分析を実施（詳細は会話内の報告を参照）。主要リスクは「リリース時に取得したCSVが改ざん・破損していた場合に誤った祝日データが配布されること」で、検証（cp932/列数/日付形式/収録最終年の後退なし）と失敗時中止で軽減する。`GET /holidays` は祝日の日付・名称と収録範囲のみを返し、個人情報・内部状態を含まない。

## 2. 影響範囲表

| ファイル | 変更内容 | 理由 | D-ID |
| --- | --- | --- | --- |
| `backend/app/services/calendar_service.py` | `import_holidays` 内のCSV解析（decode・行解析）を `parse_holiday_csv` として抽出（DB操作を含まない） | release スクリプトの検証と既存の取込みで同じ解析ロジックを共有（DRY） | D-42,D-43 |
| `backend/app/constants/bundle.py` | `HOLIDAY_DIR_NAME`・`HOLIDAY_CSV_FILE_NAME`・`HOLIDAY_METADATA_FILE_NAME` を追加 | 配布物同梱先の名前をビルド時／実行時で単一の情報源にする（既存 `EXAM_TEMPLATES_DIR_NAME` 等と同じ方式） | D-43 |
| `backend/app/content/holidays/holidays.csv`（新規） | 内閣府CSV原本を配置（初回は本単位の着手時点で取得した実データ、1955-2027年収録） | リリース時に `release.py` が更新する対象 | D-43 |
| `backend/app/content/holidays/holidays_metadata.json`（新規） | 取得日時・SHA256・取得元URL・収録範囲を記録 | 同梱メタデータ、起動時の差分検知に使用 | D-43,D-44 |
| `backend/scripts/update_holiday_csv.py`（新規） | 新旧URLを順に試して取得→`parse_holiday_csv`で検証→収録最終年が後退していないか確認→リポジトリ内CSV・メタデータを更新 | D-43の実体 | D-43 |
| `backend/scripts/release.py` | `build()` 内（`dirty`判定後、`generate_build_info`と同じ段）で `update_holiday_csv.update_bundled_holiday_csv()` を呼ぶ | リリース時に組み込む | D-43 |
| `backend/scripts/build_package.py` | `pyinstaller_args()` の `add_data` に祝日CSV・メタデータを追加 | 配布物への同梱 | D-43 |
| `backend/tests/test_build_package_misc.py` | 祝日CSV・メタデータの同梱パス存在確認テストを追加 | 同梱の確認 | D-43 |
| `backend/app/config.py` は変更なし（既存 `resolve_bundled_path` を再利用） | — | 既存の配布パッケージ対応の方式に合わせる | D-43,D-44 |
| `backend/app/constants/app_setting_keys.py` | `HOLIDAY_BUNDLED_CSV_SHA256 = "holiday.bundled_csv_sha256"` を追加 | 前回取り込んだSHA256の記録先（既存 `QUICK_RECORD_LAST_MODE_*` と同じ「実行時に更新される状態値」の慣例に合わせる） | D-44 |
| `backend/app/init/seed_data.py` | 上記キーの初期値 `("", STRING)` を追加 | 初期値投入 | D-44 |
| `backend/app/main.py` | 新関数 `import_bundled_holidays_if_needed()` を追加し、`main()`（実機起動の入口）から `resolve_startup_port()` の後・サーバ起動前に同期呼び出しする。**`bootstrap_database()`/`lifespan`には含めない** | 下記「重要な設計判断」参照 | D-44 |
| `backend/app/api/calendar.py` | `GET /holidays`（`date_from`・`date_to`は省略可）を追加 | API追加 | 第8章,D-46 |
| `backend/app/schemas/calendar.py` | `HolidayRead`・`HolidayListRead` を追加 | スキーマ | 第8章 |
| `backend/app/services/calendar_service.py` | `get_holiday_coverage`（全件からyear_from/year_to算出）・`list_holidays`（期間フィルタ）を追加 | `GET /holidays`の実体 | 第8章 |
| `frontend/src/types/api.d.ts` | `npm run generate:api-types` で再生成 | 手書き禁止 | 第8章 |
| `frontend/src/api/resources.ts` | `getHolidayCoverage()`・`importHolidaysFile(file)`（multipart、`data.ts`の`importDataFile`と同じ方式）を追加 | フロントAPI | D-46 |
| `frontend/src/features/resource/DayTypeDefaultsCard.tsx` | 収録済み年範囲の表示とCSVアップロードUIを追加 | 画面 | D-46 |
| `frontend/src/constants/queryKeys.ts` | `holidayCoverage()` キーを追加 | 既存パターンに合わせる | D-46 |
| `frontend/src/locales/ja.json`・`en.json` | 手動取込UI・年範囲表示の文言を追加 | ゼロハードコーディング | D-48 |
| `backend/app/content/help_content.json` | `export_help_content.py` で再生成 | ja.json由来のため手書き禁止 | D-48 |
| `docs/技術選定書_ミチナリ_v1.0.md` 6.2・6.3・6.5 | 自動取得（リリース時限定）・起動時取込・手動インポート併存へ改訂 | D-49 |
| `docs/OPERATIONS/07_デプロイ/7.4_配布パッケージのビルド.md` | リリース手順に祝日CSV取得工程を追記 | D-49 |
| `docs/仕様書_ミチナリ_v1.0.md`（リソース設定画面の章） | 年範囲表示・手動取込UIを追記 | D-49 |
| `docs/release-notes/`（下書き） | 「祝日を一律で予備日として扱う」が効き始め、ノルマ・完了予測が変わる旨 | D-47 |

## 3. 重要な設計判断（仕様に影響しない実装詳細、理由を記録）

1. **起動時取込みは `bootstrap_database()`/`lifespan` に入れない。** `bootstrap_database()` は `TestClient` の `lifespan` 経由で既存の全APIテスト（`client`フィクスチャ使用）でも毎回実行される。ここに実データの祝日取込みを入れると、実世界の祝日データがテストDBへ無条件に注入され、日付を跨ぐ既存テストの`resolve_day_types`/ノルマ計算の結果が広範囲に変わってしまう（D-47が想定する「意図した変化」の範囲を超える）。既存の `run_ai_startup_tasks`（AI通信を伴うため`bootstrap_database`とは意図的に分離、`app/main.py:295-310`のdocstring参照）と同じ考え方で、`main()`（実機起動の入口）からのみ呼ぶ新関数に分離する。ロジック自体は直接のユニットテストで検証する。
2. **祝日CSV・メタデータの更新はgit commitしない。** `release.py`の`write_version`（バージョン確定）も同様に、`dirty`判定後に作業ツリーへ直接書き込むだけでgit commitしない既存の慣例（`has_uncommitted_changes`は`write_version`より前に呼ばれるため、この書き込みは「dirty」とみなされず`publish`を妨げない）。祝日CSV更新もこれに揃え、`generate_build_info`と同じ段で呼ぶ。
3. **前回取り込んだSHA256の保存先は`app_setting`。** 既存に同種の専用テーブルは無く、`QUICK_RECORD_LAST_MODE_*`（実行時に更新される状態値）と同じ慣例に合わせる。
3'. **「新しい手動データを古い同梱データで上書きしない」判定は、収録最終年の比較だけでは不十分（独立レビューで指摘、2026-11-23に修正）。** 当初は収録最終年の比較のみで判定していたが、これだと同梱CSVが「同じ年の範囲内の内容を訂正する更新」（内閣府の祝日データは法改正等で既存年の日付が事後的に変わることがある）を、SHA256が更新されないまま永久に取り込めなくなる不具合があった。`app_setting`に`holiday.imported_via_manual`（手動インポートが一度でも行われたか）を追加し、**手動インポートが一度も行われていない間は年の比較を行わず常に同梱データを適用**、手動インポートが行われた後だけ年の比較による保護を効かせる方式に修正した。
4. **`GET /holidays`の`date_from`・`date_to`は省略可。** リソース設定画面（年範囲表示のみ）とガント画面（期間指定）の両方から呼べるようにする。省略時は`holidays`は空配列、`year_from`/`year_to`（全件からの収録範囲）は常に返す。

## 4. 回帰の網（15.1手順8、特性テスト）

実装前に、現在の挙動（祝日データ0件の環境）を固定するテストを追加し、変更前のコードで通ることを確認する。

- `test_resolve_day_types_with_no_holidays_treats_all_weekdays_by_default`（祝日0件・`treat_as_buffer=True`でも全日が曜日既定値どおりになること）
- 資格試験のノルマ・完了予測（`resume_service`等、`treat_holiday_as_buffer`を経由する既存の計算）について、祝日0件での現状の出力を固定するテストを1本追加（具体的な対象関数は実装時に`resolve_day_types`の呼び出し元から選定）

## 5. 横展開チェックリスト

| 検索語 | 期待する結果 |
| --- | --- |
| `grep -rn "import_holidays" backend/app` | `calendar_service.py`・`api/calendar.py`のみ。`parse_holiday_csv`抽出後も呼び出し側の挙動が変わっていないこと |
| `grep -rn "HOLIDAY_TREAT_AS_BUFFER\|treat_as_buffer" backend/app` | 既存の参照箇所に加えて新規箇所が無いこと（設定値そのものは変更しない、D-47） |
| `grep -rn "holiday" frontend/src/locales/ja.json frontend/src/locales/en.json` | 追加した文言が両方に存在すること |
| `grep -rn "resolve_bundled_path" backend/app` | 祝日CSV/メタデータの読込みも同じ関数を使っていること |
| `grep -rn "bootstrap_database\|lifespan" backend/app/main.py` | 祝日の起動時取込み呼び出しが`lifespan`経路に含まれていないこと |
| `npm run generate:api-types` 後の diff | 手書きの型定義が残っていないこと |

## 6. チェックリスト（実装）

- [x] D-43: `calendar_service.parse_holiday_csv` を抽出し `import_holidays` から利用（既存テスト無変更で通ること）
- [x] D-43: `backend/app/content/holidays/holidays.csv`・`holidays_metadata.json` を追加（初回は実データ）
- [x] D-43: `backend/scripts/update_holiday_csv.py`（新旧URL・検証・書き込み、ネットワーク未接続でのテストはモック）
- [x] D-43: `release.py`に組み込み、失敗時`SystemExit`（実装当初は`build()`内だったが、開発Todo_スケジュール・ガントチャート_検証修正_v1.0.md 修正2で`main()`の`sync_holiday_csv`へ移動済み。2026-11実態反映）
- [x] D-43: `build_package.py`の`add_data`・`tests/test_build_package_misc.py`
- [x] D-44: `app_setting`キー追加・`seed_data.py`
- [x] D-44: `app/main.py`に起動時取込み関数を追加（`bootstrap_database`に含めない、冪等性のテスト、手動取込みより古いデータでの上書き防止のテスト）
- [x] D-47: 特性テスト追加（第4節）→祝日データ投入後の挙動変化を確認するテストを追加
- [x] 第8章: `GET /holidays`・スキーマ・サービス関数・テスト（認可境界は既存の仕組みに準拠)
- [x] D-46: フロントエンド（年範囲表示・CSVアップロードUI・API型再生成）
- [x] D-48: ロケール・help_content.json
- [x] D-49: 技術選定書6.2/6.3/6.5・OPERATIONS.md・仕様書
- [x] リリースノート下書き（D-47）

## 7. 追跡表

| D-ID | 実装箇所 | テスト名 |
| --- | --- | --- |
| D-42 | `calendar_service.parse_holiday_csv`（内閣府CSVが正であることは変更なし） | `test_calendar_service.py`（既存） |
| D-43（取得・検証・更新） | `backend/scripts/update_holiday_csv.py`（`fetch_holiday_csv`・`validate_holiday_csv`・`update_bundled_holiday_csv`）、`release.py`の`sync_holiday_csv`（実装当初は`build()`内だったが、開発Todo_スケジュール・ガントチャート_検証修正_v1.0.md 修正2で`main()`側へ移動済み。2026-11実態反映） | `tests/test_update_holiday_csv.py`、`tests/test_release.py::test_sync_holiday_csv_*`（3件）、`tests/test_release.py::test_build_cleans_up_stale_leftovers_before_archiving_and_discarding`（`build()`自体の退避・掃除順の検証、祝日CSVは含まない） |
| D-43（配布物への同梱） | `app/constants/bundle.py`（`HOLIDAY_*`）、`scripts/build_package.py`の`pyinstaller_args` | `tests/test_build_package_misc.py::...test_bundles_the_holiday_csv_and_metadata_where_the_runtime_reads_them` |
| D-43（アプリは外部通信しない） | `backend/app/`配下に`urllib`/`requests`呼び出しを追加していないこと（検証: 横展開チェックリスト） | （grepで確認、専用テストなし） |
| D-44（起動時取込み・冪等性・新しい手動データを上書きしない） | `calendar_service.import_bundled_holidays_if_needed`・`mark_manual_holiday_import`、`HOLIDAY_IMPORTED_VIA_MANUAL`（app_setting）、`app/api/calendar.py`の手動インポートエンドポイント、`app/main.py`の`import_bundled_holidays_if_needed`（`bootstrap_database`に含めない） | `tests/test_calendar_service.py::test_import_bundled_holidays_if_needed_*`（7件）・`test_mark_manual_holiday_import_sets_the_flag`、`tests/test_bootstrap.py::test_import_bundled_holidays_if_needed_*`（3件）、`tests/test_phase3_service_guards.py`（2件）、`tests/test_desktop_runner.py`（呼び出し確認付きスタブ）、`tests/test_api_calendar.py::test_import_holidays_endpoint_marks_manual_import` |
| D-45（収録範囲外の年の注記） | 単位3（ガント画面）の対象。`GET /holidays`のAPI自体は本単位で用意済み | — |
| D-46（`GET /holidays`・手動取込みUI） | `app/api/calendar.py`・`app/schemas/calendar.py`・`calendar_service.get_holiday_coverage`/`list_holidays`、`frontend/src/features/resource/DayTypeDefaultsCard.tsx`、`frontend/src/api/resources.ts` | `tests/test_api_calendar.py::test_get_holidays_*`（3件）、`tests/test_calendar_service.py::test_get_holiday_coverage_*`/`test_list_holidays_*`（4件）、`DayTypeDefaultsCard.test.tsx`（9件） |
| D-47（特性テスト） | — | `tests/test_calendar_service.py::test_resolve_day_types_treats_a_real_holiday_as_plan_when_no_holiday_data_imported` |
| D-48（文言） | `ja.json`/`en.json`の`resources.dayTypeDefaults.*`、`help.sections.resources.p2`、`help_content.json`（再生成） | `tests/test_help_content.py`（既存の整合性チェック） |
| D-49（文書） | 技術選定書6.2・6.3・6.5、OPERATIONS/7.4、仕様書6.3 | — |
| D-50 | 本単位では版数を確定しない（変更なし） | — |

## 9. リリースノートの下書き（D-47）

現行の運用（`docs/release-notes/README.md`のA方式、v1.2.2以降は詳細ノートファイルを作らずGitHub Releases本文のみで運用）では、本文はリリース時に`release.bat`が作る下書きをGitHub上で書き換える。版数は本単位では確定しない（D-50）ため、ファイルを先に作らず、ここに文面だけを残す（リリース作業者が下書きへ貼り付ける）。

```
## 祝日データの反映について

本バージョンから、内閣府「国民の祝日」データを同梱し、起動時に自動で取り込むようになりました。
これにより、既定でONになっている「祝日を一律で予備日として扱う」設定（リソース設定画面）が
実際に効き始めます。

資格試験の目標をお使いの場合、祝日が予備日として扱われるようになるため、日々のノルマや完了予測の
数値が変わることがあります（通常は余裕が増える方向の変化です）。この設定はリソース設定画面で
いつでもOFFに変更できます。
```

## 10. 範囲外の改善提案（対応しない判断、15.1手順11）

コミット前の観点別レビューで、フロントエンドの「隠しinput+ボタンクリックでファイル選択」のUIパターン（`useRef`＋`<input type="file" className="hidden">`＋選択後に`value`をリセット）が、本単位の`DayTypeDefaultsCard.tsx`を含めて3箇所（`frontend/src/features/data/DataActionsCard.tsx`・`frontend/src/pages/AttachmentManagementPage.tsx`）で重複しているとの指摘（DRYレビュー、MEDIUM）を受けた。

- multipart送信＋エラーハンドリングの重複（同レビューのHIGH指摘）は本単位の範囲内（`frontend/src/api/resources.ts`の新規コード）のため、`client.ts`の`postMultipart`へ共通化済み（`importDataFile`・`uploadAttachment`も合わせて移行し、カバレッジの抜け漏れも解消）。
- 一方、UIパターンの共通化は`DataActionsCard.tsx`・`AttachmentManagementPage.tsx`という**単位1の範囲外の既存ファイル**の変更を伴う。第15章手順11「単位の範囲外は変更しない」に従い、本単位では対応せず、ここに記録するのみとする。対応する場合は`FileImportButton`等の共通部品（props: `label`・`accept`・`disabled`・`onFileSelected`）への切り出しを推奨する。

## 8. 次の単位への引き継ぎ事項

- `GET /holidays`は単位1で用意済み（期間省略時は収録範囲のみ返す）。単位3（ガント画面）はこのAPIをそのまま使い、D-45「収録範囲外の年の注記」をフロントエンドに実装すること。
- `calendar_service.get_holiday_coverage`・`list_holidays`はテスト済みで単位3からそのまま呼べる。
- `app_setting`に`holiday.imported_via_manual`（HOLIDAY_IMPORTED_VIA_MANUAL）を追加した。単位5（AI修正案）が資格試験の既存締切計算（`material_service.compute_due_date`）を経由して祝日データに依存するため、この依存関係自体は変更していないが、祝日データが「いつ・どちらの経路で」入ったかを追跡できる状態になったことを留意されたい。
- `backend/app/content/holidays/`のCSV・メタデータはgit commit対象外の運用（`release.py`が都度更新）。開発環境で初めてクローンした直後は本単位でコミットした初期データ（1955〜2027年、取得日時2026-11-23）がそのまま使われる。
- フロントエンドのmultipartアップロード共通化（`client.ts`の`postMultipart`）を行った。今後ファイルアップロードを追加する画面は、個別にfetchを書かずこの関数を使うこと。
