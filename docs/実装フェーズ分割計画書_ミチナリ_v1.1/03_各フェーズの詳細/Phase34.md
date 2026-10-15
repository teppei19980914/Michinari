### Phase 34：描画テストの共通基盤

| 項目 | 内容 |
| --- | --- |
| 目的 | 画面の描画テストを書くための共通ヘルパを整備し、以降の画面テストを複製で展開できる状態にする |
| 投入文書 | CLAUDE.md、運用設計ルール |

**背景**

描画テストを持つファイルが、`QueryClient` の生成と `QueryClientProvider` での包み込みをそれぞれ逐語で書いている。画面テストを増やすほどこの重複が広がるため、テスト対象を増やす前に共通化する（CODING_RULES.md「①DRYの原則」）。

テスト用の `QueryClient` は再試行を無効にする必要がある。既定では失敗したクエリを再試行するため、エラー表示を検証するテストが再試行の完了を待って遅くなる・不安定になるためである。

**実装対象**

- `src/test/renderWithProviders.tsx`（新設）：使い捨ての `QueryClient`（再試行なし）による `QueryClientProvider` と `MemoryRouter` で包んで描画するヘルパ。初期表示のURLを指定できるようにする
- 既存の描画テストのうち、他の作業と編集が競合しないものから順次移行する

**完了条件**

- 新しい画面テストが、ヘルパを取り込んで確認観点を書くだけで始められる
- 移行した既存テストの結果が移行前と変わらない

---

**Phase34完了（2026-09-13）。**`src/test/renderWithProviders.tsx`（再試行なしの使い捨て `QueryClient`・`MemoryRouter`・`ToastProvider` で包む）と `src/test/fixtures.ts`（`makeGoalDetail` 等のフィクスチャ組み立て）を新設。`src/test/**` はテストコードの一部であるためカバレッジ対象外とする。既存の描画テストは `CloseGoalModal`・`DeleteArchivedGoalModal`・`DailyReportViewPage`・`ProgressOnlyPage` の4件を移行し、移行前後でテスト件数・結果が変わらないことを確認した（8/8/4/5件）。`DailyReportPage.test.tsx` は離脱警告（`useBlocker`）がデータルータでしか動作せず `createMemoryRouter` を要するため、ヘルパの適用対象外として据え置く（ヘルパのコメントと OPERATIONS.md に理由を明記）。これにより自前でProviderを組む描画テストは同ファイルのみとなった。

---

