import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { apiErrorMessage } from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { VocabDeckWordsTab } from './VocabDeckWordsTab'
import type { VocabDeck } from '../../api/vocab'

const getVocabDecks = vi.hoisted(() => vi.fn())
const updateVocabDeck = vi.hoisted(() => vi.fn())
const generateVocabDeckQuiz = vi.hoisted(() => vi.fn())
const getVocabCards = vi.hoisted(() => vi.fn())
vi.mock('../../api/vocab', () => ({
  getVocabDecks,
  updateVocabDeck,
  generateVocabDeckQuiz,
  getVocabCards,
  createVocabCard: vi.fn(),
  updateVocabCard: vi.fn(),
  deleteVocabCard: vi.fn(),
  checkVocabCard: vi.fn(),
  previewVocabImport: vi.fn(),
  confirmVocabImport: vi.fn(),
  exportVocabDeck: vi.fn(),
}))

const getAiStatus = vi.hoisted(() => vi.fn())
vi.mock('../../api/ai', () => ({ getAiStatus }))

function makeDeck(overrides: Partial<VocabDeck> = {}): VocabDeck {
  return {
    id: 1,
    goal_id: 10,
    name: 'デッキA',
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

beforeEach(() => {
  vi.clearAllMocks()
  getVocabCards.mockResolvedValue([])
  updateVocabDeck.mockResolvedValue(makeDeck())
  getAiStatus.mockResolvedValue({ authenticated: true, model_status: {}, login_in_progress: false })
})

afterEach(() => {
  cleanup()
})

describe('VocabDeckWordsTab の表示', () => {
  it('shows the loading text while fetching', () => {
    getVocabDecks.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<VocabDeckWordsTab goalId={10} />)

    expect(screen.getByText(t('common.loading'))).toBeDefined()
  })

  it('shows an error message when fetching fails', async () => {
    const error = new Error('取得失敗')
    getVocabDecks.mockRejectedValue(error)
    renderWithProviders(<VocabDeckWordsTab goalId={10} />)

    expect(await screen.findByText(apiErrorMessage(error))).toBeDefined()
  })

  it('shows an error message when the goal has no deck yet (should not normally happen)', async () => {
    getVocabDecks.mockResolvedValue([])
    renderWithProviders(<VocabDeckWordsTab goalId={10} />)

    expect(await screen.findByText(apiErrorMessage(undefined))).toBeDefined()
  })

  it('shows the mastered count summary', async () => {
    getVocabDecks.mockResolvedValue([makeDeck({ card_count: 10, mastered_card_count: 3 })])
    renderWithProviders(<VocabDeckWordsTab goalId={10} />)

    expect(
      await screen.findByText(t('vocab.deckDetail.masteredCount', { mastered: 3, total: 10 })),
    ).toBeDefined()
  })

  it('does not show a deck name or description, since the deck itself is hidden from users', async () => {
    getVocabDecks.mockResolvedValue([makeDeck({ name: 'デッキA' })])
    renderWithProviders(<VocabDeckWordsTab goalId={10} />)

    await screen.findByText(t('vocab.deckDetail.masteredCount', { mastered: 0, total: 0 }))
    expect(screen.queryByText('デッキA')).toBeNull()
    expect(screen.queryByRole('button', { name: t('common.action.delete') })).toBeNull()
  })
})

describe('VocabDeckWordsTab のAI利用切替', () => {
  it('toggles use_in_ai immediately', async () => {
    const user = userEvent.setup()
    getVocabDecks.mockResolvedValue([makeDeck({ use_in_ai: true })])
    renderWithProviders(<VocabDeckWordsTab goalId={10} />)

    await user.click(await screen.findByRole('checkbox'))

    await waitFor(() => expect(updateVocabDeck).toHaveBeenCalledWith(1, { use_in_ai: false }))
  })
})

describe('VocabDeckWordsTab の今日の復習の問題作り', () => {
  it('shows the AI-unconfigured notice instead of the button when AI is not configured', async () => {
    getAiStatus.mockResolvedValue({
      authenticated: false,
      model_status: {},
      login_in_progress: false,
    })
    getVocabDecks.mockResolvedValue([makeDeck()])
    renderWithProviders(<VocabDeckWordsTab goalId={10} />)

    expect(await screen.findByText(t('aiUnconfigured.message'))).toBeDefined()
    expect(
      screen.queryByRole('button', { name: t('vocab.deckDetail.generateQuizButton') }),
    ).toBeNull()
  })

  it('shows a toast with the created count on success', async () => {
    const user = userEvent.setup()
    getVocabDecks.mockResolvedValue([makeDeck()])
    generateVocabDeckQuiz.mockResolvedValue({ created: 3 })
    renderWithProviders(<VocabDeckWordsTab goalId={10} />)

    await user.click(
      await screen.findByRole('button', { name: t('vocab.deckDetail.generateQuizButton') }),
    )

    expect(generateVocabDeckQuiz).toHaveBeenCalledWith(1)
    expect(
      await screen.findByText(t('vocab.deckDetail.quizGenerateSucceeded', { count: 3 })),
    ).toBeDefined()
  })

  it('shows a toast saying nothing was created when created is zero', async () => {
    const user = userEvent.setup()
    getVocabDecks.mockResolvedValue([makeDeck()])
    generateVocabDeckQuiz.mockResolvedValue({ created: 0 })
    renderWithProviders(<VocabDeckWordsTab goalId={10} />)

    await user.click(
      await screen.findByRole('button', { name: t('vocab.deckDetail.generateQuizButton') }),
    )

    expect(
      await screen.findByText(t('vocab.deckDetail.quizGenerateSucceededNone')),
    ).toBeDefined()
  })
})
