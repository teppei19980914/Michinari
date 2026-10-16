## 6. API設計

### 6.1 基本方針

| 項目 | 方針 |
| --- | --- |
| 形式 | REST |
| ベースパス | `/api/v1` |
| 認証 | なし（単一利用者、ローカル動作） |
| 応答形式 | JSON |
| エラー形式 | `{ "error": { "code": "...", "message": "...", "details": [...] } }` |
| 日付形式 | ISO 8601（YYYY-MM-DD） |
| 日時形式 | ISO 8601（タイムゾーン付き） |

### 6.2 エンドポイント一覧

**ダッシュボード**

| メソッド | パス | 概要 |
| --- | --- | --- |
| GET | /dashboard | ダッシュボードに必要な全情報を一括取得 |

初期表示2秒以内という性能要件のため、複数のリソースを個別に取得せず1回の呼び出しで返す。今日の一言はAI応答の待機が発生するため本エンドポイントに含めず、未生成時は null を返して別途 GET /daily-message で取得する。

`has_ever_reported_record`（bool）は、カテゴリを問わず1件でも確定済み(REPORTED)の記録があるかを返す。初回記録バナー（仕様書6.1、S-4 4-2）の非表示条件に用いる。`location.state`のような遷移1回限りの状態ではなく実データで判定するため、この値をここに含めた。

`weekly_digests`（`WeeklyDigestRead`の配列、目標ごとに1件、S-4 4-4）は「先週のまとめ」（仕様書6.1）用の値。直前の月曜始まりの週について、`weekly_summary`（`is_anonymized=false`の版）が既に存在すればその`summary_body`を`ai_summary_text`へ、無ければ`metrics_service.compute_weekly_record_summary`が返す非AI集計（`recorded_days`・`total_minutes`。`total_minutes`は資格試験目標のみ非null）を格納する。AI呼び出しは行わずDBの既存データを読むだけのため、今日の一言と異なり`GET /dashboard`へ含めても初期表示2秒以内の性能要件に影響しない。

目標カード（goal_cards）は`category`を含み、`category=READING`の場合はprogress_rate・remaining_daysを書籍の派生値（ページ進捗・読了目標日までの残日数）で置き換え、forecast_deviation_days・has_warning・has_forced_replanは対象外（null／false）とする。書籍の詳細（残日数・直近記録日・連続記録日数・ページ進捗）は`book`フィールドに`BookRead`をそのまま含める（Phase17実装）。`category=WORK`の場合は、progress_rate・remaining_daysに相当する定量指標を持たないため、着手日からの経過日数・直近記録日・連続記録日数・直近の月次報告有無という軽量な表示に置き換える（読書のDSH-06相当の設計を踏襲、6.2「案件」参照）。forecast_deviation_days・has_warning・has_forced_replanはREADINGと同様に対象外（null／false）とする。

**資格試験テンプレート**（1.1改23、実装フェーズ分割計画書Phase38）

| メソッド | パス | 概要 |
| --- | --- | --- |
| GET | /exam-templates | 資格モード作成ウィザードが提示するテンプレート一覧。`backend/app/templates/exams/`配下のJSONを都度読み込む（DBには保存しない）。構文エラー・スキーマ不一致のファイルは警告ログを出して読み飛ばす |

**目標**

| メソッド | パス | 概要 |
| --- | --- | --- |
| GET | /goals | 目標一覧 |
| POST | /goals | 目標作成（`category`を指定。既定値EXAM。試験科目・教材・書籍・案件情報はそれぞれ別エンドポイントで追加する） |
| GET | /goals/{id} | 目標詳細（categoryがEXAMなら科目・教材・配分・負荷プロファイル、READINGなら書籍、WORKなら案件情報`work_assignment`を含む） |
| PATCH | /goals/{id} | 目標更新（`category`は更新不可。リソース配分は本エンドポイントでは扱わず`PUT /goals/{id}/slot-allocations`で更新する） |
| GET | /goals/{id}/slot-allocations | 本目標のスロット別配分の取得。全有効スロットを返し、未配分のスロットは`minutes=0`、あわせて各スロットの連続時間と他目標の配分合計（＝空き時間の算出根拠）を含める |
| PUT | /goals/{id}/slot-allocations | スロット別配分の一括更新。WORK目標に対しては`VALIDATION_ERROR`で拒否する（要件定義書R-74）。いずれかのスロットで合計が連続時間を超える場合は`RESOURCE_EXCEEDED` |
| DELETE | /goals/{id} | 目標削除（DRAFT のみ許可） |
| PATCH | /goals/{id}/archive | アーカイブ（論理削除、ACTIVE以外の状態のみ許可） |
| PATCH | /goals/{id}/unarchive | アーカイブ解除（復元） |
| DELETE | /goals/{id} | 物理削除。実行中以外のすべての状態（アーカイブ済みを含む）で許可。関連データは常にカスケード削除する（1.1改32。旧 `DELETE /goals/{id}/archived` と `cascade_study_logs` は廃止） |
| POST | /goals/{id}/activate | 進行中へ遷移。EXAMでは科目・教材・リソース配分（1スロット以上へ1分以上）を要求する。READINGでは書籍登録済み、WORKでは案件情報登録済みであることのみを要求する（READINGのリソース配分は任意。要件定義書R-64） |
| POST | /goals/{id}/pause | 一時停止へ遷移 |
| POST | /goals/{id}/resume | 中断・完了・一時停止から実行中へ復帰（1.1改32）。資格は再開日から計画を再計算し、警告を戻り値 `warnings` で返す |
| POST | /goals/{id}/complete | 完了へ遷移（資格は全科目の合否登録済みが前提、読書は読了の記録、仕事は納品等の成果を伴う終了）。読了・完了レポートは自動生成せず、出力画面の生成ボタンで生成する（1.1改32・改33） |
| POST | /goals/{id}/abandon | 中断へ遷移（資格・読書は中断、仕事は中止・打ち切り）。実行中・一時停止から可能（1.1改32） |
| POST | /goals/{id}/replan | 基準値を再設定（EXAMのみ） |
| GET | /goals/{id}/baselines | リプラン履歴の取得（EXAMのみ） |

**書籍（category=READINGの場合のみ）**

| メソッド | パス | 概要 |
| --- | --- | --- |
| POST | /goals/{id}/book | 書籍の新規作成（1目標1冊、`goal_id`のUNIQUE制約で保証） |
| PATCH | /books/{id} | 書籍情報の更新（書名、著者、総ページ数、読了目標日） |

書籍の作成は試験科目・教材と同じく目標配下のネストパス（`POST /goals/{id}/book`）とする。データ構造編1.1（改4）時点では「目標作成時に同時に行う」としていたが、実装時（Phase15）に既存の科目・教材と同じ設計（新規作成は`POST /goals/{id}/...`、個別更新は独立エンドポイント）へ揃えた。

**残日数・直近記録日・連続記録日数（・ページ進捗）の取得**

独立した`GET /goals/{id}/plan`は設けない。教材の派生値（総作業量・現在周回・残量・進捗率）が`MaterialRead`に埋め込まれているのと同じ方針で、書籍の派生値は`GET /goals/{id}`および`PATCH /books/{id}`の応答（`BookRead`）に埋め込む（都度算出、保存しない。ロジック・プロンプト編21.2）。データ構造編1.1（改4）時点では別エンドポイントを想定していたが、実装時（Phase15）に教材と同じ「Readスキーマへの埋め込み」方式へ揃えた。

**総括レポート・読了レポートの生成条件（1.1改33）**：`POST /goals/{id}/retrospective` は、資格試験（EXAM）・読書（READING）の目標について、完了（`CLOSED_WITH_RESULT`）の状態でのみ生成する。それ以外（実行中・一時停止・中断）は `INVALID_STATE_TRANSITION`（409）で拒否する。完了操作による自動生成は行わず、利用者が生成ボタンを押したときのみ生成する。匿名化エクスポートでは、完了した目標に限って匿名化版を再生成する（実行中・中断の目標ではAIを呼ばない）。仕事目標は対象外（月次報告・半期評価）。

**案件（category=WORKの場合のみ）**

| メソッド | パス | 概要 |
| --- | --- | --- |
| POST | /goals/{id}/work-assignment | 案件情報の新規登録（1目標1件、`goal_id`のUNIQUE制約で保証）。`role`（評価者／被評価者、任意）を含む |
| PATCH | /goals/{id}/work-assignment | 案件情報の更新（想定業務内容等。更新は上書き、変更履歴は保持しない。要件定義書R-73）。`role`も更新可 |

案件情報の作成・更新は書籍と異なり、目標配下のネストパス（`POST /goals/{id}/work-assignment`）に更新も統一する（`work_assignment`は`id`単体では意味を持たず、常に「その目標の案件情報」として1対1で参照されるため、`books`のような独立リソースパス`/work-assignments/{id}`は設けない）。

**チームメンバー（category=WORKの場合のみ、要件定義書R-93〜R-94、2026-09-23）**

| メソッド | パス | 概要 |
| --- | --- | --- |
| POST | /goals/{id}/work-assignment/members | メンバーの新規登録。`characteristics`を非空で指定する場合は`consent_confirmed=true`が必須（`CONSENT_REQUIRED`） |
| PATCH | /work-members/{id} | メンバーの更新（同意ゲートは作成時と同じ） |
| DELETE | /work-members/{id} | メンバーの物理削除。評価レポートが1件でも存在する場合は拒否（`VALIDATION_ERROR`、`details.reason=WORK_MEMBER_HAS_REPORTS`） |
| POST | /work-members/{id}/deactivate | メンバーの無効化（ソフトデリート） |

一覧取得専用のエンドポイントは設けない。`GET /goals/{id}`が返す`WorkAssignmentRead.members`に無効化済みも含めて全件embedし、目標詳細画面・日次報告画面の双方がこれを参照することで、追加の同期処理なしに双方の画面が常に同じ内容を表示する（要件定義書R-93「同期」）。メンバーの新規作成のみ目標配下のネストパス（`work_assignment`と同じ理由）、更新・削除・無効化は独立リソースパス（`materials.py`と同型）とする。

**月次報告・半期評価（category=WORKの場合のみ）**

| メソッド | パス | 概要 |
| --- | --- | --- |
| POST | /goals/{id}/monthly-report | 月次報告ドラフトの生成（再生成を含む。既存行があれば上書き、ロジック・プロンプト編22.6参照）。クエリパラメータ`period=YYYY-MM`で対象月を指定。省略時は「提出対象年月」の既定値＝前月（今日が2026-09なら"2026-08"）。応答には報告月（`reporting_period_key`、対象月の翌月。DBには保存しない派生値）を含む |
| GET | /goals/{id}/monthly-report | 月次報告の取得。クエリパラメータ`period=YYYY-MM`で対象月を指定。省略時はPOSTと同じ既定値（前月）。応答には報告月（`reporting_period_key`、対象月の翌月。DBには保存しない派生値）を含む |
| PATCH | /goals/{id}/monthly-report | 月次報告レビュー画面での編集（`target_goal_text`・`business_summary`・`achievement_score`・`achievement_reflection`・`next_goal_text`・`report_notes`を利用者が個別に修正。`body`は直接編集させず、保存のたびにテンプレートから再組み立てする。ロジック・プロンプト編22.6）。クエリパラメータ`period=YYYY-MM`必須。対象行が存在しない場合は新規作成する（初回の手動シード。後述の「行が存在しない場合の扱い」を参照）。保存時に`edited_at`を現在時刻に更新する |
| POST | /goals/{id}/semiannual-review | 半期評価レポートの生成（再生成を含む。既存行があれば上書き）。クエリパラメータ`period=YYYY-H1\|YYYY-H2`で対象半期を指定 |
| GET | /goals/{id}/semiannual-review | 半期評価レポートの取得。クエリパラメータ`period=YYYY-H1\|YYYY-H2`で対象半期を指定 |
| PATCH | /goals/{id}/semiannual-review | 半期評価レビュー画面での編集。クエリパラメータ`period=YYYY-H1\|YYYY-H2`必須。項目・挙動は月次報告のPATCHと同様（`report_notes`は半期評価では対象外のため受け付けない） |

いずれも`goal_retrospective`（`period_type`／`period_key`で期間を区別、WORKでは1期間1行）を読み書きする。既存の`POST /goals/{id}/retrospective`（EXAM/READING専用の総括レポート・読了レポート生成エンドポイント）はWORK目標に対してはVALIDATION_ERRORで拒否する。読書がPhase15時点で暫定的に経由した拒否ガード（後にGOAL_RETROSPECTIVE_READINGの実装で解消）と似た挙動だが、仕事目標では月次・半期という別エンドポイントを新設するため、この拒否は恒久的な仕様である点が読書と異なる（`/retrospective`はクローズ時1回のレポートを前提とした設計であり、周期的に生成し続けるWORKの月次・半期報告とは呼び出しの意味が異なるため統合しない）。

**行が存在しない場合の扱い（初回利用者への配慮）**：`target_goal_text`は前期の`next_goal_text`を複製して埋めるため、前期の行が存在しない状態（案件開始直後の初回）でPOSTすると、AIが達成度を判定する対象を持たない（`achievement_score`はNULLのまま、生成される本文にも「比較対象となる前期の目標が無いため今回は評価対象外」と明記する。ロジック・プロンプト編22.6参照）。この状態で運用を続けたくない場合、利用者は`PATCH /goals/{id}/monthly-report?period={前期のperiod_key}`を**POSTで生成する前に**呼び出し、存在しない前期の行を新規作成した上で`next_goal_text`のみ手動入力できる（PATCHは対象行が無い場合、`body`等の生成専用列を空のまま行を新規作成する。この行はAI生成を経ていないため`generated_at`は作成時刻、`edited_at`も同時刻を設定し、いずれもNULLにはしない）。

**AI評価レポート（category=WORKかつrole=EVALUATORの場合のみ、要件定義書R-95〜R-96、2026-09-23）**

| メソッド | パス | 概要 |
| --- | --- | --- |
| POST | /goals/{id}/work-assignment/evaluation-reports | 評価レポートの生成。body で`member_id`・`considerations`を指定。role≠EVALUATORの場合`VALIDATION_ERROR` |
| GET | /goals/{id}/work-assignment/evaluation-reports | 生成履歴の取得（`generated_at`降順）。クエリパラメータ`member_id`で絞込可 |
| PATCH | /goals/{id}/work-assignment/evaluation-reports/{report_id} | レビュー画面での編集（`body`のみ）。保存時に`edited_at`を現在時刻に更新する |

`work_evaluation_report`（5.3）を読み書きする。月次報告・半期評価とは異なり、生成のたびに新規行を追加する（1期間1行upsertではない）ため、PATCHは既存行の更新のみを行い、行が存在しない場合の新規作成（月次報告の「初回利用者への配慮」に相当する仕組み）は設けない（生成は必ずPOST経由で行われ、PATCH単独で新規のレポートを作る運用は想定していないため）。

**試験科目**

| メソッド | パス | 概要 |
| --- | --- | --- |
| POST | /goals/{id}/subjects | 科目追加 |
| PATCH | /subjects/{id} | 科目更新 |
| DELETE | /subjects/{id} | 科目削除 |
| POST | /subjects/{id}/fix-date | 受験日を確定日に変更し計画を再算出 |

**教材**

| メソッド | パス | 概要 |
| --- | --- | --- |
| POST | /goals/{id}/materials | 教材追加 |
| PATCH | /materials/{id} | 教材更新 |
| DELETE | /materials/{id} | 教材削除（実績がある場合は拒否） |
| POST | /materials/{id}/deactivate | 教材の無効化 |
| GET | /materials/{id}/slot-check | スロット充足の検証結果 |
| GET | /materials/{id}/cycles | 周回ごとの進捗、速度、品質の取得 |

**負荷プロファイル**

| メソッド | パス | 概要 |
| --- | --- | --- |
| GET | /goals/{id}/load-profiles | 一覧 |
| POST | /goals/{id}/load-profiles | 追加 |
| PATCH | /load-profiles/{id} | 更新 |
| DELETE | /load-profiles/{id} | 削除 |

**リソース**

| メソッド | パス | 概要 |
| --- | --- | --- |
| GET | /resources/slots | スロット一覧 |
| POST | /resources/slots | スロット追加 |
| PATCH | /resources/slots/{id} | スロット更新 |
| DELETE | /resources/slots/{id} | スロット削除 |
| GET | /resources/allocation | 配分状況と空き容量。スロットごとに、連続時間・目標別の配分時間・未配分の残り時間・超過フラグ（NT-09）を返す |
| GET | /resources/day-type-defaults | 曜日別既定値 |
| PUT | /resources/day-type-defaults | 曜日別既定値の一括更新 |
| GET | /resources/day-boundary-hour | 1日の境界時刻の取得 |
| PUT | /resources/day-boundary-hour | 1日の境界時刻の更新（0〜11時、仕様書10章） |

**カレンダー**

| メソッド | パス | 概要 |
| --- | --- | --- |
| GET | /calendar | 期間指定で日種別と記録状態を取得 |
| PUT | /calendar/{date}/day-type | 日種別の個別指定 |
| DELETE | /calendar/{date}/day-type | 個別指定の解除 |
| POST | /calendar/holidays/import | 祝日データの取込 |

**日次記録**

| メソッド | パス | 概要 |
| --- | --- | --- |
| GET | /records/today | 論理的な本日の日付と記録状態を取得 |
| GET | /records/{date} | 指定日の記録取得 |
| POST | /records/{date}/progress | 進捗のみ登録 |
| POST | /records/{date}/chat | AI対話の実行（1往復。資格試験＝DAILY_FEEDBACK） |
| POST | /records/{date}/reading-chat | 読書のAI対話の実行（1往復。DAILY_FEEDBACK_READING。Phase16実装） |
| POST | /records/{date}/work-chat | 仕事のAI対話の実行（1往復。DAILY_FEEDBACK_WORK） |
| POST | /records/{date}/finalize | 資格試験の報告確定 |
| POST | /records/{date}/reading-finalize | 読書の報告確定（1.1（改16）） |
| POST | /records/{date}/work-finalize | 仕事の報告確定（1.1（改16）） |
| GET | /records/{date}/quota | 指定日の日次ノルマ取得 |
| GET | /records/{date}/previous-diary | 「前回はこう書いていました」ヒント用、goal_id指定（1.1（改22）） |
| GET | /records/{date}/previous-reading-log | 同上、book_id指定（1.1（改22）） |
| GET | /records/{date}/previous-work-log | 同上、work_assignment_id指定（1.1（改22）） |
| POST | /records/{date}/comments | コメント追加 |
| PATCH | /comments/{id} | コメント更新 |
| DELETE | /comments/{id} | コメント削除 |

`GET /records/today` は、1日の境界時刻を考慮した論理的な本日を返す。クライアント側でシステム日付から判断しない。返す記録状態は3カテゴリの集約値である（5.4参照）。

`POST /records/{date}/progress`（進捗のみ登録）は、`study_log`（教材別実績）・`reading_log`（書籍別の想起記録）・`work_log`（案件別の業務記録）の配列をまとめて受け付ける。入力があったカテゴリのみ確定済みガード・状態更新の対象になるため、他カテゴリが確定済みでも影響しない。

報告確定は`/finalize`（資格試験、`study_log`＋日記）・`/reading-finalize`（読書、`reading_log`）・`/work-finalize`（仕事、`work_log`）にカテゴリごとに分離する（1.1（改16）。AI対話エンドポイントの`/chat`・`/reading-chat`・`/work-chat`分離と同じ設計方針）。従来は`/finalize`が3カテゴリの実績を一括で受け取り単一の記録状態を更新していたため、1カテゴリの確定が他カテゴリの確定状態まで変えてしまっていた。書籍・案件ごとの個別エンドポイントは設けない（`study_log`と同様、配列で複数件をまとめて受け付ける）。`study_log`/`reading_log`/`work_log`のいずれも配列が空（0件）の状態で`/finalize`系を呼ぶことを禁止していない。これを利用し、「今日は何もしていない」ボタン（1.1（改28）、記録画面改善タスク）は空配列でカテゴリを確定する（実績行を作らずカテゴリの確定状態のみREPORTEDにする）。

`GET /records/{date}/previous-diary`・`/previous-reading-log`・`/previous-work-log`（1.1（改22））は、記述欄の「前回はこう書いていました」ヒント表示専用の読み取りAPIである。それぞれ対象（goal_id／book_id／work_assignment_id）を必須クエリパラメータとして受け取り、対象日より前で本文のある直近1件の`record_date`・本文を返す（該当が無ければ`null`。存在確認をエラーにしない設計は、フロントの「前回の記録が無い場合は表示しない」という任意表示の性質に合わせたもの）。空文字/NULLの本文（`daily_goal_diary.diary_body`は任意入力のため空文字の行がありうる）は「前回」として提示する意味がないため対象から除く。

**AI対話エンドポイントの分離について**：データ構造編1.1（改4）時点では「`POST /records/{date}/chat` を目標ごとに独立した会話として扱う（category別にAiPurposeを切り替える）」としていたが、実装時（Phase16）に既存の`/chat`（DAILY_FEEDBACK、goal_id=NULLで複数の資格試験目標を1回答に集約する設計。16.3）とは別エンドポイント `POST /records/{date}/reading-chat`（DAILY_FEEDBACK_READING）に分離した。1回のHTTP呼び出しでcategoryを跨いで多重応答させる設計は複雑さに見合わないため、「用途ごとに会話を分離する」既存方針（16.3）をエンドポイント単位でも踏襲した。仕事目標のAI対話（`POST /records/{date}/work-chat`、DAILY_FEEDBACK_WORK）も同じ設計思想で、読書と対称の別エンドポイントとして新設する。

**分析**

| メソッド | パス | 概要 |
| --- | --- | --- |
| GET | /analytics/quality | 品質指標推移（教材別、周回別、粒度指定） |
| GET | /analytics/progress | 累積完了量と計画線 |
| GET | /analytics/forecast | 完了予測と乖離 |
| GET | /analytics/speed | 実効速度推移（周回別） |
| GET | /analytics/gantt | ガントチャート用データ |

**完了処理とエクスポート**

| メソッド | パス | 概要 |
| --- | --- | --- |
| POST | /subjects/{id}/result | 受験結果の登録 |
| PATCH | /results/{id} | 受験結果の更新（クローズ前のみ） |
| GET | /goals/{id}/retrospective | 総括レポート（categoryがREADINGの場合は読了レポート）の取得。categoryがWORKの場合は対象外（VALIDATION_ERROR、下記「案件（category=WORKの場合のみ）」の月次報告・半期評価エンドポイントを使用する） |
| POST | /goals/{id}/retrospective | 総括レポート（読了レポート）の生成・再生成。categoryがWORKの場合は対象外（VALIDATION_ERROR） |
| GET | /goals/{id}/knowledge-export/preview | エクスポート内容のプレビュー |
| POST | /goals/{id}/knowledge-export | ナレッジエクスポートの実行 |
| GET | /goals/{id}/knowledge-export/progress | 匿名化実行中の進捗取得（ポーリング用） |

`POST /goals/{id}/knowledge-export` のリクエストには、含める項目のリストと匿名化の有無、出力形式を指定する。匿名化時は複数回のAI呼び出し（週次要約1件ずつ＋総括レポート）を伴いブロッキングするため、`GET /goals/{id}/knowledge-export/progress` をポーリングして進捗（完了件数／合計件数）を表示する（実装フェーズ分割計画書Phase10注意点）。進捗はプロセス内メモリで保持し、DBには保存しない。読書目標（category=READING）では週次要約が存在しないため、匿名化時のAI呼び出しは読了レポートの再生成のみとなる。仕事目標（category=WORK）も週次要約を持たないため、匿名化時のAI呼び出しは対象goalに紐づく全`goal_retrospective`（period_type問わず、すなわち生成済みの月次報告・半期評価の全件）の再生成となる。

**設定・データ管理**

| メソッド | パス | 概要 |
| --- | --- | --- |
| GET | /settings | 設定一覧 |
| PUT | /settings | 設定の一括更新 |
| GET | /settings/prompts | プロンプトテンプレート一覧 |
| PUT | /settings/prompts/{purpose} | テンプレート更新 |
| POST | /settings/prompts/{purpose}/reset | テンプレートを初期値に戻す |
| GET | /ai/status | 認証状態とAI基盤の稼働状況 |
| POST | /ai/login | 認証の実行（非同期）。PAT指定時の`authenticated`は、ローカルのPAT形式チェックに加え、軽量なAPI呼び出し（アシスタント一覧取得）による実疎通確認の結果（S-5 5-2、ロジック・プロンプト編16.2） |
| POST | /ai/logout | トークンの破棄 |
| GET | /ai/assistants | アシスタント一覧の取得 |
| GET | /data/export | 全データのエクスポート |
| POST | /data/import | データのインポート |
| POST | /data/backup | バックアップの作成 |
| GET | /data/backups | バックアップ一覧 |
| POST | /data/backups/{id}/restore | バックアップからの復元 |

バックアップ作成時、`backup.retention_count`（既定5）を超える古いバックアップを作成日時の古い順に自動削除する（D-02）。

**システム情報・診断ログ（SC-15、Phase40で拡張）**

| メソッド | パス | 概要 |
| --- | --- | --- |
| GET | /system-info | アプリバージョン・Pythonバージョン・ビルド日時・使用ライブラリ一覧の取得 |
| GET | /system-info/logs/export | 期間（`date_from`・`date_to`、両端含む）を指定して診断ログをダウンロードする。応答は`text/plain`（JSONスキーマなし）。ローテーション世代（`michinari.log`〜`.{LOG_BACKUP_COUNT}`）を古い→新しい順に横断し、行頭タイムスタンプで期間内の行（スタックトレース等の継続行は直前の主行に従う）のみを抽出して結合する。`date_to < date_from`は`VALIDATION_ERROR`、該当ログが無い場合はエラーにせず空文字列を返す |
| POST | /client-logs | フロントエンドが捕捉した未処理エラー（描画中の例外・イベントハンドラ内の例外・未処理のPromise rejection）を診断ログへ記録する。`message`・`stack`・`component_stack`はそれぞれ4000文字まで。`message`は改行をエスケープしてから1行で記録し、偽の行を混入させるログインジェクションを防ぐ。入力値そのもの（学習記録の本文等）は送信対象に含めない設計とする |

診断ログ（`michinari.log`、%LOCALAPPDATA%\Michinari\data\logs\、1MB×4世代でローテーション）は、設定画面（SC-11）の「AI通信ログの保存」が扱う`ai_log`テーブル（AIとの通信内容、保持期間90日で自動削除）とは別物である。診断ログにはアクセスログ（method/path/status、相関ID付き）・業務エラー・フロントの未処理エラーを記録し、**利用者の入力値そのものは記録しない**（下記セキュリティ設計参照）。

各リクエストには相関ID（`X-Request-Id`ヘッダ、12桁の16進数）を発行し、同一リクエストで出力される全てのログ行（アクセスログ・業務エラー・未分類例外）へ自動的に付与する（`logging.setLogRecordFactory`によるプロセス全体への注入、ハンドラ単位の`logging.Filter`では`caplog`等の別ハンドラに乗らないため採用しない）。フロントはレスポンスの`X-Request-Id`ヘッダを`ApiError.requestId`として保持し、エラー表示の詳細欄に「エラーID」として表示する。

**その他**

| メソッド | パス | 概要 |
| --- | --- | --- |
| GET | /daily-message | 今日の一言の取得（目標ごとに配列で返す。未生成の目標があれば生成。未決事項L-04）。AI未設定時はAI呼び出しをスキップし、`is_fallback=true`・`body=""`の固定フォールバックを200で返す（DBには保存しない、S-4 4-1） |
| GET | /health | 稼働確認 |

### 6.3 エラーコード

| コード | HTTPステータス | 意味 |
| --- | --- | --- |
| VALIDATION_ERROR | 400 | 入力値の検証エラー |
| EXAM_SUBJECT_REQUIRED | 400 | 資格試験目標の開始に必要な試験科目が未登録（教材未登録・配分未設定と画面上で区別するため専用コードとする） |
| MATERIAL_REQUIRED | 400 | 資格試験目標の開始に必要な教材が未登録（同上） |
| RESOURCE_ALLOCATION_REQUIRED | 400 | 資格試験目標の開始・再開に必要なリソース配分が未設定（同上。読書は配分が任意のため対象外、R-64） |
| RESOURCE_EXCEEDED | 400 | あるスロットへの配分時間の合計が、そのスロットの連続時間を超過（仕様書NT-04） |
| CYCLE_CONFLICT | 400 | 予定周回数が完了済み周回を下回る |
| BOOK_ALREADY_EXISTS | 400 | 読書目標に対し2件目の書籍を登録しようとした（1目標1冊制約違反） |
| CURRENT_PAGE_EXCEEDS_TOTAL_PAGES | 400 | 想起記録の現在ページが書籍の総ページ数を超えている（進捗率が100%を超えないようにするための検証。1.1改20） |
| WORK_ASSIGNMENT_ALREADY_EXISTS | 400 | 仕事目標に対し2件目の案件情報を登録しようとした（1目標1案件制約違反） |
| CONSENT_REQUIRED | 400 | チームメンバーの特徴・性格を、本人確認済みの確認なしに保存しようとした（要件定義書R-94、2026-09-23） |
| IMMUTABLE_RECORD | 409 | 確定済み記録への更新 |
| INVALID_STATE_TRANSITION | 409 | 許可されない状態遷移 |
| EXAM_RESULTS_INCOMPLETE | 409 | 受験結果が揃っていない資格試験目標の完了要求（確認では解消しない。完了ボタンは結果が揃うまで無効化する。1.1改32。旧 CLOSE_CONFIRMATION_REQUIRED は確認要求の廃止に伴い置換） |
| DATABASE_BUSY | 503 | SQLiteの書き込みロック待ちタイムアウト（AI生成や起動時の自動処理と保存が重なった場合）。再試行で解消しうる（1.1改32） |
| BACKDATE_LIMIT_EXCEEDED | 400 | 遡及入力の期限超過 |
| NOT_FOUND | 404 | 対象が存在しない |
| AI_AUTH_REQUIRED | 401 | AI基盤の認証が必要 |
| AI_CONFIG_ERROR | 400 | AI連携の設定不備 |
| AI_TIMEOUT | 504 | AI応答のタイムアウト |
| AI_ERROR | 502 | AI基盤からのエラー応答 |
| INTERNAL_ERROR | 500 | 想定外のエラー（DomainError/RequestValidationError以外の未分類の例外もここへ集約する最終防波堤ハンドラを持つ。1.1改24） |
| DATABASE_BUSY | 503 | SQLiteの書き込みロック待ちタイムアウト（`database is locked`）。AI生成や起動時の自動処理と保存が重なった場合に返す。再試行で解消しうるため、画面は「1〜2分待ってから再試行」を案内する。ロック以外のDB例外はINTERNAL_ERRORのまま |

**`details`のreason（1.1改24、2026-09-23にWORK_MEMBER_HAS_REPORTSを追加）**: 実績・想起記録・業務記録・評価レポートが紐づく教材/書籍/案件情報/メンバーの削除拒否は、コードは`VALIDATION_ERROR`のまま増やさず、`details`に`{"reason": "..."}`を1件付与して原因を区別する（`MATERIAL_HAS_LOGS`／`BOOK_HAS_LOGS`／`WORK_ASSIGNMENT_HAS_LOGS`／`WORK_MEMBER_HAS_REPORTS`）。フロントは`ApiError.localizedMessage`（`frontend/src/api/client.ts`）がこの`reason`を優先的に文言化する（`locales/ja.json`の`errors.reasons.*`）。

### 6.4 セキュリティ設計（診断ログ出力・トレース強化、Phase40）

**信頼境界**：本アプリはシングルユーザーのローカル常駐デスクトップアプリであり、`127.0.0.1`のみで待受け、既存エンドポイント全てが無認証（6.1「認証: なし」）。`POST /client-logs`は「フロントエンド（同一マシン上のブラウザ）→バックエンド」という既存の信頼境界内の入力であり、リモート攻撃者からの直接到達は想定しない。

**脅威と対策（STRIDE）**

| 脅威 | カテゴリ | 対策 | 実装箇所 |
| --- | --- | --- | --- |
| 巨大な`message`/`stack`を送りつけログファイルを肥大化させる | D（サービス妨害） | `Field(max_length=4000)`で上限を設け、超過は既存の`RequestValidationError`ハンドラで自動400 | `backend/app/schemas/client_logs.py` |
| `message`に改行を混入させ偽のログ行（別レベル・別時刻に見える行）を挿入する（ログインジェクション） | T（改ざん） | 単一行として扱う`message`は改行を`\n`表記へエスケープしてから記録。多行が前提の`stack`/`component_stack`は明示的な区切りの下に記録する | `backend/app/api/client_logs.py` |
| 検証エラーの`details`（pydanticの`errors()`が持つ`input`キー）をそのままログすると利用者の入力値が漏洩する | I（情報漏洩） | `loc`/`type`のみを抽出してログし、`input`は使わない | `backend/app/api/errors.py` |
| ログエクスポートAPIに不正な日付範囲（`date_to < date_from`）を渡す | T（改ざん） | `ValidationError`で400。範囲の上限は設けない（同一マシン内のローカルファイルで最大でも1MB×4世代のため） | `backend/app/services/system_log_export_service.py` |
| ログファイル自体に将来的に機微情報が混入する | I（情報漏洩） | 「ログには入力値を書かない」ことをコード上のコメントで明記し、レビュー時の指針とする（完全な自動検知は困難なため、コードレビュー運用で担保するAccept判断） | 全変更箇所のコメント |
| なりすまし・権限昇格 | S/E | 該当なし（既存エンドポイント同様、ローカル単一ユーザーのため認可境界が存在しない。アプリ全体の設計方針を踏襲するAccept判断） | - |

---

