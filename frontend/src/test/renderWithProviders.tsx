/** 画面・部品の描画テスト用に、本番と同じProviderで包んで描画する共通ヘルパ（Phase 34）。
 *
 * 描画テストを持つファイルが `QueryClient` の生成・`QueryClientProvider`・`ToastProvider`・
 * ルータの用意をそれぞれ逐語で書いていたため、1箇所へ集約する（CODING_RULES.md ①DRYの原則）。
 *
 * `QueryClient` はテストごとに使い捨てにする。使い回すとキャッシュが次のテストへ漏れ、
 * 実行順で結果が変わるため。再試行は切る。既定では失敗したクエリ・ミューテーションを
 * 再試行するため、エラー表示を検証するテストが再試行の完了待ちで遅くなり不安定になる。
 *
 * `DailyReportDraftProvider` も本番同様に含める（App.tsxのLayout参照）。SC-06/SC-07の
 * 下書きはこのProviderが無いと `useDraftStore` が例外を投げるため、これらを描画する
 * テストは全てこのヘルパ（または同等のProvider構成）を経由する必要がある。 */
import type { ReactElement, ReactNode } from 'react'
import { render, type RenderResult } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, type InitialEntry } from 'react-router-dom'
import { ToastProvider } from '../components/Toast'
import { DailyReportDraftProvider } from '../features/record/dailyReportDraftStore'

export interface RenderWithProvidersOptions {
  /** 初期表示のURL。ルートパラメータを読む画面で使う（既定は `/`）。
   * `location.state` を検証したい画面では `{ pathname, state }` の形でも渡せる
   * （`MemoryRouter`の`initialEntries`へそのまま渡すだけのため）。 */
  initialEntries?: InitialEntry[]
}

/** テスト用の `QueryClient`（再試行なし・使い捨て）。 */
function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
}

/** Provider一式で包んで描画する。戻り値は `@testing-library/react` の `render` と同じ。 */
export function renderWithProviders(
  ui: ReactElement,
  options: RenderWithProvidersOptions = {},
): RenderResult {
  const queryClient = createTestQueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={options.initialEntries ?? ['/']}>
        <ToastProvider>
          <DailyReportDraftProvider>{children}</DailyReportDraftProvider>
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>
  )

  return render(ui, { wrapper })
}
