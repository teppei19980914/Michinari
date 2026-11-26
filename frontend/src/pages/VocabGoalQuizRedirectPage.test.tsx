import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Route, RouterProvider, createMemoryRouter, createRoutesFromElements } from 'react-router-dom'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { ROUTE_PATTERNS } from '../constants/routes'
import { VocabGoalQuizRedirectPage } from './VocabGoalQuizRedirectPage'
import type { VocabDeck } from '../api/vocab'

const getVocabDecks = vi.hoisted(() => vi.fn())
vi.mock('../api/vocab', () => ({ getVocabDecks }))

const QUIZ_SETUP_MARKER = '問題出題内容設定画面に到達した'

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

/** goalIdからdeckIdを解決して遷移するため、実際のルーティングで検証する
 * （`VocabDeckDetailPage.test.tsx`と同じ理由）。 */
function renderAtGoalRoute(goalId: number) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const router = createMemoryRouter(
    createRoutesFromElements(
      <>
        <Route path={ROUTE_PATTERNS.vocabGoalQuiz} element={<VocabGoalQuizRedirectPage />} />
        <Route path={ROUTE_PATTERNS.vocabQuiz} element={<p>{QUIZ_SETUP_MARKER}</p>} />
      </>,
    ),
    { initialEntries: [`/vocab/by-goal/${goalId}/quiz`] },
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

describe('VocabGoalQuizRedirectPage', () => {
  it('shows the loading text while fetching', () => {
    getVocabDecks.mockReturnValue(new Promise(() => {}))
    renderAtGoalRoute(1)

    expect(screen.getByText(t('common.loading'))).toBeDefined()
  })

  it('shows an error message when fetching fails', async () => {
    const error = new Error('取得失敗')
    getVocabDecks.mockRejectedValue(error)
    renderAtGoalRoute(1)

    expect(await screen.findByText(apiErrorMessage(error))).toBeDefined()
  })

  it('shows an error message when the goal has no vocab deck', async () => {
    getVocabDecks.mockResolvedValue([])
    renderAtGoalRoute(1)

    expect(await screen.findByText(apiErrorMessage(undefined))).toBeDefined()
  })

  it('redirects to the quiz setup screen for the goal’s single deck', async () => {
    getVocabDecks.mockResolvedValue([makeDeck({ id: 7 })])
    renderAtGoalRoute(1)

    expect(await screen.findByText(QUIZ_SETUP_MARKER)).toBeDefined()
    expect(getVocabDecks).toHaveBeenCalledWith(1)
  })
})
