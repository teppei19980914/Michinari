import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { apiErrorMessage } from '../../api/client'
import { VocabDeckListTab } from './VocabDeckListTab'
import type { VocabDeck } from '../../api/vocab'

const getVocabDecks = vi.hoisted(() => vi.fn())
const createVocabDeck = vi.hoisted(() => vi.fn())
const deleteVocabDeck = vi.hoisted(() => vi.fn())
const reorderVocabDecks = vi.hoisted(() => vi.fn())
vi.mock('../../api/vocab', () => ({
  getVocabDecks,
  createVocabDeck,
  deleteVocabDeck,
  reorderVocabDecks,
}))

const GOAL_ID = 1

function makeDeck(overrides: Partial<VocabDeck> = {}): VocabDeck {
  return {
    id: 1,
    goal_id: GOAL_ID,
    name: 'デッキA',
    description: null,
    use_in_ai: true,
    display_order: 0,
    card_count: 3,
    mastered_card_count: 0,
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  createVocabDeck.mockResolvedValue(makeDeck())
  deleteVocabDeck.mockResolvedValue(undefined)
  reorderVocabDecks.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
})

describe('VocabDeckListTab の一覧', () => {
  it('shows the empty message when there are no decks', async () => {
    getVocabDecks.mockResolvedValue([])
    renderWithProviders(<VocabDeckListTab goalId={GOAL_ID} />)

    expect(await screen.findByText(t('vocab.deckList.empty'))).toBeDefined()
  })

  it('shows the card count and the AI-off badge', async () => {
    getVocabDecks.mockResolvedValue([makeDeck({ use_in_ai: false, card_count: 5 })])
    renderWithProviders(<VocabDeckListTab goalId={GOAL_ID} />)

    expect(await screen.findByText(/5枚/)).toBeDefined()
    expect(screen.getByText(new RegExp(t('vocab.deckList.useInAiOffBadge')))).toBeDefined()
  })

  it('shows the mastered count', async () => {
    getVocabDecks.mockResolvedValue([makeDeck({ card_count: 5, mastered_card_count: 2 })])
    renderWithProviders(<VocabDeckListTab goalId={GOAL_ID} />)

    expect(
      await screen.findByText(
        new RegExp(t('vocab.deckList.masteredCount', { mastered: 2, total: 5 })),
      ),
    ).toBeDefined()
  })

  it('shows an error message when fetching fails', async () => {
    const error = new Error('取得失敗')
    getVocabDecks.mockRejectedValue(error)
    renderWithProviders(<VocabDeckListTab goalId={GOAL_ID} />)

    expect(await screen.findByText(apiErrorMessage(error))).toBeDefined()
  })
})

describe('VocabDeckListTab の作成', () => {
  it('creates a deck with a null description when left blank', async () => {
    const user = userEvent.setup()
    getVocabDecks.mockResolvedValue([])
    renderWithProviders(<VocabDeckListTab goalId={GOAL_ID} />)

    await user.click(await screen.findByRole('button', { name: t('vocab.deckList.addTitle') }))
    await user.type(screen.getByLabelText(t('vocab.deckList.nameLabel')), '新しいデッキ')
    await user.click(screen.getByRole('button', { name: t('common.action.save') }))

    await waitFor(() => expect(createVocabDeck).toHaveBeenCalledOnce())
    expect(createVocabDeck).toHaveBeenCalledWith(GOAL_ID, {
      name: '新しいデッキ',
      description: null,
    })
  })

  it('includes the description when provided', async () => {
    const user = userEvent.setup()
    getVocabDecks.mockResolvedValue([])
    renderWithProviders(<VocabDeckListTab goalId={GOAL_ID} />)

    await user.click(await screen.findByRole('button', { name: t('vocab.deckList.addTitle') }))
    await user.type(screen.getByLabelText(t('vocab.deckList.nameLabel')), '新しいデッキ')
    await user.type(screen.getByLabelText(t('vocab.deckList.descriptionLabel')), '説明文')
    await user.click(screen.getByRole('button', { name: t('common.action.save') }))

    await waitFor(() =>
      expect(createVocabDeck).toHaveBeenCalledWith(GOAL_ID, {
        name: '新しいデッキ',
        description: '説明文',
      }),
    )
  })

  it('closes the form without creating anything on cancel', async () => {
    const user = userEvent.setup()
    getVocabDecks.mockResolvedValue([])
    renderWithProviders(<VocabDeckListTab goalId={GOAL_ID} />)

    await user.click(await screen.findByRole('button', { name: t('vocab.deckList.addTitle') }))
    await user.click(screen.getByRole('button', { name: t('common.action.cancel') }))

    expect(createVocabDeck).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: t('vocab.deckList.addTitle') })).toBeDefined()
  })
})

describe('VocabDeckListTab の削除', () => {
  it('does not delete when the confirmation is dismissed', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    getVocabDecks.mockResolvedValue([makeDeck()])
    renderWithProviders(<VocabDeckListTab goalId={GOAL_ID} />)

    await user.click(await screen.findByRole('button', { name: t('common.action.delete') }))

    expect(deleteVocabDeck).not.toHaveBeenCalled()
  })

  it('deletes only after the confirmation is accepted', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    getVocabDecks.mockResolvedValue([makeDeck()])
    renderWithProviders(<VocabDeckListTab goalId={GOAL_ID} />)

    await user.click(await screen.findByRole('button', { name: t('common.action.delete') }))

    await waitFor(() => expect(deleteVocabDeck).toHaveBeenCalledWith(1))
  })
})

describe('VocabDeckListTab の並び替え', () => {
  it('disables moving the first deck up and the last deck down', async () => {
    getVocabDecks.mockResolvedValue([makeDeck({ id: 1 }), makeDeck({ id: 2 })])
    renderWithProviders(<VocabDeckListTab goalId={GOAL_ID} />)

    const upButtons = await screen.findAllByRole('button', { name: t('vocab.deckList.moveUp') })
    const downButtons = screen.getAllByRole('button', { name: t('vocab.deckList.moveDown') })
    expect((upButtons[0] as HTMLButtonElement).disabled).toBe(true)
    expect((downButtons[1] as HTMLButtonElement).disabled).toBe(true)
  })

  it('swaps the clicked deck with the one above it', async () => {
    const user = userEvent.setup()
    getVocabDecks.mockResolvedValue([makeDeck({ id: 1 }), makeDeck({ id: 2 })])
    renderWithProviders(<VocabDeckListTab goalId={GOAL_ID} />)

    const downButtons = await screen.findAllByRole('button', { name: t('vocab.deckList.moveDown') })
    await user.click(downButtons[0])

    await waitFor(() => expect(reorderVocabDecks).toHaveBeenCalledWith(GOAL_ID, [2, 1]))
  })

  it('swaps the second deck with the one above it when moving up', async () => {
    const user = userEvent.setup()
    getVocabDecks.mockResolvedValue([makeDeck({ id: 1 }), makeDeck({ id: 2 })])
    renderWithProviders(<VocabDeckListTab goalId={GOAL_ID} />)

    const upButtons = await screen.findAllByRole('button', { name: t('vocab.deckList.moveUp') })
    await user.click(upButtons[1])

    await waitFor(() => expect(reorderVocabDecks).toHaveBeenCalledWith(GOAL_ID, [2, 1]))
  })

  it('does not move when already at the boundary', async () => {
    getVocabDecks.mockResolvedValue([makeDeck({ id: 1 })])
    renderWithProviders(<VocabDeckListTab goalId={GOAL_ID} />)

    const upButton = await screen.findByRole('button', { name: t('vocab.deckList.moveUp') })
    expect((upButton as HTMLButtonElement).disabled).toBe(true)
  })
})
