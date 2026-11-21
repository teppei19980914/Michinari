import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { TodayVocabSuggestionsCard } from './TodayVocabSuggestionsCard'
import type { VocabCard, VocabDeck, VocabTermSuggestion } from '../../api/vocab'

const getAiStatus = vi.hoisted(() => vi.fn())
vi.mock('../../api/ai', () => ({ getAiStatus }))

const getVocabDecks = vi.hoisted(() => vi.fn())
const getVocabTermSuggestions = vi.hoisted(() => vi.fn())
const acceptVocabTermSuggestion = vi.hoisted(() => vi.fn())
const dismissVocabTermSuggestion = vi.hoisted(() => vi.fn())
vi.mock('../../api/vocab', () => ({
  getVocabDecks,
  getVocabTermSuggestions,
  acceptVocabTermSuggestion,
  dismissVocabTermSuggestion,
}))

const GOAL_ID = 1
const RECORD_DATE = '2026-11-20'

function makeDeck(id: number, name = 'デッキA'): VocabDeck {
  return {
    id,
    goal_id: GOAL_ID,
    name,
    description: null,
    use_in_ai: true,
    display_order: 0,
    card_count: 0,
  }
}

function makeSuggestion(overrides: Partial<VocabTermSuggestion> = {}): VocabTermSuggestion {
  return {
    id: 1,
    goal_id: GOAL_ID,
    record_date: RECORD_DATE,
    term: 'TCP',
    source_sentence: 'TCPの仕組みを学んだ',
    ...overrides,
  }
}

function makeCard(): VocabCard {
  return {
    id: 1,
    deck_id: 1,
    term: 'TCP',
    meaning: '通信の仕組み',
    aliases: null,
    note: null,
    is_checked: false,
    display_order: 0,
    correct_count: 0,
    incorrect_count: 0,
    accuracy_percent: null,
    consecutive_incorrect: 0,
    last_answered_at: null,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  getAiStatus.mockResolvedValue({ authenticated: true, model_status: {}, login_in_progress: false })
  getVocabDecks.mockResolvedValue([])
  getVocabTermSuggestions.mockResolvedValue({ suggestions: [], default_deck_id: null })
  acceptVocabTermSuggestion.mockResolvedValue(makeCard())
  dismissVocabTermSuggestion.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
})

describe('TodayVocabSuggestionsCard', () => {
  it('renders nothing when AI is not configured', async () => {
    getAiStatus.mockResolvedValue({
      authenticated: false,
      model_status: {},
      login_in_progress: false,
    })
    renderWithProviders(<TodayVocabSuggestionsCard goalId={GOAL_ID} recordDate={RECORD_DATE} />)

    await waitFor(() => expect(getAiStatus).toHaveBeenCalled())
    expect(screen.queryByText(t('vocab.suggestions.title'))).toBeNull()
    expect(screen.queryByText(t('vocab.suggestions.noDeckNotice'))).toBeNull()
    expect(getVocabTermSuggestions).not.toHaveBeenCalled()
  })

  it('shows the no-deck notice and never fetches suggestions when the goal has no decks', async () => {
    getVocabDecks.mockResolvedValue([])
    renderWithProviders(<TodayVocabSuggestionsCard goalId={GOAL_ID} recordDate={RECORD_DATE} />)

    expect(await screen.findByText(t('vocab.suggestions.noDeckNotice'))).toBeTruthy()
    expect(getVocabTermSuggestions).not.toHaveBeenCalled()
  })

  it('renders nothing when there are no pending suggestions', async () => {
    getVocabDecks.mockResolvedValue([makeDeck(1)])
    getVocabTermSuggestions.mockResolvedValue({ suggestions: [], default_deck_id: 1 })
    renderWithProviders(<TodayVocabSuggestionsCard goalId={GOAL_ID} recordDate={RECORD_DATE} />)

    await waitFor(() => expect(getVocabTermSuggestions).toHaveBeenCalledWith(GOAL_ID, RECORD_DATE))
    expect(screen.queryByText(t('vocab.suggestions.title'))).toBeNull()
  })

  it('pre-fills the form from the suggestion and default deck, then accepts it', async () => {
    getVocabDecks.mockResolvedValue([makeDeck(1, 'デッキA'), makeDeck(2, 'デッキB')])
    getVocabTermSuggestions.mockResolvedValue({
      suggestions: [makeSuggestion()],
      default_deck_id: 2,
    })
    const user = userEvent.setup()
    renderWithProviders(<TodayVocabSuggestionsCard goalId={GOAL_ID} recordDate={RECORD_DATE} />)

    expect(await screen.findByText(t('vocab.suggestions.title'))).toBeTruthy()
    const termInput = screen.getByLabelText(t('vocab.suggestions.termLabel')) as HTMLInputElement
    expect(termInput.value).toBe('TCP')
    const meaningInput = screen.getByLabelText(
      t('vocab.suggestions.meaningLabel'),
    ) as HTMLTextAreaElement
    expect(meaningInput.value).toBe('TCPの仕組みを学んだ')
    const deckSelect = screen.getByLabelText(t('vocab.suggestions.deckLabel')) as HTMLSelectElement
    expect(deckSelect.value).toBe('2')

    await user.click(screen.getByRole('button', { name: t('vocab.suggestions.addButton') }))

    await waitFor(() =>
      expect(acceptVocabTermSuggestion).toHaveBeenCalledWith(GOAL_ID, 1, {
        deck_id: 2,
        term: 'TCP',
        meaning: 'TCPの仕組みを学んだ',
        aliases: null,
      }),
    )
  })

  it('dismisses a suggestion', async () => {
    getVocabDecks.mockResolvedValue([makeDeck(1)])
    getVocabTermSuggestions.mockResolvedValue({
      suggestions: [makeSuggestion()],
      default_deck_id: 1,
    })
    const user = userEvent.setup()
    renderWithProviders(<TodayVocabSuggestionsCard goalId={GOAL_ID} recordDate={RECORD_DATE} />)

    await user.click(
      await screen.findByRole('button', { name: t('vocab.suggestions.dismissButton') }),
    )

    await waitFor(() => expect(dismissVocabTermSuggestion).toHaveBeenCalledWith(GOAL_ID, 1))
  })

  it('renders one card per suggestion and falls back to the first deck without a default', async () => {
    getVocabDecks.mockResolvedValue([makeDeck(1, 'デッキA')])
    getVocabTermSuggestions.mockResolvedValue({
      suggestions: [makeSuggestion({ id: 1, term: 'TCP' }), makeSuggestion({ id: 2, term: 'UDP' })],
      default_deck_id: null,
    })
    renderWithProviders(<TodayVocabSuggestionsCard goalId={GOAL_ID} recordDate={RECORD_DATE} />)

    expect(await screen.findAllByRole('button', { name: t('vocab.suggestions.addButton') })).toHaveLength(2)
    const deckSelects = screen.getAllByLabelText(
      t('vocab.suggestions.deckLabel'),
    ) as HTMLSelectElement[]
    expect(deckSelects.every((select) => select.value === '1')).toBe(true)
  })
})
