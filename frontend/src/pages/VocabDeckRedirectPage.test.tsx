import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Route, RouterProvider, createMemoryRouter, createRoutesFromElements } from 'react-router-dom'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { ROUTE_PATTERNS } from '../constants/routes'
import { VocabDeckRedirectPage } from './VocabDeckRedirectPage'
import type { VocabDeck } from '../api/vocab'

const getVocabDeck = vi.hoisted(() => vi.fn())
vi.mock('../api/vocab', () => ({ getVocabDeck }))

const GOAL_DETAIL_MARKER = '目標詳細に到達した'

function makeDeck(overrides: Partial<VocabDeck> = {}): VocabDeck {
  return {
    id: 5,
    goal_id: 1,
    name: '資格デッキ',
    description: null,
    use_in_ai: true,
    display_order: 0,
    card_count: 0,
    mastered_card_count: 0,
    term_card_count: 0,
    term_mastered_card_count: 0,
    situation_card_count: 0,
    situation_mastered_card_count: 0,
    session_default_questions: 10,
    session_max_questions: 100,
    ...overrides,
  }
}

/** `VocabDeckRedirectPage`はdeckIdから遷移先（目標詳細）を決めるため、実際のルーティングで
 * 検証する（`DailyReportPage.test.tsx`と同じ理由。`MemoryRouter`単体では`<Navigate>`の
 * 遷移先に何が描画されるか確認できない）。 */
function renderAtDeckRoute(deckId: number) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const router = createMemoryRouter(
    createRoutesFromElements(
      <>
        <Route path={ROUTE_PATTERNS.vocabDeck} element={<VocabDeckRedirectPage />} />
        <Route path={ROUTE_PATTERNS.goalDetail} element={<p>{GOAL_DETAIL_MARKER}</p>} />
      </>,
    ),
    { initialEntries: [`/vocab/${deckId}`] },
  )
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
})

describe('VocabDeckRedirectPage', () => {
  it('shows the loading text while fetching', () => {
    getVocabDeck.mockReturnValue(new Promise(() => {}))
    renderAtDeckRoute(5)

    expect(screen.getByText(t('common.loading'))).toBeDefined()
  })

  it('shows an error message when fetching fails', async () => {
    const error = new Error('取得失敗')
    getVocabDeck.mockRejectedValue(error)
    renderAtDeckRoute(5)

    expect(await screen.findByText(apiErrorMessage(error))).toBeDefined()
  })

  it('redirects to the deck owner goal detail page once the deck loads', async () => {
    getVocabDeck.mockResolvedValue(makeDeck({ goal_id: 42 }))
    renderAtDeckRoute(5)

    expect(await screen.findByText(GOAL_DETAIL_MARKER)).toBeDefined()
    expect(getVocabDeck).toHaveBeenCalledWith(5)
  })
})
