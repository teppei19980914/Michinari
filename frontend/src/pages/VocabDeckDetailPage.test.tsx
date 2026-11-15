import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { renderWithProviders } from '../test/renderWithProviders'
import { VocabDeckDetailPage } from './VocabDeckDetailPage'
import type { VocabDeck } from '../api/vocab'

const getVocabDeck = vi.hoisted(() => vi.fn())
const getVocabCards = vi.hoisted(() => vi.fn())
vi.mock('../api/vocab', () => ({
  getVocabDeck,
  getVocabCards,
  updateVocabDeck: vi.fn(),
  deleteVocabDeck: vi.fn(),
  previewVocabImport: vi.fn(),
  confirmVocabImport: vi.fn(),
  exportVocabDeck: vi.fn(),
}))

function makeDeck(overrides: Partial<VocabDeck> = {}): VocabDeck {
  return {
    id: 5,
    goal_id: 1,
    name: '資格デッキ',
    description: null,
    use_in_ai: true,
    display_order: 0,
    card_count: 0,
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  getVocabCards.mockResolvedValue([])
})

afterEach(() => {
  cleanup()
})

describe('VocabDeckDetailPage', () => {
  it('shows the loading text while fetching', () => {
    getVocabDeck.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<VocabDeckDetailPage />, { initialEntries: ['/vocab/5'] })

    expect(screen.getByText(t('common.loading'))).toBeDefined()
  })

  it('shows an error message when fetching fails', async () => {
    const error = new Error('取得失敗')
    getVocabDeck.mockRejectedValue(error)
    renderWithProviders(<VocabDeckDetailPage />, { initialEntries: ['/vocab/5'] })

    expect(await screen.findByText(apiErrorMessage(error))).toBeDefined()
  })

  it('shows the deck name and disables the start-quiz button when there are no cards', async () => {
    getVocabDeck.mockResolvedValue(makeDeck({ card_count: 0 }))
    renderWithProviders(<VocabDeckDetailPage />, { initialEntries: ['/vocab/5'] })

    expect(await screen.findByText('資格デッキ')).toBeDefined()
    expect(
      (screen.getByRole('button', { name: t('vocab.deckDetail.startQuizButton') }) as HTMLButtonElement)
        .disabled,
    ).toBe(true)
  })

  it('enables the start-quiz button when there are cards', async () => {
    getVocabDeck.mockResolvedValue(makeDeck({ card_count: 3 }))
    renderWithProviders(<VocabDeckDetailPage />, { initialEntries: ['/vocab/5'] })

    expect(
      (
        await screen.findByRole('button', { name: t('vocab.deckDetail.startQuizButton') })
      ).hasAttribute('disabled'),
    ).toBe(false)
  })
})
