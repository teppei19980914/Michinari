import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { AddVocabTermButton } from './AddVocabTermButton'
import type { VocabCard, VocabDeck } from '../../api/vocab'

const getVocabDecks = vi.hoisted(() => vi.fn())
const createVocabCard = vi.hoisted(() => vi.fn())
vi.mock('../../api/vocab', () => ({ getVocabDecks, createVocabCard }))

const GOAL_ID = 1

function makeDeck(id: number, name = 'デッキA'): VocabDeck {
  return {
    id,
    goal_id: GOAL_ID,
    name,
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
  }
}

function makeCard(): VocabCard {
  return {
    id: 1,
    deck_id: 1,
    card_type: 'TERM',
    term: '用語',
    meaning: '意味',
    aliases: null,
    note: null,
    situation_text: null,
    question_text: null,
    is_checked: false,
    display_order: 0,
    correct_count: 0,
    incorrect_count: 0,
    accuracy_percent: null,
    consecutive_incorrect: 0,
    last_answered_at: null,
    is_mastered: false,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  createVocabCard.mockResolvedValue(makeCard())
})

afterEach(() => {
  cleanup()
})

describe('AddVocabTermButton', () => {
  it('shows the no-deck notice when the goal has no decks', async () => {
    getVocabDecks.mockResolvedValue([])
    renderWithProviders(<AddVocabTermButton goalId={GOAL_ID} />)

    expect(await screen.findByText(t('vocab.suggestions.manualAddNoDeckNotice'))).toBeTruthy()
    expect(
      screen.queryByRole('button', { name: t('vocab.suggestions.manualAddButton') }),
    ).toBeNull()
  })

  it('opens the add form and creates a card with the chosen deck', async () => {
    getVocabDecks.mockResolvedValue([makeDeck(1, 'デッキA'), makeDeck(2, 'デッキB')])
    const user = userEvent.setup()
    renderWithProviders(<AddVocabTermButton goalId={GOAL_ID} />)

    await user.click(
      await screen.findByRole('button', { name: t('vocab.suggestions.manualAddButton') }),
    )
    await user.selectOptions(screen.getByLabelText(t('vocab.suggestions.deckLabel')), 'デッキB')
    await user.type(screen.getByLabelText(t('vocab.suggestions.termLabel')), 'TCP')
    await user.type(screen.getByLabelText(t('vocab.suggestions.meaningLabel')), '通信の仕組み')
    await user.click(screen.getByRole('button', { name: t('common.action.save') }))

    await waitFor(() =>
      expect(createVocabCard).toHaveBeenCalledWith(2, {
        term: 'TCP',
        meaning: '通信の仕組み',
        aliases: null,
      }),
    )
  })

  it('closes the form without creating anything on cancel', async () => {
    getVocabDecks.mockResolvedValue([makeDeck(1)])
    const user = userEvent.setup()
    renderWithProviders(<AddVocabTermButton goalId={GOAL_ID} />)

    await user.click(
      await screen.findByRole('button', { name: t('vocab.suggestions.manualAddButton') }),
    )
    await user.click(screen.getByRole('button', { name: t('common.action.cancel') }))

    expect(createVocabCard).not.toHaveBeenCalled()
    expect(
      await screen.findByRole('button', { name: t('vocab.suggestions.manualAddButton') }),
    ).toBeTruthy()
  })
})
