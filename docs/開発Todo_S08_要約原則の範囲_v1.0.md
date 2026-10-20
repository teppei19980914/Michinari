# 開発Todo：S08 要約原則の対象範囲の確定と対応（G5・G8・G9）

本書は、要件定義書R-35「過去の報告内容は週次要約として保持し、対話時の入力に用いること。全期間の原文を入力に含めないこと」が、どのプロンプトにどこまで適用されるかを確定し、未適用部分（G5）を実装する作業の正（Single Source of Truth）である。版番号（`pyproject.toml`、現在2.1.0）は変更しない。作業は`dev/2026-10-19`で行う。

## 0. 決定事項（2026-10-19 時点で確定）

| # | 決定 | 値 |
| --- | --- | --- |
| G5-範囲 | 過去日のAIとの対話（`chat_message`）を週次要約の材料に含めるか | **含める。利用者の発言（`role=USER`）のみ**。AIの応答（`role=ASSISTANT`）は対象外（AIが自身の過去の発言を再入力される自己参照を避け、プロンプト増量も抑える。週次要約の既存の狙い「学習者が用いた表現や説明の粒度を保存する」と一致するのは利用者本人の発言） |
| G5-再生成 | 既に生成済みの週次要約を作り直すか | **作り直さない**。新しい原則は今後生成される週からのみ適用する（既存データへの遡及AI呼び出しをしない） |
| G8-範囲 | 今日の一言（`daily_message_service`）を要約経由の原則の対象にするか | **対象外**。設計書・要件定義書に明記する（1〜2文の短文生成が目的で、R-36自体がR-35と異なる要求のため）。実装変更なし |
| G9-位置づけ | テーマ別振り返り（`recap_generation_service`）の分割統合方式を、原則の「要約機能」と同等の圧縮として認めるか | **認める**。設計書に明記する。実装変更なし |

## 1. 影響範囲（フルスキャンの結果）

### 1.1 現状の棚卸し（3項目共通の前提）

要件定義書R-35を実装する既存の仕組みは次の2段階（`ai_context_common.py`）。

1. `resolve_weekly_compressed_period`：`[period_start, period_end]`内で既に生成済みの週次要約を圧縮表現として収集
2. `exclude_covered_dates`：生ログ側から同じ日付を除外（二重注入回避）

この仕組みは次の6用途に適用済み：資格・読書・仕事の日次報告フィードバック（17.2・17.6・17.8）、総括レポート・読了レポート・月次報告・半期評価・AI評価レポート（17.5・17.7・17.9・17.10・17.13）。週次要約（`weekly_summary_service.py`、17.3・17.11・17.12）自体は、資格=実績＋日記＋集計、読書=想起記録、仕事=業務記録のみを材料とし、`chat_message`（AIとの対話）は一度も材料に入っていない。

### 1.2 G5（週次要約への対話の追加）：変更内容

| 項目 | 現状 | 変更内容 |
| --- | --- | --- |
| バックエンド・新規関数 | なし | `ai_context_common.py`に`build_week_user_chat_text(session, goal, purpose, week_start, week_end)`を追加（資格・読書・仕事で共通。`ChatMessage`を`role=ChatRole.USER`・`purpose`・`goal_id`・週の日付範囲で絞り込み、日付ごとに整形）。既存の`_fetch_study_log_rows`等と同じ「共通クエリをservices層に集約」方針（CODING_RULES DRYの原則） |
| `weekly_summary_service.py` | `_CategorySpec`に対話用の情報なし | `_CategorySpec`へ`daily_feedback_purpose: AiPurpose`を追加（資格=`DAILY_FEEDBACK`、読書=`DAILY_FEEDBACK_READING`、仕事=`DAILY_FEEDBACK_WORK`）。`generate_for_week`の変数組み立てに`"week_chat": ai_context_common.build_week_user_chat_text(...)`を追加（3カテゴリ共通処理のため、各`_xxx_week_variables`ではなく`generate_for_week`側に1箇所で実装し重複を避ける） |
| `app/models/record.py` | — | 変更なし（既存`ChatMessage`テーブルをそのまま利用。新規列・新規テーブル不要） |
| `app/init/prompt_texts_exam.py`（`WEEKLY_SUMMARY`）、`prompt_texts_reading.py`（`WEEKLY_SUMMARY_READING`）、`prompt_texts_work.py`（`WEEKLY_SUMMARY_WORK`） | `{{week_chat}}`を持たない3文面 | 各文面に「# 本人の発言（AIとの対話）」セクション（`{{week_chat}}`）を追加。「要約の要件」の該当箇所（学習者/読者の表現・説明の粒度を保存する項目）へ「対話中の発言も対象とする」旨を追記（文面は§7に確定版を記載） |
| `backend/alembic/versions/` | head=`0ad4f28cd909` | 新規マイグレーション1件（`update`のみ、`create_table`なし）。`prompt_template`の`WEEKLY_SUMMARY`・`WEEKLY_SUMMARY_READING`・`WEEKLY_SUMMARY_WORK`を、`is_customized=False`の行のみ新文面へ更新（`0ad4f28cd909`と同じ方式。利用者が編集済みのテンプレートは上書きしない） |
| テスト | — | `test_ai_context_common.py`（新規関数）、`test_weekly_summary_service.py`（`generate_for_week`の変数に`week_chat`を追加）、`test_migration_prompt.py`（新規マイグレーションの`updates_non_customized`/`preserves_customized`を3purpose分、既存の`parametrize`パターンに追従） |

**影響（文字数・既存データ・AI呼び出し回数・起動時間）**

- 文字数：週次要約生成1回あたりのプロンプトに、その週・その目標の利用者発言分（通常は0〜数百字、対話が多い週でも千字程度）が追加される。既存の`ai.max_prompt_chars`（30,000字）に対しては小さい増分。週次要約自体は圧縮後の出力（本文のみ）なので、以降の日次フィードバック等への影響は要約の質に委ねられる
- 既存データ：ChatMessageは資格・読書・仕事とも既に蓄積済み（Phase26でgoal_id付与済み）。goal_id=NULLのレガシー行は対象外（既存の`list_active_exam_goals`等と同じ「帰属不明は対象外」方針を踏襲）
- AI呼び出し回数：**増加しない**（既存の週次要約生成バッチ呼び出しに変数を1つ追加するのみ。再生成しない決定のため遡及呼び出しもない）
- 起動時間：**変化しない**（`build_week_user_chat_text`のクエリは週次要約生成時にのみ実行され、件数は週・目標単位で小さい）

### 1.3 G8（今日の一言）：対象外の根拠整理（実装変更なし）

- `daily_message_service.py`は`{{recent_activity}}`（直近7日固定の生ログ）のみを使い、`{{weekly_summaries}}`変数を持たない。要件定義書R-36は「進捗状況を踏まえた肯定的な短文」「同日中は再生成しない」が要求であり、R-35の「全期間を漏れなく入力する」要求とは独立している
- 対象に含めた場合の変更内容（採用しない案の記録）：`_CategorySpec`相当の仕組みを`daily_message_service`にも作り、`resolve_weekly_compressed_period`を呼ぶ必要がある。1〜2文の短文生成のために全期間分の週次要約を読み込むのは不釣り合い（文字数・読み込みコストに対して出力の価値が低い）
- 影響：採用しないため文字数・AI呼び出し回数・起動時間への影響はゼロ。ドキュメント（17.4）に対象外の理由を明記するのみ

### 1.4 G9（テーマ別振り返り）：位置づけ整理（実装変更なし）

- `recap_generation_service.py`は「分類（`RECAP_CLASSIFY`）→テーマ本文への統合（`RECAP_THEME_BODY`）」という独自方式を持つ。情報を失わないことを`RECAP_MIN_RETENTION_RATIO`（既定0.8、応答が既存本文の80%未満なら不採用・再処理）で保証しており、週次要約方式（「要約済みの週は要約、要約が無い日は生ログ」）とは異なる手段で同じ目的（原文を全期間入力に含めず、かつ情報を失わない）を達成している
- 対象に含めた場合の変更内容（採用しない案の記録）：recapを週次要約ベースの縮退方式へ置き換えると、「テーマ単位で体系的に整理する」という目的（週次要約は目標単位・週単位の時系列整理で、テーマ単位の整理には使えない）に合わなくなる。実装コスト・回帰リスクが最も大きい案のため不採用
- 影響：採用しないため文字数・AI呼び出し回数・起動時間への影響はゼロ。設計書（17.14）・要件定義書（R-35背景）に「認める」旨を明記するのみ

### 1.5 ドキュメントへの反映

| 文書 | 変更 |
| --- | --- |
| `docs/要件定義書_ミチナリ_v1.1.md` | 「要求の背景」節（R-35）に、chat_messageの扱い（利用者発言のみ、再生成なし）・今日の一言の対象外・recapの位置づけを1段落で追記。改訂履歴に新しい番号（直前の最大値の次）を追記 |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1/17_プロンプト設計/17.3_週次要約.md` | `{{week_chat}}`の変数行・初期文面を更新 |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1/17_プロンプト設計/17.11_読書用週次要約.md` | 同上（読書版） |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1/17_プロンプト設計/17.12_仕事用週次要約.md` | 同上（仕事版） |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1/17_プロンプト設計/17.4_今日の一言.md` | 末尾に「対象外とする」旨と根拠を1文追記 |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1/17_プロンプト設計/17.14_振り返りテーマ累積.md` | 末尾に「同等の圧縮として認める」旨と根拠を1文追記 |
| `docs/設計書_データ構造編_ミチナリ_v1.1/05_テーブル定義/5.4_記録系.md` | `chat_message`の用途説明に「週次要約生成時の材料としても参照される（role=USER、G5）」を追記（テーブル構造自体は変更なし。当初Todoは5.5と記載していたが、`chat_message`の実際の定義は5.4にあったため修正） |
| 要件定義書の改訂履歴 | 新しい番号（1.1（改44））を追記。設計書ロジック・プロンプト編・データ構造編は分割後（S03）「改訂履歴」表を持たず、各文書の24章・9章の未決事項ログ（L-XX／D-XX）が実質的な変更履歴を兼ねるため、そちらへ追記する（当初Todoは「各文書に改訂履歴番号を追記」としていたが、実際の文書構成を確認して訂正。仕様書（S-XX）は本改修で画面・設定項目の変更が無いため追記不要） |

### 1.6 既存機能への横展開（同じ問題の有無を確認）

| 項目 | 状況 | 対応 |
| --- | --- | --- |
| 日次報告フィードバック・総括レポート系（6用途） | 既にR-35の仕組みが適用済み | 変更不要（横展開済みであることを確認） |
| 今日の一言・テーマ別振り返り | 未適用（本Todoで扱うG8・G9） | 対象外／同等として明記（上記） |
| `ai_log`・`chat_message`のGDPR/個人情報的配慮 | 既存の匿名化版生成（`anonymize=True`）は`{{anonymize}}`指示で個人特定情報の言及を避けるようAIへ指示する設計（出力側の配慮） | `{{week_chat}}`も匿名化版生成時は同じ`{{anonymize}}`指示の対象範囲内（本文中の事情を一般化する指示は対話内容にも及ぶため、個別の追加対応は不要。確認のみ） |

## 2. ベースライン（2026-10-19、開発前）

- バックエンド：`ruff check .` 合格。`pytest`（`backend`）1,886件合格、カバレッジ100%（8,229文・1,548分岐）、2 warnings（本件と無関係）
- フロントエンド：`npm run lint`（oxlint）0件。`npx tsc -b` 0件。`npm run test`（vitest）155ファイル・1,318件合格、カバレッジ100%（文1,825・分岐1,249・関数864・行1,755）

## 3. 作業Todo

凡例：`[ ]` 未着手、`[x]` 完了。各項目の完了条件は「テストが通ること」と「カバレッジ100%（例外処理を除く）」。

### 3.1 文書改訂（フェーズAの決定を反映）

- [x] D-01 要件定義書：「要求の背景」節にR-35の対応状況（G5・G8・G9）を追記。改訂履歴に1.1（改44）を追記
- [x] D-02 設計書（ロジック・プロンプト編）17.3・17.11・17.12：`{{week_chat}}`変数行・初期文面を更新
- [x] D-03 設計書（ロジック・プロンプト編）17.4：今日の一言を対象外とする根拠を追記
- [x] D-04 設計書（ロジック・プロンプト編）17.14：テーマ別振り返りを同等の圧縮として認める根拠を追記
- [x] D-05 設計書（データ構造編）5.4：`chat_message`の用途説明にG5の参照を追記（当初Todoの5.5から訂正）
- [x] D-06 設計書（ロジック・プロンプト編）24章未決事項にL-16を追加（分割後の文書には「改訂履歴」表が無く、未決事項ログが変更履歴を兼ねるため。当初Todoの想定を訂正）

### 3.2 バックエンド実装（G5のみ）

- [x] B-01 `ai_context_common.py`：`build_week_user_chat_text(session, goal, purpose, week_start, week_end)`を追加（`ChatMessage`を`role=USER`・`purpose`・`goal_id`・週の日付範囲で絞り込み、日付ごとに整形。0件時は「（この週の対話はありません）」）
- [x] B-02 `weekly_summary_service.py`：`_CategorySpec`へ`daily_feedback_purpose`を追加し、`_EXAM_SPEC`/`_READING_SPEC`/`_WORK_SPEC`へ値を設定（`AiPurpose.DAILY_FEEDBACK`/`DAILY_FEEDBACK_READING`/`DAILY_FEEDBACK_WORK`）
- [x] B-03 `weekly_summary_service.generate_for_week`：変数組み立てに`"week_chat"`を追加（3カテゴリ共通処理として1箇所に実装）
- [x] B-04 `prompt_texts_exam.py`・`prompt_texts_reading.py`・`prompt_texts_work.py`：`WEEKLY_SUMMARY`・`WEEKLY_SUMMARY_READING`・`WEEKLY_SUMMARY_WORK`の初期文面を更新（§7の確定文面を一字一句転記）
- [x] B-05 Alembicマイグレーション新規作成（リビジョン`9d3d5631a940`、`down_revision="0ad4f28cd909"`）：3purposeの`prompt_template.body`を、`is_customized=False`の行のみ新文面へ更新。`downgrade`で旧文面へ戻す（スクラッチDBで upgrade/downgrade 双方を実機検証済み）

## 4. テスト計画

対象はG5のみ（G8・G9は実装変更なしのため対象外）。新規追加するコード（§3.2のB-01〜B-05）に対し、既存方針（CODING_RULES.mdテストカバレッジ、例外処理を除き100%）を維持する。既存の`parametrize`パターン（3purpose：資格・読書・仕事）に揃えて網羅する。

### 4.1 追加するテスト

- [x] T-01 `test_ai_context_common.py`：`build_week_user_chat_text`（0件、単日複数発言、複数日、他goal_idの除外、他purposeの除外、`role=ASSISTANT`の除外、週範囲外の除外）
- [x] T-02 `test_weekly_summary_service.py`：`generate_for_week`が組み立てる変数に`week_chat`が含まれること（資格・読書・仕事3カテゴリ、AIの応答は含まれないこと、対話が無い週は固定文言になること）
- [x] T-03 `test_migration_prompt.py`：新規マイグレーションの`test_week_chat_prompt_migration_updates_non_customized_template`／`test_week_chat_prompt_migration_preserves_customized_template`を3purpose分（既存の`@pytest.mark.parametrize`パターンに追従）
- [x] T-04 既存DBからのアップグレード確認（スクラッチDBにgoal・daily_record・chat_message・weekly_summaryの既存データを投入→マイグレーション適用→件数・内容が変化しないことを確認。実環境のユーザーDBはこのセッションから参照できないため、同等の既存データを再現したスクラッチDBで検証）

### 4.2 検証手順

- [x] V-01 `ruff check .`（全体合格）・`pytest`（backend、1,903件合格、カバレッジ100%（8,237文・1,552分岐）。初回実行で`test_initial_prompt_templates_content_is_unchanged_by_the_file_split`が意図通り失敗したため、意図した変更であることを確認のうえハッシュ値を更新し、再実行で全件合格）
- [x] V-02 既存DBのコピーへのマイグレーション適用確認（T-04と同一の検証で実施。goal/daily_record/chat_message/weekly_summaryの件数・内容が不変であることを確認）
- [ ] V-03 実機確認（任意）：資格・読書・仕事いずれか1目標で、日次報告フィードバックで対話（ユーザー発言）を送信→起動時バッチで週次要約を生成→生成結果に対話内容が反映されていることを確認（AI接続が必要なため未実施。任意項目のため完了の定義には含めない）

## 5. 未決事項

- なし（G5・G8・G9はいずれも§0で確定済み）

## 6. 別件（本Todoの範囲外として記録）

- NewtonX利用ナレッジ§6・§8.9.1に関連する「GPT-4o mini」「GPT-4o」の使用可否未確認は、本改修と無関係のため対応しない（既存メモリ`prompt_degradation_weekly_summary`参照）
- 日英i18n対応（`ai_context_exam.py`の列挙型ラベル以外の自由文言）は既知の制限として別件管理（既存メモリ`i18n_en_support_investigation`参照）。本Todoの新規文言（`{{week_chat}}`セクション見出し等）は日本語のみのプロンプト内固定文のため対象外（既存の`{{week_logs}}`等の見出しと同じ扱い）

## 7. 付録：確定文面（G5、転記元）

### 7.1 資格試験（`WEEKLY_SUMMARY`）

`# 日々の記録\n{{week_diaries}}`の直後に以下を追加する。

```
# 本人の発言（AIとの対話）
{{week_chat}}
```

「要約の要件」の2番目の項目を以下へ改める。

```
2. この週に学習した主題と、その理解度に関する記述
   （後日の比較対象となるため、学習者が用いた表現や
     説明の粒度を保存してください。日記に加え、
     AIとの対話中の発言も対象とします）
```

### 7.2 読書（`WEEKLY_SUMMARY_READING`）

`# 想起記録\n{{week_recalls}}`の直後に以下を追加する。

```
# 本人の発言（AIとの対話）
{{week_chat}}
```

「要約の要件」の2番目の項目を以下へ改める。

```
2. 感じたこと・考えたこと（読者が用いた表現や
   説明の粒度を保存してください。想起記録に加え、
   AIとの対話中の発言も対象とします）
```

### 7.3 仕事（`WEEKLY_SUMMARY_WORK`）

`# 業務記録\n{{week_logs}}`の直後に以下を追加する。

```
# 本人の発言（AIとの対話）
{{week_chat}}
```

「要約の要件」の2番目の項目を以下へ改める。

```
2. 工夫や粘り強さが記述されている場合はその内容
   （成果の評価ではなく、プロセスの記録として。
     業務記録に加え、AIとの対話中の発言も対象とします）
```

## 8. 作業記録

- 2026-10-20 フェーズB実施結果
  - 文書改訂（§3.1）：D-01〜D-06すべて完了。実施中に2点の訂正が判明した。(a) `chat_message`の表定義は設計書データ構造編5.5ではなく5.4にあった（当初Todoの誤記）。(b) 設計書ロジック・プロンプト編・データ構造編は文書分割（S03、2026-10-15）以降「改訂履歴」表を持たず、各文書の未決事項ログ（ロジック・プロンプト編24章のL-XX、データ構造編9章のD-XX）が実質的な変更履歴を兼ねる構成になっていた（要件定義書のみ「改訂履歴」表を保持）。両方を本文書・各文書へ反映済み（要件定義書1.1（改44）、ロジック・プロンプト編L-16）。仕様書は画面・設定項目の変更が無いため追記不要と判断。
  - バックエンド実装（§3.2）：B-01〜B-05すべて完了。マイグレーション（リビジョン`9d3d5631a940`）はスクラッチSQLiteで upgrade/downgrade 双方を実機検証し、is_customized=Falseの行のみ更新・Trueの行は保護されることを確認。既存のgoal・daily_record・chat_message・weekly_summaryデータを模したスクラッチDBでも、本マイグレーション適用前後でこれらのテーブルの件数・内容が一切変化しないことを確認（T-04・V-02）。
  - テスト（§4.1）：T-01〜T-04すべて完了。新規テスト17件（`test_ai_context_common.py`7件、`test_weekly_summary_service.py`4件、`test_migration_prompt.py`6件）を追加。
  - 検証（§4.2）：V-01・V-02完了。バックエンド全体 `ruff check .` 合格、`pytest` 1,903件合格（開発前ベースライン1,886件+17件、新規テスト数と一致）、カバレッジ100%（8,237文・1,552分岐）。初回実行時、既存のドリフト検知テスト`test_initial_prompt_templates_content_is_unchanged_by_the_file_split`（`test_seed_data.py`）が意図通り失敗（同テストは「意図した文面変更のたびにハッシュ値を更新する」設計）。本件がG5による意図した文面変更であることを確認したうえでハッシュ値を更新し、再実行で全件合格となった。フロントエンドは本フェーズで変更なし（開発前ベースラインをそのまま維持）。V-03（実機確認）はAI接続が必要なため未実施（任意項目）。
  - 横展開チェック：既存のR-35適用済み6用途（日次フィードバック3種・総括レポート系5種）には影響がないことを確認（これらは`{{weekly_summaries}}`・`{{recent_logs}}`等、別の変数名・別の仕組みを使用しており、週次要約自体の変数追加とは独立）。`_CategorySpec`を直接構築している箇所が他に無いこと（`grep`で確認、3件とも`weekly_summary_service.py`内のみ）、`ai_context_helpers.py`への新規テストヘルパー追加が既存の`test_analytics_service.py`内の同種プライベートヘルパーと機能重複する点を認識した上で、テスト対象ドメインが異なるため統合は本Todoの範囲外と判断（別件化はしない軽微な重複として記録のみ）。
  - 完了の定義（§3〜4）を満たした。G8・G9は実装変更なしのまま文書反映のみで完了。
