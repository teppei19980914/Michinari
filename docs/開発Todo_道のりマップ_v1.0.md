# 開発Todo：道のりマップ（v2.4.0 対象）

本書は、目標ごとの進捗を「スタート→現在地→ゴール」の図（資格=山、読書=地図上の道、仕事=足跡の積み上げ）として可視化する「道のりマップ」機能の開発作業の正（Single Source of Truth）である。
規模はマイナーバージョンアップ（2.3.1 → 2.4.0）に相当する。作業は現行ブランチ `dev/2026-10-29` で行う。

## 0. 決定事項（2026-10-29 時点で確定）

| # | 決定 | 値・理由 |
| --- | --- | --- |
| U1 | 詳細版の配置場所 | `GoalDetailPage` に新規タブ「道のり」を追加（`basicInfo` の次、全種別共通）。理由：`AnalyticsPage` は `selectableAnalyticsGoals.ts` でDRAFT状態の目標を一覧から除外する設計のため、要件「下書き…のそれぞれで表示に矛盾が出ないように」と矛盾する。`GoalDetailPage` は `isReadOnly = isClosedGoalStatus(goal.status)` のみで分岐し、DRAFT〜CLOSED全状態を表示できる |
| U2 | 縮小版の配置 | ダッシュボードの目標カード一覧（`GoalCardList` 系）に追加。単独コンポーネント `GoalRoadmapMini` として実装し、ふりかえりまとめ・社内共有カードでも再利用できるようにする（読み取り専用、クリックで詳細タブへ遷移） |
| U3 | CLOSED目標の遷移経路 | 目標一覧からCLOSED目標を選ぶと現状 `resolveGoalListTarget` により `ROUTES.goalExport`（SC-13 ナレッジエクスポート）へ遷移し `GoalDetailPage` へは行かない。ダッシュボードの縮小版「道のり」クリックはこの振り分けを経由せず、常に `GoalDetailPage` の道のりタブへ直接遷移させる（URL直接指定）。これによりCLOSED後も道のりを閲覧できる |
| U4 | 資格：山頂の日付 | 要件文言どおり「全科目の受験を終える日」＝ 目標に紐づく全科目の `effective_exam_date` の最大値（最も遅い日）を新規算出する。既存の `dashboard.py` `_goal_remaining_days`（最も近い受験日を使う別目的の関数）とは流用せず、新規関数とする |
| U5 | 資格：2周目・3周目の扱い | 標高＝全周回を通した進捗率。既存 `cycle_service`（`total_work = total_amount × planned_cycles`）をそのまま使う。周回ごとの区切り線等の追加表現は本件のスコープ外とし、§7（既知のリスクと対策）に将来課題として残す |
| U6 | 資格：複数教材の計画線集約 | 教材ごとの `analytics_service.compute_plan_line` の結果を日次で単純平均し、目標単位の1本の計画線に合成する新規ロジックを追加する |
| U7 | 読書・仕事：進捗状態アイコン（UI-02〜04） | **新設しない**（利用者回答、2026-10-29）。既存仕様書（v1.1 13.4）が「完了予測・スケジュール状態の表示は資格試験目標にのみ行い、読書・仕事目標には表示しない」と明記しているため、この既定方針を維持する。読書・仕事の現在地アイコンは常にUI-01（normal）とし、計画との差は図中の線のズレ自体（計画線と実際の歩みの間隔）で表現する。達成時のみUI-11 |
| U8 | 予備日アイコン（UI-07） | 資格のみ。バッファ日（`day_type`）の概念は資格専用（`calendar_service`、`metrics_service.compute_buffer_usage_rate` も資格以外は `None` を返す）。読書・仕事には予備日アイコンを表示しない |
| U9 | 仕事：道の起点・終点 | 起点＝現評価期間の開始日、終点＝評価期間の終了日。`work_report_service.default_semiannual_period_key` / `_semiannual_period_range`（private）を公開関数として切り出し利用する。`goal.start_date` や `work_assignment.start_date` は使わない |
| U10 | 読書・仕事：道の引き直し目印 | **表示しない**（利用者回答、2026-10-29）。計画基準値（`PlanBaseline`）という概念自体が読書・仕事には設計上存在しない（データ構造編5.3）。新しい値をDBに保存しない方針の下で代替データも作らない。読書・仕事は「実際の歩み（足跡）の積み上がり自体がまっすぐ向かう強みの可視化になる」とし、計画線と実績線を重ねる表現（要件2の前段）のみ行う |
| U11 | 英語ロケール | 今回は `ja.json` のみに本機能のヘルプ文言を追加する。`en.json` は対象外（既存方針：`ja.json` がヘルプ本文の正、英語対応は別件・未実装） |
| U12 | 新規API | 算出済みの「正規化された点列・マイルストーン」をJSONで返すエンドポイントを追加する。SVG座標への変換はフロント側（`roadmapGeometry.ts`）で行い、座標計算ロジックの重複を避ける |
| U13 | バージョン | 2.4.0。`pyproject.toml` の版更新は**リリース手順（`release.bat`）で入力する**（開発中は変更しない） |
| U14 | フェーズ | 新フェーズ Phase 47（直前の最終フェーズはPhase 46・リマインド導線、2026-10-28マージ済み） |
| U15 | APIの分割 | ダッシュボードの縮小版は既存 `GET /dashboard` の `GoalCardRead` に軽量フィールド（進捗比率・達成フラグ・EXAMのみスケジュール状態／乖離日数）を追加するのみとし、線データ・目印データは返さない。詳細版は目標詳細タブを開いたときに新規 `GET /goals/{id}/roadmap` を呼び、計画線・実績線・足跡・道標・リプラン目印を返す。これにより新規データ取得をダッシュボード初期表示（2秒要件）から分離する |

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
- [x] S-02 新規APIレスポンス構造（正規化された点列・マイルストーン）の設計確定（2026-10-29）。詳細版 `GoalRoadmapRead`：`category`／`startDate`／`goalDate`／`todayDate`／`progressRatio`(0.0-1.0)／`isAchieved`／`plannedPoints: {date, ratio}[]`／`actualPoints: {date, ratio}[]`／`footprintDates: {date, hasInput}[]`（READING/WORK用、EXAMは空配列）／`replanMarks: {date, ratio}[]`（EXAMのみ、U10によりREADING/WORKは空配列）／`feedbackMarks: {date}[]`（道標、`date`は`ROUTES.dailyReportView(date)`の引数そのもの）／`bufferDates: date[]`（EXAMのみ、U8によりREADING/WORKは空配列）／`scheduleStatus: 'delayed'|'onTrack'|'ahead'|null`（EXAMのみ、U7によりREADING/WORKはnull）／`overrunDays: int|null`。縮小版は既存`GoalCardRead`に`progressRatio`／`isAchieved`／`scheduleStatus`／`overrunDays`のみ追加（U15）。文言（カテゴリ表示名等）は返さず、フロント側が`ja.json`で解決する（ゼロハードコーディング、CLAUDE.md）

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

- [ ] B-01 `work_report_service.py`：`default_semiannual_period_key`／`_semiannual_period_range` を公開関数化（既存呼び出し元のテストが通ることを確認）
- [ ] B-02 `roadmap_service.py`：EXAM用算出（山頂日付＝全科目中の最も遅い受験日、標高＝全周回進捗率、計画線＝複数教材の単純平均合成、リプラン目印＝`PlanBaseline`、道標＝AIフィードバック日）
- [ ] B-03 `roadmap_service.py`：READING用算出（道の長さ＝総ページ数、現在地＝現在ページ、足跡＝ページ未入力の記録日、計画線＝日数按分の予定ページ、道標＝AIフィードバック日）
- [ ] B-04 `roadmap_service.py`：WORK用算出（道の起点・終点＝現評価期間、足跡＝記録した日、道標＝AIフィードバック日）
- [ ] B-05 新規API（縮小版・詳細版）、スキーマ、`main.py` 登録。エラーはドメイン例外→API層で変換
- [ ] B-06 境界値テスト：記録0件、ゴール当日、ゴール超過、進捗100%、AI未設定、フィードバック履歴0件、各目標状態（DRAFT/ACTIVE/PAUSED/CLOSED_WITH_RESULT/CLOSED_WITHOUT_RESULT、`archived_at`設定済み）
- [ ] B-07 性能確認：縮小版APIが既存ダッシュボードの2秒要件に抵触しないこと（N+1なきクエリ設計、AI呼び出しなし）

### 3.4 フロントエンド実装

- [ ] F-01 `roadmapGeometry.ts`：3種別の純粋関数（SVG座標計算）とテスト
- [ ] F-02 `GoalRoadmapMini.tsx`：単独コンポーネント、ダッシュボードへの組込み、`role="img"`・`aria-label`（要約文言）
- [ ] F-03 `GoalRoadmapTab.tsx`：`GoalDetailPage` への新規タブ追加（`EXAM_TABS`／`READING_TABS`／`WORK_TABS`）
- [ ] F-04 初回表示アニメーション（現在地まで歩く）、`prefers-reduced-motion` 分岐とテスト
- [ ] F-05 道標クリック→`ROUTES.dailyReportView(date)` への遷移
- [ ] F-06 `api/`新規ファイル、型の生成し直し（`npm run generate:api-types`）
- [ ] F-07 `ja.json`：`help` 名前空間に図の見方の説明、図内要約文言のキーを追加
- [ ] F-08 ダークモード確認（`chartColors.ts` の既存関数を利用）
- [ ] F-09 `npm run lint`・`tsc -b`・`npm run test` の閾値確認

### 3.5 検証

- [ ] V-01 ruff・pytest・vitest（新規機能のカバレッジ100%。全体の最終実行は§9）
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

## 7. 完了の定義

- 全項目（§3）が `[x]` になり、テストが通る（バックエンド・フロントエンドとも）。
- カバレッジは例外処理を除き100%。
- §5 の基準を満たすか、未達の場合は理由と対応を §9 に記録する。
- 文書（§1.3）が実装と一致する。
- §0 の決定事項（U1〜U14）がすべて実装に反映されている。

## 8. 作業記録

（作業の進行に応じて追記する）

- 2026-10-29 工程1・工程2完了。バックグラウンド調査（2件）により、前提資料・既存Todoとの競合確認・全ソースコードのフルスキャンを実施。ベースライン（バックエンド2064件・フロントエンド1402件、ともにカバレッジ100%）を記録。未決事項2件（読書・仕事の「道の引き直し」目印の表現、READING/WORKへの進捗状態アイコン新設の要否）を利用者に確認し、いずれも「現状の既定方針を維持（新設・表示しない）」の回答を得た（U7・U10に反映）。
