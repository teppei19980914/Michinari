# 開発Todo：道のりマップ（v2.4.0 対象）

本書は、目標ごとの進捗を「スタート→現在地→ゴール」の図（資格=山、読書=地図上の道、仕事=足跡の積み上げ）として可視化する「道のりマップ」機能の開発作業の正（Single Source of Truth）である。
規模はマイナーバージョンアップ（2.3.1 → 2.4.0）に相当する。作業は現行ブランチ `dev/2026-10-29` で行う。

## 0. 決定事項（2026-10-29 時点で確定）

| # | 決定 | 値・理由 |
| --- | --- | --- |
| U1 | 詳細版の配置場所 | `GoalDetailPage` に新規タブ「道のり」を追加（`basicInfo` の次、全種別共通）。理由：`AnalyticsPage` は `selectableAnalyticsGoals.ts` でDRAFT状態の目標を一覧から除外する設計のため、要件「下書き…のそれぞれで表示に矛盾が出ないように」と矛盾する。`GoalDetailPage` は `isReadOnly = isClosedGoalStatus(goal.status)` のみで分岐し、DRAFT〜CLOSED全状態を表示できる |
| U2 | 縮小版の配置 | ダッシュボードの目標カード一覧（`GoalCardList` 系）に追加。単独コンポーネント `GoalRoadmapMini` として実装し、ふりかえりまとめ・社内共有カードでも再利用できるようにする（読み取り専用、クリックで詳細タブへ遷移） |
| U3 | CLOSED目標の遷移経路 | 目標一覧からCLOSED目標を選ぶと現状 `resolveGoalListTarget` により `ROUTES.goalExport`（SC-13 ナレッジエクスポート）へ遷移し `GoalDetailPage` へは行かない。**実装時訂正（2026-10-30）**：ダッシュボードの目標カードは元々 `resolveGoalListTarget` を経由せず常に `ROUTES.goalDetail`（プレーンな `Link`）へ遷移する実装だったため、CLOSED後も道のりを閲覧できる目的はこの既存経路で既に満たされていた。タブへの深いリンク（URL直接指定で`roadmap`タブを開く）は、既存の`WorkGoalCard`のコメントに明記された「URLベースのタブ深いリンクは現状の実装方針に無いため導入しない」という既存方針に合わせ、本機能でも導入しない（他タブへの導線と一貫させる）。GoalDetailPageを開いた後、利用者が「道のり」タブを選ぶ |
| U4 | 資格：山頂の日付 | 要件文言どおり「全科目の受験を終える日」＝ 目標に紐づく全科目の `effective_exam_date` の最大値（最も遅い日）を新規算出する。既存の `dashboard.py` `_goal_remaining_days`（最も近い受験日を使う別目的の関数）とは流用せず、新規関数とする |
| U5 | 資格：2周目・3周目の扱い | 標高＝全周回を通した進捗率。既存 `cycle_service`（`total_work = total_amount × planned_cycles`）をそのまま使う。周回ごとの区切り線等の追加表現は本件のスコープ外とし、§7（既知のリスクと対策）に将来課題として残す |
| U6 | 資格：複数教材の計画線集約 | 教材ごとの `analytics_service.compute_plan_line` の結果を日次で単純平均し、目標単位の1本の計画線に合成する新規ロジックを追加する |
| U7 | 読書・仕事：進捗状態アイコン（UI-02〜04） | **新設しない**（利用者回答、2026-10-29）。既存仕様書（v1.1 13.4）が「完了予測・スケジュール状態の表示は資格試験目標にのみ行い、読書・仕事目標には表示しない」と明記しているため、この既定方針を維持する。読書・仕事の現在地アイコンは常にUI-01（normal）とし、計画との差は図中の線のズレ自体（計画線と実際の歩みの間隔）で表現する。達成時のみUI-11 |
| U8 | 予備日アイコン（UI-07） | 資格のみ。バッファ日（`day_type`）の概念は資格専用（`calendar_service`、`metrics_service.compute_buffer_usage_rate` も資格以外は `None` を返す）。読書・仕事には予備日アイコンを表示しない |
| U9 | 仕事：道の起点・終点 | 起点＝現評価期間の開始日、終点＝評価期間の終了日。`work_report_service.default_semiannual_period_key` / `_semiannual_period_range`（private）を公開関数として切り出し利用する。`goal.start_date` や `work_assignment.start_date` は使わない |
| U10 | 読書・仕事：道の引き直し目印 | **表示しない**（利用者回答、2026-10-29）。計画基準値（`PlanBaseline`）という概念自体が読書・仕事には設計上存在しない（データ構造編5.3）。新しい値をDBに保存しない方針の下で代替データも作らない。読書・仕事は「実際の歩み（足跡）の積み上がり自体がまっすぐ向かう強みの可視化になる」とし、計画線と実績線を重ねる表現（要件2の前段）のみ行う |
| U11 | 英語ロケール | **実装時訂正（2026-10-30）**：当初は`ja.json`のみに追加する決定だったが、実装時に確認した結果、`en.json`の`help`名前空間は既存の全セクションで`ja.json`と同じキー数（214キー）を持ち、既に完全に英訳済みだった（本決定の前提にした「英語対応は別件・未実装」はヘルプ本文には当てはまらず、誤りだった）。また`localeKeyUsage.test.ts`が本番コード中の全`t('...')`呼び出しをja/en両方で解決可能であることを機械的に検証するため、タブラベル・ツールチップ等のUI文言キーは構造的にも両方必須。横展開の方針（既存の全機能が両言語で揃っている実態に合わせる）に従い、本機能のタブラベル・ツールチップ・要約文言・ヘルプ本文（`help.sections.goals.roadmap`）を`en.json`にも追加した |
| U12 | 新規API | 算出済みの「正規化された点列・マイルストーン」をJSONで返すエンドポイントを追加する。SVG座標への変換はフロント側（`roadmapGeometry.ts`）で行い、座標計算ロジックの重複を避ける |
| U13 | バージョン | 2.4.0。`pyproject.toml` の版更新は**リリース手順（`release.bat`）で入力する**（開発中は変更しない） |
| U14 | フェーズ | 新フェーズ Phase 47（直前の最終フェーズはPhase 46・リマインド導線、2026-10-28マージ済み） |
| U15 | APIの分割 | ダッシュボードの縮小版は既存 `GET /dashboard` の `GoalCardRead` に軽量フィールド（`roadmap_progress_ratio`／`roadmap_is_achieved`／`roadmap_overrun_days`。EXAM以外は`roadmap_overrun_days=null`）を追加するのみとし、線データ・目印データは返さない。詳細版は目標詳細タブを開いたときに新規 `GET /goals/{id}/roadmap` を呼び、計画線・実績線・足跡・道標・リプラン目印を返す。これにより新規データ取得をダッシュボード初期表示（2秒要件）から分離する |
| U16（実装時追記、2026-10-29） | スケジュール状態フィールドの重複排除 | バックエンドは `scheduleStatus`（delayed/onTrack/ahead）を返さず、`overrun_days`（float\|None）のみ返す。遅れ/予定どおり/先行の判定は既存のフロント側 `scheduleStatus.ts` の `resolveScheduleStatus(overrunDays)` が既に持つため、同じロジックをバックエンドにも複製するとDRY違反になる（CLAUDE.md①）。S-02のレスポンス構造から`scheduleStatus`フィールドを削除し、`overrunDays`のみとする |
| U17（実装時追記、2026-10-29） | 仕事目標の計画線・実績線 | WORKには「進捗量」の概念がなく（U7の既定方針どおり遅れ/先行の判定も無い）、計画線と比較すべきペースの指標が存在しない。`plannedPoints`／`actualPoints`は常に空配列とし、`progress_ratio`は「現評価期間に対する経過日数の割合」（`(today - start_date) / (goal_date - start_date)`、0〜1にクランプ）を返す。道（時間軸）の上に現在地（経過日数割合の位置）と足跡（記録した日）を置くのみの表現とする |
| U18（実装時追記、2026-10-30） | `RoadmapDiagramInput`型の不整合 | フロント実装（フォーク作業）が中断された状態を引き継いだ際、`RoadmapDiagram.tsx`が`roadmap.overrun_days`を参照しているのに型`RoadmapDiagramInput`（`RoadmapLayoutInput & {category, is_achieved}`）に`overrun_days`が無く、`tsc -b`が8件のエラーで失敗していることを検証中に発見した。`overrun_days: number \| null`を型へ追加し、連動して`GoalCardList.tsx`（`roadmap_progress_ratio`/`roadmap_overrun_days`が`GoalCardRead`では任意フィールドのため`undefined`を取り得る点に`?? null`で対応）と`statsVisibility.test.ts`（新規必須フィールド`roadmap_is_achieved`をフィクスチャに追加）を修正して解消した |
| U19（実装時追記、2026-10-30） | `GoalRoadmapTab.tsx`の未実装 | フロント実装フォークが中断された時点で、描画エンジン`RoadmapDiagram.tsx`・縮小版`GoalRoadmapMini.tsx`は完成していたが、詳細版をGoalDetailPageに表示するF-03（`GoalRoadmapTab.tsx`とタブ配列への組込み）が未着手だった。既存の`ReplanHistoryTab.tsx`と同じuseQuery＋読み込み中／エラー表示の構成で新規作成し、`EXAM_TABS`／`READING_TABS`／`WORK_TABS`（`basicInfo`の次）とタブ本体の描画分岐へ追加した |

## 1. 影響範囲（フルスキャンの結果）

### 1.1 バックエンド

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| 新規サービス | `app/services/roadmap_service.py`（想定） | 3種別の道のり算出を集約。既存の `cycle_service`・`metrics_service`・`analytics_service.compute_plan_line`・`baseline_service`（EXAMのみ）・`book_service.get_book_progress`・`work_report_service` を呼び出す形で構築 |
| 既存サービスの公開化 | `app/services/work_report_service.py` の `default_semiannual_period_key` / `_semiannual_period_range` | `_` を外し公開関数化（既存の呼び出し元の挙動は変えない） |
| 新規関数 | 資格の山頂日付（全科目中の最も遅い `effective_exam_date`）、複数教材の計画線合成 | `roadmap_service.py` 内に新規実装（既存の `_goal_remaining_days` とは別） |
| 道標（AIフィードバック日） | `chat_message`（`goal_id`・`purpose`・`role`、`daily_record_id` 経由で `record_date` に紐づく） | 既存テーブルを集計で利用。新規保存はしない |
| 新規API | `app/api/`（既存 `dashboard.py` への縮小版用フィールド追加、または新規 `roadmap.py` の詳細版エンドポイント） | 追加。サービス層はドメイン例外、API層で変換（CLAUDE.md） |
| 新規スキーマ | `app/schemas/`（新規 `roadmap.py` または既存スキーマへの追加） | 正規化された点列・マイルストーンのレスポンス型 |
| テスト | `backend/tests/`（新規 `roadmap_service` の単体テスト、API結合テスト。境界：記録0件、ゴール当日、ゴール超過、進捗100%） | 追加 |

### 1.2 フロントエンド

| 領域 | 対象 | 変更の種類 |
| --- | --- | --- |
| 単独コンポーネント | `src/features/goal/GoalRoadmapMini.tsx`（新規） | ダッシュボード用縮小版。読み取り専用、クリックで詳細タブへ遷移 |
| 詳細コンポーネント | `src/features/goal/GoalRoadmapTab.tsx`（新規） | `GoalDetailPage` の新規タブ本体 |
| ジオメトリ計算 | `src/features/goal/roadmapGeometry.ts`（新規、純粋関数＋テスト） | 既存の `features/analytics/ganttGeometry.ts` と同じ「純粋関数でレイアウト計算→テストで検証→コンポーネントで描画」パターンに揃える |
| ページ | `src/pages/GoalDetailPage.tsx` | `EXAM_TABS`／`READING_TABS`／`WORK_TABS`（34〜128行目）各配列に `roadmap` タブを追加し、タブ本体の描画分岐（367行目以降）に追記 |
| ダッシュボード | `src/features/dashboard/` の目標カード一覧コンポーネント | `GoalRoadmapMini` を組込み |
| API層 | `src/api/`（新規または既存への追加）、`src/types/api.d.ts` | バックエンドの新規エンドポイントに対応。型は `npm run generate:api-types` で再生成（手書き禁止、CLAUDE.md） |
| 配色 | `src/features/analytics/chartColors.ts` | 既存の `resolvePlanLineColor()`／`resolveGridLineColor()`／`resolveAxisLineColor()`／`cycleSeriesColor()` をそのまま再利用（新規関数追加は最小限に留める） |
| アイコン | `src/constants/characterIcons.ts` | 既存の `CHARACTER_ICONS`（UI-01/02-04/07/11）をそのまま参照。新規画像素材は作らない |
| 文言 | `src/locales/ja.json` | `help` 名前空間に図の見方の説明を追加。図内の要約文言（例：「全体の62%、予定より3日遅れ」）用のキーを追加 |
| テスト | 上記各ファイルの `.test.tsx`／`.test.ts`（アクセシビリティ：`role="img"`・`aria-label`、`prefers-reduced-motion` 分岐、各種別・各状態の描画） | 追加 |

### 1.3 ドキュメント

| 文書 | 変更 |
| --- | --- |
| `docs/要件定義書_ミチナリ_v1.1.md` | 新設要件（R-番号は着手時に採番）、改訂履歴 |
| `docs/仕様書_ミチナリ_v1.1.md` | 機能一覧表、`GoalDetailPage` のタブ構成（6.2節）、ダッシュボード画面仕様、改訂履歴。13.4節に「道のりマップの現在地アイコンは本節の既定方針に従い資格のみ」等の参照を追記 |
| `docs/設計書_ロジック・プロンプト編_ミチナリ_v1.1.md` | 3種別の道のり算出ロジック、山頂日付・計画線合成・評価期間の起点終点の算出式、改訂履歴 |
| `docs/設計書_データ構造編_ミチナリ_v1.1.md` | 新規APIレスポンス構造（DBスキーマ変更なしのため新規テーブルは無し）、改訂履歴 |
| `docs/実装フェーズ分割計画書_ミチナリ_v1.1.md` | Phase 47 の追加 |
| `docs/OPERATIONS.md` | 本機能に関する運用上の注意点（変更があれば追記。新規ツール導入は無いため基本不要） |

### 1.4 既存機能への横展開・確認のみ（同じ問題の有無を確認）

| 項目 | 状況 | 対応 |
| --- | --- | --- |
| goal.categoryごとの表示分岐 | `features/goal/goalCategoryVariant.ts` の `resolveByGoalCategory` を既存コンポーネント（`AnalyticsPage.tsx`・`GoalDetailPage.tsx`）が使用 | 新規コンポーネントもこの網羅的分岐方式に揃える（tscが分岐漏れを検知） |
| ダークモード対応 | `chartColors.ts` の `isDarkTheme()` | 新規コンポーネントも同形式の関数で色を解決する |
| AI未設定時の表示 | `useAiConfigured` フック・`AiUnconfiguredNotice` | 道標（AIフィードバック日の目印）はフィードバック履歴が0件なら自然に消えるため、専用の未設定バナーは不要（空配列ハンドリングのみ）と判断 |
| 日次報告閲覧への遷移 | `ROUTES.dailyReportView(date)` = `/records/:date/view` | 道標クリック時の遷移先として確認済み、流用する |
| エクスポート・バックアップ | `export_service_exam.py`（リプラン履歴は既存のナレッジエクスポートに出力済み）、`app/api/data.py`（バックアップは生テーブルダンプ） | 新規の図はUI専用の算出値でありDBに保存しないため、エクスポート形式・バックアップへの変更は不要（確認のみ） |
| Alembicマイグレーション | `backend/alembic/` | 新しい値をDBに保存しない方針のため、原則マイグレーション不要（確認のみ） |
| 性能要件 | `GET /dashboard` は既にAI呼び出しを行わない非AI集計のみで2秒要件を満たす設計 | 新規フィールド追加時もこの方針を継続する（N+1を避けるクエリ設計） |

## 2. 現状のベースライン（開発前、2026-10-29）

- バックエンド：`ruff check .` 全通過、`pytest --cov=app` **2064件全通過・カバレッジ100%**（stmt/branch共に9050/1620行）。失敗しているテストなし。
- フロントエンド：`oxlint` 0件、`tsc -b` 0件、`vitest run --coverage` **164ファイル・1402件全通過・カバレッジ100%**（stmt/branch/func/line全て）。失敗しているテストなし。
- 既存開発Todoとの競合：なし。`開発Todo_目標状態遷移再設計_ミチナリ_v1.0.md` にチェック更新漏れ（実装済みだが `[ ]` のまま）があるが、本件とは無関係。

## 3. 作業Todo

凡例：`[ ]` 未着手、`[x]` 完了。各項目の完了条件は「テストが通ること」と「カバレッジ100%（例外処理を除く）」。

### 3.1 設計（新機能のため着手前に必須）

- [x] S-01 `/threat-model`（STRIDE分析）を実施（2026-10-29）。結果は下表（§3.1 STRIDE分析結果）および §6 に反映
- [x] S-02 新規APIレスポンス構造（正規化された点列・マイルストーン）の設計確定（2026-10-29）。詳細版 `GoalRoadmapRead`：`category`／`startDate`／`goalDate`／`todayDate`／`progressRatio`(0.0-1.0)／`isAchieved`／`plannedPoints: {date, ratio}[]`／`actualPoints: {date, ratio}[]`／`footprintDates: {date, hasInput}[]`（READING/WORK用、EXAMは空配列）／`replanMarks: {date, ratio}[]`（EXAMのみ、U10によりREADING/WORKは空配列）／`feedbackMarks: {date}[]`（道標、`date`は`ROUTES.dailyReportView(date)`の引数そのもの）／`bufferDates: date[]`（EXAMのみ、U8によりREADING/WORKは空配列）／`overrunDays: float|null`（EXAMのみ算出。スケジュール状態への変換はフロント既存の`resolveScheduleStatus`に委ね、backendでは複製しない。U16）。縮小版は既存`GoalCardRead`に`roadmap_progress_ratio`／`roadmap_is_achieved`／`roadmap_overrun_days`のみ追加（U15）。文言（カテゴリ表示名等）は返さず、フロント側が`ja.json`で解決する（ゼロハードコーディング、CLAUDE.md）

#### STRIDE分析結果（2026-10-29）

データフロー：`[利用者（開発キットで認証済み）] → [GET /dashboard（既存拡張）／GET /goals/{id}/roadmap（新規）] → [roadmap_service（既存テーブルの読み取りのみ）] → [DataStore：新規保存なし]`。信頼境界はブラウザ↔ローカルFastAPIサーバ間（社内限定・単一利用者のデスクトップ運用、CLAUDE.md前提）。

| カテゴリ | 脅威 | 対策の決定 |
| --- | --- | --- |
| Spoofing | 未認証でのAPI呼び出し | Mitigate：既存の認証依存関係（Depends）を新規ルーターにも必ず付与する（B-05で確認） |
| Tampering | 存在しない／他の `goal_id` を指定した改ざんされたリクエスト | Mitigate：既存の目標取得パターン（存在確認→404、ドメイン例外→API層変換）をそのまま使う（B-05） |
| Repudiation | 該当なし（読み取り専用、状態変更を伴わない） | Accept：対象外 |
| Information Disclosure | エラーメッセージからの内部情報漏洩、道標クリック先（日次報告閲覧）での越権表示 | Mitigate：既存のドメイン例外→HTTPエラー変換パターンを踏襲。日次報告閲覧は既存ルート・既存権限チェックを流用し新規リスクを増やさない |
| Denial of Service | 複数教材・長期目標での計画線合成計算の計算量増大 | Mitigate：日次ループの計算量を教材数×日数の線形に留め、B-07でダッシュボード2秒要件への影響を確認する |
| Elevation of Privilege | 該当なし（ロール区分なし、単一利用者前提） | Accept：対象外 |

※ 本結果は §4 の文書改訂（D-03、設計書ロジック・プロンプト編の脅威モデル節）に反映する。

### 3.2 文書改訂

- [ ] D-01 要件定義書：新設要件（R-番号）、改訂履歴
- [ ] D-02 仕様書：機能一覧、`GoalDetailPage` タブ構成、ダッシュボード画面仕様、13.4節の参照追記、改訂履歴
- [ ] D-03 設計書（ロジック・プロンプト編）：3種別の算出ロジック、改訂履歴
- [ ] D-04 設計書（データ構造編）：新規APIレスポンス構造、改訂履歴
- [ ] D-05 実装フェーズ分割計画書：Phase 47
- [ ] D-06 OPERATIONS.md：必要があれば追記

### 3.3 バックエンド実装

- [x] B-01 `work_report_service.py`：`default_semiannual_period_key`／`semiannual_period_range` を公開関数化（既存呼び出し元・テストを更新し、既存テストが通ることを確認、2026-10-29）
- [x] B-02 `roadmap_service.py`：EXAM用算出（山頂日付＝全科目中の最も遅い受験日、標高＝全周回進捗率、計画線＝複数教材の単純平均合成、リプラン目印＝`PlanBaseline`〈INITIAL除く〉、道標＝AIフィードバック日、予備日＝バッファ日、2026-10-29）
- [x] B-03 `roadmap_service.py`：READING用算出（道の長さ＝総ページ数、現在地＝現在ページ、足跡＝ページ未入力の記録日、計画線＝日数按分の予定ページ、道標＝AIフィードバック日、2026-10-29）
- [x] B-04 `roadmap_service.py`：WORK用算出（道の起点・終点＝現評価期間、足跡＝記録した日、道標＝AIフィードバック日、2026-10-29）。実装中に判明：`resolve_work_period`は常にtodayを含む期間を返すため「ゴール超過」は構造的に発生しない。期間最終日（ゴール当日）を達成扱い（`today >= goal_date`）とし、dashboard.pyの縮小版も同じ条件にした
- [x] B-05 新規API（`GET /goals/{id}/roadmap`詳細版、`GET /dashboard`の`GoalCardRead`拡張で縮小版）、スキーマ（`app/schemas/roadmap.py`）。goals.pyは既存の`baselines`エンドポイントと同じ置き場所のため`main.py`への新規ルーター登録は不要（既存`goals_router`に相乗り、2026-10-29）
- [x] B-06 境界値テスト：記録0件、ゴール当日、ゴール超過、進捗100%、AI未設定、フィードバック履歴0件、各目標状態（DRAFT/ACTIVE/PAUSED/CLOSED_WITH_RESULT/CLOSED_WITHOUT_RESULT、`archived_at`設定済み）。`backend/tests/test_roadmap_service.py`（29件）・`test_api_goals.py`追加3件で網羅（2026-10-29）
- [x] B-07 性能確認：縮小版（`GoalCardRead`拡張）は既存の`progress_rate`・`forecast_deviation_days`を再利用するのみで新規DBクエリを追加しておらず、N+1なし・AI呼び出しなしを確認（2026-10-29）

### 3.4 フロントエンド実装

- [x] F-01 `roadmapGeometry.ts`：3種別の純粋関数（SVG座標計算）とテスト（2026-10-29、フォーク実装）
- [x] F-02 `GoalRoadmapMini.tsx`：単独コンポーネント、`GoalCardList.tsx`への組込み、`role="img"`・`aria-label`（要約文言）（2026-10-29、フォーク実装）
- [x] F-03 `GoalRoadmapTab.tsx`：`GoalDetailPage` への新規タブ追加（`EXAM_TABS`／`READING_TABS`／`WORK_TABS`の`basicInfo`の次、描画分岐は`GoalDetailTabContent`に集約）（2026-10-30、フォーク中断を引き継ぎ本セッションで実装。U19参照）
- [x] F-04 初回表示アニメーション（現在地まで歩く、`requestAnimationFrame`で遷移を発生させる）、`prefers-reduced-motion` 分岐とテスト（2026-10-29フォーク実装、2026-10-30にoxlintの`set-state-in-effect`警告を解消するため`requestAnimationFrame`化）
- [x] F-05 道標クリック→`ROUTES.dailyReportView(date)` への遷移（`RoadmapDiagram.tsx`の`FeedbackMarks`、`interactive`時のみ。2026-10-29）
- [x] F-06 `api/goals.ts`に`getGoalRoadmap`追加、型の生成し直し（`npm run generate:api-types`→`api.d.ts`に`GoalRoadmapRead`等反映）（2026-10-29）
- [x] F-07 `ja.json`：`help.sections.goals.roadmap`に図の見方の説明、`goals.roadmap.*`に要約文言・ラベルのキーを追加（2026-10-29）。U11の訂正により`en.json`にも同内容を追加（2026-10-30）
- [x] F-08 ダークモード確認：`chartColors.ts`の既存関数（`resolveAxisLineColor`/`resolveGridLineColor`/`resolvePlanLineColor`/`cycleSeriesColor`）をそのまま使用、新規色関数は追加していない（2026-10-29）
- [x] F-09 `npx tsc -b`・`npm run lint`（oxlint）・`npm run test`（vitest、カバレッジ付き）を実行し確認（2026-10-30）。初回実行でtsc 8件のエラー（U18）とoxlint警告3件（`GoalDetailPage`/`RoadmapDiagram`の関数行数超過、`RoadmapDiagram`のeffect内setState）を検出し、型修正・関数分割・`requestAnimationFrame`化で解消。最終結果：tsc 0件・oxlint 0件・vitest **170ファイル・1446件全通過・カバレッジ100%**（開発前164ファイル・1402件から+6ファイル・+44件、既存テストの破壊なし）

### 3.5 検証

- [x] V-01 ruff・pytest・vitest（2026-10-30実行。backend: `ruff check .`全通過、`pytest --cov=app` 2093件全通過・カバレッジ100%〈バックエンド実装完了時から変化なし、本セッションではbackendを変更していない〉。frontend: 上記F-09のとおり170ファイル・1446件全通過・カバレッジ100%）
- [ ] V-02 既存DBからの起動確認（新しい値を保存しないため、マイグレーション不要であることの確認）
- [ ] V-03 実機確認：3種別それぞれの図、各状態（下書き・進行中・一時停止・アーカイブ・クローズ）での矛盾のなさ、ダッシュボード初期表示2秒以内、ダークモード、`prefers-reduced-motion`
- [ ] V-04 横展開チェック（§1.4の確認対象の再確認）
- [ ] V-05 コーディングルールチェック（DRY・ゼロハードコーディング・命名・コメント規約）
- [ ] V-06 セキュリティチェック（認可境界：道標クリックが自分の目標の日次報告のみに遷移すること等。関連レビューエージェント：`auth-reviewer`・`xss-reviewer`）

## 4. 処理フロー（確定版）

1. **EXAM（山）**：標高＝全周回を通した目標単位の進捗率（教材平均）。山頂X軸＝全科目中の `effective_exam_date` の最大値。計画線＝教材ごとの `compute_plan_line` を日次で単純平均し1本に合成。現在地アイコン＝`resolveScheduleStatusIcon`（UI-02〜04、既存のEXAM専用判定をそのまま使用）、予備日はUI-07。リプラン履歴（`PlanBaseline`）の各時点に「道の引き直し」目印、引き直し後の新しい計画線を描く。
2. **READING（道）**：道の長さ＝総ページ数。現在地＝現在ページ（`book_service.get_book_progress`）。ページ未入力の記録日は道の上に足跡として配置。計画線＝開始日からゴール（最終ページ）までの日数按分。現在地アイコンは常にUI-01（U7）。道の引き直し目印は表示しない（U10）。
3. **WORK（足跡の積み上げ）**：道の起点・終点＝現評価期間（U9）。記録した日を足跡として積み上げる。現在地アイコンは常にUI-01（U7）。道の引き直し目印は表示しない（U10）。
4. **共通**：AIフィードバックを受けた日（`chat_message`、`daily_record_id`経由）に道標を配置。クリックで `ROUTES.dailyReportView(date)` へ遷移。達成時（進捗100%またはゴール到達）はゴールにUI-11。図には `role="img"`・`aria-label` で要約文言（例：「全体の62%、予定より3日遅れ」）を付与。初回表示時のみ現在地まで歩くアニメーション（`prefers-reduced-motion` 時は無効化）。

## 5. 検証の基準

| 項目 | 基準 |
| --- | --- |
| ダッシュボード初期表示 | 2秒以内（既存要件を維持） |
| アクセシビリティ | 図に `role="img"`・`aria-label`（要約文言）を付与 |
| 境界ケース | 記録0件・ゴール当日・ゴール超過・進捗100%で破綻しないこと（単体テストで検証） |
| 状態の一貫性 | DRAFT／ACTIVE／PAUSED／CLOSED_WITH_RESULT／CLOSED_WITHOUT_RESULT／`archived_at`設定済みの全組み合わせで表示矛盾がないこと |
| テストカバレッジ | 新規コンポーネント・算出処理ともに100%（例外処理を除く） |

## 6. 既知のリスクと対策

| リスク | 対策 |
| --- | --- |
| 資格の複数教材の計画線合成が実際の感覚とズレる | 単純平均で開始し、実機確認（§3.5 V-03）で違和感があれば加重方式を検討（本Todoに追記してから対応） |
| 2周目・3周目の表現が「標高＝全周回進捗率」のみでは単調に見える | 本件スコープ外とし、将来課題として記録（周回の区切り線等は別Todoで検討） |
| 読書・仕事の「強みの可視化」要件を部分的にしか満たせない（U7・U10で縮小） | 決定事項として明記済み。足跡の積み上がり・計画線との重ね描きで代替する |
| 道標クリックの認可境界（他利用者の目標の日次報告が見えてしまう等） | 単一利用者アプリだが、`auth-reviewer` でAPIの目標ID検証を確認する |
| CLOSED目標への新しい直接遷移経路の追加が既存のエクスポート誘導と混在する | ダッシュボードの縮小版からのみ直接遷移を許可し、一覧の既存振り分け（`resolveGoalListTarget`）は変更しない |
| **【文書改訂時に発見、2026-10-30】U8の前提誤り**：既存仕様書13.5「休憩バッファアイコン（UI-07）の適用範囲」は「資格試験・読書目標にのみ表示し、仕事目標には表示しない」と明記しており、READINGもUI-07の対象に含まれる。バッファ日（`day_type`）は`calendar_service.resolve_day_types`が算出する**目標に依存しないアプリ全体のカレンダー概念**（関数に`goal`/`category`引数が無い）であり、U8が前提にした「バッファ日の概念は資格専用」は誤り（根拠にした`metrics_service.compute_buffer_usage_rate`がEXAM以外`None`を返すのは「バッファ**消費率**」という別の派生指標の話であり、バッファ日の存在自体とは別概念だった）。現在の実装（`roadmap_service._reading_roadmap`）はREADINGの`buffer_dates`を常に空配列にしており、既存仕様13.5と不整合（実装ギャップ）。 | 本工程（文書改訂・検証）では実装を変更しないため、次の実装工程で`_reading_roadmap`にも`_buffer_dates`を適用し、READINGの道にも予備日（UI-07）を表示するよう修正する。修正までの間、本機能のREADINGの道のりは13.5の既定方針より狭い表示になっている（現在地アイコンは常にUI-01のまま。U7は維持：進捗状態アイコンUI-02〜04は不要論拠が別にあり妥当だが、予備日UI-07の除外根拠は誤りだったため訂正が必要） |

## 7. 完了の定義

- 全項目（§3）が `[x]` になり、テストが通る（バックエンド・フロントエンドとも）。
- カバレッジは例外処理を除き100%。
- §5 の基準を満たすか、未達の場合は理由と対応を §9 に記録する。
- 文書（§1.3）が実装と一致する。
- §0 の決定事項（U1〜U14）がすべて実装に反映されている。

## 8. 作業記録

（作業の進行に応じて追記する）

- 2026-10-29 工程1・工程2完了。バックグラウンド調査（2件）により、前提資料・既存Todoとの競合確認・全ソースコードのフルスキャンを実施。ベースライン（バックエンド2064件・フロントエンド1402件、ともにカバレッジ100%）を記録。未決事項2件（読書・仕事の「道の引き直し」目印の表現、READING/WORKへの進捗状態アイコン新設の要否）を利用者に確認し、いずれも「現状の既定方針を維持（新設・表示しない）」の回答を得た（U7・U10に反映）。

- 2026-10-29 バックエンド実装（§3.3 B-01〜B-07）完了。
  - 新規：`backend/app/services/roadmap_service.py`（EXAM/READING/WORKの3種別算出、`resolve_work_period`・`compute_elapsed_ratio`はdashboard.pyと共用）、`backend/app/schemas/roadmap.py`（`GoalRoadmapRead`等）、`backend/tests/test_roadmap_service.py`（29件）。
  - 変更：`backend/app/services/work_report_service.py`（`_semiannual_period_range`→`semiannual_period_range`公開化）、`backend/app/api/goals.py`（`GET /goals/{id}/roadmap`追加）、`backend/app/api/dashboard.py`（`_resolve_roadmap_summary`追加、`GoalCardRead`に`roadmap_progress_ratio`／`roadmap_is_achieved`／`roadmap_overrun_days`を付与）、`backend/app/schemas/dashboard.py`（同3フィールド追加）、`backend/tests/test_work_report_service.py`（リネーム追随）、`backend/tests/test_api_goals.py`（roadmap API テスト3件追加）。
  - 実装中に追記した決定事項：U16（スケジュール状態フィールドの重複排除、backendは`overrunDays`のみ返しフロント既存の`resolveScheduleStatus`に委ねる）、U17（仕事目標の計画線・実績線は常に空配列、進捗比率は経過日数割合で代替）。
  - 検証結果：`ruff check .` 全通過。`pytest --cov=app` **2093件全通過・カバレッジ100%**（開発前2064件から+29件、既存テストの破壊なし）。環境側の問題（myvenvに`pypdf`が未導入でテスト収集が14件エラー）を発見し、`pyproject.toml`の既存宣言どおり`pip install -e .`で導入して解消（本機能のスコープ外、環境ドリフトの復旧）。
  - 残課題：文書改訂（§3.2 D-01〜D-06）・フロントエンド実装（§3.4 F-01〜F-09）・検証（§3.5 V-02〜V-06）は次工程。

- 2026-10-30 フロントエンド実装（§3.4 F-01〜F-09）完了。前回セッションでフロントエンド実装フォークが完了前にホストプロセス終了により中断（F-03未着手、§8未更新のまま停止）していたものを引き継いで完了させた。
  - 中断時点までにフォークが作成・変更していたファイル（自動コミット済み）：`frontend/src/features/goal/roadmapGeometry.ts`+test、`GoalRoadmapMini.tsx`+test、`RoadmapDiagram.tsx`+test、`roadmapSummaryText.ts`+test、`frontend/src/hooks/usePrefersReducedMotion.ts`+test、`frontend/src/api/goals.ts`（`getGoalRoadmap`）、`frontend/src/constants/queryKeys.ts`、`frontend/src/features/dashboard/GoalCardList.tsx`（`GoalRoadmapMini`組込み）、`frontend/src/locales/ja.json`・`en.json`、`frontend/src/types/api.d.ts`、`backend/app/content/help_content.json`。
  - 本セッションで追加実装：`frontend/src/features/goal/GoalRoadmapTab.tsx`（新規、F-03）＋test、`GoalDetailPage.tsx`への`roadmap`タブ組込み（`EXAM_TABS`/`READING_TABS`/`WORK_TABS`、`GoalDetailTabContent`への描画分岐の切り出し）。
  - 検証で発見し修正した不整合（U18）：`RoadmapDiagramInput`型に`overrun_days`が無く`tsc -b`が8件エラー（`RoadmapDiagram.tsx`本体が未検証のまま参照していた）。型へ追加し、連動する`GoalCardList.tsx`（`?? null`）・`statsVisibility.test.ts`（フィクスチャに`roadmap_is_achieved`追加）を修正。
  - oxlint警告3件（`GoalDetailPage`/`RoadmapDiagram`の関数行数超過、effect内のsetState）を関数分割（`GoalDetailTabContent`、`BufferTicks`/`FootprintMarks`/`ReplanMarks`/`FeedbackMarks`）と`requestAnimationFrame`化で解消。
  - U11を訂正（上表参照）：`en.json`のヘルプ本文は既に全機能で完全対訳済みと判明したため、本機能のタブラベル・ツールチップ・要約文言・ヘルプ本文も`en.json`に追加した（フォークの実装が正しく、当初のU11決定が誤りだった）。
  - U3の記述を実装事実に合わせて訂正（上表参照）：ダッシュボードカードは元々`resolveGoalListTarget`を経由しないプレーンな`Link`だったため、新規の「タブへの直接URL遷移」は導入せず、既存の「タブ深いリンクは導入しない」方針に合わせた。
  - 新規テスト追加（カバレッジ100%達成のため）：`GoalRoadmapTab.test.tsx`（3件）、`RoadmapDiagram.test.tsx`に3件追加（計画線/実績線のpolyline描画、足跡、リプラン目印）、`GoalCardList.test.tsx`に1件追加（roadmap関連フィールドが`undefined`でも破綻しない）。
  - 最終確認：`cd backend && ruff check . && python -m pytest --cov=app`（2093件全通過・カバレッジ100%、本セッションでbackend未変更のため前回と同値）。`cd frontend && npx tsc -b && npm run lint && npm run test`（tsc 0件・oxlint 0件・vitest 170ファイル1446件全通過・カバレッジ100%）。
  - 残課題：文書改訂（§3.2 D-01〜D-06）・検証（§3.5 V-02〜V-06）は次工程。
