### Phase 41：読書目標の本棚UI

| 項目 | 内容 |
| --- | --- |
| 目的 | 読書は「管理型」ではなく「記録・活用型」（6.11本文、[[goal-category-design-axis]]）という位置づけにもかかわらず、読了・中断した読書目標が資格試験・仕事目標と同じクローズ済み一覧に無機質に並ぶだけだった。読書という体験にふさわしい見せ方（本棚に書籍を並べる）を提供し、書籍単位で日次の想起記録・成長記述・振り返りレポートへ一望でアクセスできるようにする |
| 投入文書 | CLAUDE.md、運用設計ルール、仕様書（第4章画面一覧・6.18〜6.19節新設） |

**背景**

利用者との設計協議（2026-09-25〜26）で、読了・中断した読書目標を独立した「本棚」画面に書籍カードとして表示し、「アーカイブする」＝棚からしまう、という対応にする方針を確定した。既存の`goal.archived_at`をそのまま流用し、本棚専用のDB状態は追加しない。中断（`CLOSED_WITHOUT_RESULT`）も読了とは別枠（中断棚）で表示する。書籍詳細（書誌情報・想起記録・成長記述・振り返りレポート）は`AnalyticsPage`・`KnowledgeExportPage`が既に持つ`ReadingLogHistoryTab`・`GrowthDescriptionTab`・`RetrospectiveSection`をそのまま流用し、新規ロジックを持ち込まない。バックエンドは`GET /goals`・`GET /goals/{id}`が既にstatus・archived_atに関わらず一律に返す設計だったため、変更不要（フロントエンドのみの機能追加）。

**実装対象**

- `frontend/src/constants/routes.ts`に`bookshelf`（`/bookshelf`）・`bookDetail`（`/bookshelf/:goalId`）を追加し、`App.tsx`・`GlobalNav.tsx`に配線
- `frontend/src/api/goals.ts`に`listCompletedReadingBooks`（`listActiveReadingBooks`と対になる、category=READING×status∈{CLOSED_WITH_RESULT, CLOSED_WITHOUT_RESULT}の一覧取得。同じ理由でN+1構成を許容）を追加
- `frontend/src/features/bookshelf/`を新設: `bookStatusVariant.ts`（読了/中断の判定・色分け）、`groupCompletedBooks.ts`（棚上/しまった本×読了/中断の4区分への振り分け、closed_at降順ソート）、`BookSpineCard.tsx`（書籍カード。アーカイブ/復元/完全削除は`GoalsListPage`の`GoalCard`と同じ操作パターン）、`BookShelfSection.tsx`（1関数100行の上限対応で切り出したセクション部品）、`BookInfoTab.tsx`（書誌情報タブ。達成バッジ`is_achieved`は出さない＝棚に置かれていること自体が達成の表現という設計判断）
- `frontend/src/pages/BookshelfPage.tsx`（SC-18本棚）・`BookDetailPage.tsx`（SC-19書籍詳細、4タブ構成）を新設。既存の`GoalsListPage`のクローズ済み行・エクスポートリンクは変更しない（本棚は追加の入口という位置づけ）
- `frontend/src/locales/ja.json`に`nav.bookshelf`・`bookshelf.*`を追加（画面ごとに独立したキー空間という既存慣習を踏襲）

**完了条件**

- 読了した読書目標が本棚の「読了した本」棚に、中断した読書目標が「中断した本」棚に分けて表示される
- 書籍をアーカイブすると本棚の棚から消え、「しまった本を見る」トグルで再表示できる。復元・完全削除も一覧画面（GoalsListPage）と同じ挙動になる
- 書籍詳細画面で、想起記録（記録タブ）・成長記述・振り返りレポート（NewtonX生成の`goal_retrospective`）が実データで表示される
- 既存のバックエンド・フロントエンドのテストが引き続き成功し、フロントエンドのカバレッジ100%を維持する

---

**Phase41完了（2026-09-26）。**

- バックエンド：変更なし（`GET /goals`・`GET /goals/{id}`が既にstatus・archived_atに依存しない設計だったため）
- フロントエンド：新規ファイル7件（`api/goals.ts`への追記含む。`features/bookshelf/bookStatusVariant.ts`・`groupCompletedBooks.ts`・`BookSpineCard.tsx`・`BookShelfSection.tsx`・`BookInfoTab.tsx`、`pages/BookshelfPage.tsx`・`BookDetailPage.tsx`）、新規テストファイル7件。1200テスト・カバレッジ100%
- `tsc -b`・oxlint 通過（新規ファイルによる警告なし）

---

