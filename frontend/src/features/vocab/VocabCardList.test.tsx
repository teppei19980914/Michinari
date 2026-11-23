import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { apiErrorMessage } from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { VocabCardList } from './VocabCardList'
import type { VocabCard } from '../../api/vocab'

const getVocabCards = vi.hoisted(() => vi.fn())
const createVocabCard = vi.hoisted(() => vi.fn())
const updateVocabCard = vi.hoisted(() => vi.fn())
const deleteVocabCard = vi.hoisted(() => vi.fn())
const checkVocabCard = vi.hoisted(() => vi.fn())
vi.mock('../../api/vocab', () => ({
  getVocabCards,
  createVocabCard,
  updateVocabCard,
  deleteVocabCard,
  checkVocabCard,
}))

const DECK_ID = 1

function makeCard(overrides: Partial<VocabCard> = {}): VocabCard {
  return {
    id: 1,
    deck_id: DECK_ID,
    card_type: 'TERM',
    term: '用語A',
    meaning: '意味A',
    aliases: null,
    note: null,
    situation_text: null,
    question_text: null,
    is_checked: false,
    display_order: 0,
    correct_count: 2,
    incorrect_count: 1,
    accuracy_percent: 66.6,
    consecutive_incorrect: 0,
    last_answered_at: null,
    is_mastered: false,
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  getVocabCards.mockResolvedValue([])
  createVocabCard.mockResolvedValue(makeCard())
  updateVocabCard.mockResolvedValue(makeCard())
  deleteVocabCard.mockResolvedValue(undefined)
  checkVocabCard.mockResolvedValue(makeCard({ is_checked: true }))
})

afterEach(() => {
  cleanup()
})

describe('VocabCardList の一覧表示', () => {
  it('shows the loading text while fetching', () => {
    getVocabCards.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)

    expect(screen.getByText(t('common.loading'))).toBeDefined()
  })

  it('shows an error message when fetching fails', async () => {
    const error = new Error('取得失敗')
    getVocabCards.mockRejectedValue(error)
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)

    expect(await screen.findByText(apiErrorMessage(error))).toBeDefined()
  })

  it('shows the empty message when there are no cards', async () => {
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)

    expect(await screen.findByText(t('vocab.deckDetail.cardsEmpty'))).toBeDefined()
  })

  it('shows "—" for accuracy when the card has never been answered', async () => {
    getVocabCards.mockResolvedValue([makeCard({ accuracy_percent: null, correct_count: 0, incorrect_count: 0 })])
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)

    expect(await screen.findByText(/正答率 —/)).toBeDefined()
  })

  it('rounds the accuracy percentage', async () => {
    getVocabCards.mockResolvedValue([makeCard({ accuracy_percent: 66.6 })])
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)

    expect(await screen.findByText(/正答率 67%/)).toBeDefined()
  })

  it('shows the mastered badge for a mastered card', async () => {
    getVocabCards.mockResolvedValue([makeCard({ is_mastered: true })])
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)

    expect(await screen.findByText(t('vocab.deckDetail.masteredBadge'))).toBeDefined()
  })

  it('does not show the mastered badge for an unmastered card', async () => {
    getVocabCards.mockResolvedValue([makeCard({ is_mastered: false })])
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)

    await screen.findByText('用語A')
    expect(screen.queryByText(t('vocab.deckDetail.masteredBadge'))).toBeNull()
  })

  it('shows the situation badge and the situation text (not meaning) for a situation card', async () => {
    getVocabCards.mockResolvedValue([
      makeCard({
        card_type: 'SITUATION',
        term: '見出しA',
        meaning: '最善の対応A',
        situation_text: '状況A',
      }),
    ])
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)

    expect(await screen.findByText('見出しA')).toBeTruthy()
    expect(screen.getByText('状況A')).toBeTruthy()
    expect(screen.queryByText('最善の対応A')).toBeNull()
  })

  it('re-fetches with the chosen card type filter', async () => {
    const user = userEvent.setup()
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)
    await waitFor(() =>
      expect(getVocabCards).toHaveBeenCalledWith(DECK_ID, 'ALL', 'REGISTERED', undefined),
    )

    await user.selectOptions(
      screen.getByLabelText(t('vocab.deckDetail.cardTypeFilterLabel')),
      t('vocab.deckDetail.cardTypeOptions.SITUATION'),
    )

    await waitFor(() =>
      expect(getVocabCards).toHaveBeenCalledWith(DECK_ID, 'ALL', 'REGISTERED', 'SITUATION'),
    )
  })

  it('re-fetches with the chosen filter and sort', async () => {
    const user = userEvent.setup()
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)
    await waitFor(() =>
      expect(getVocabCards).toHaveBeenCalledWith(DECK_ID, 'ALL', 'REGISTERED', undefined),
    )

    await user.selectOptions(
      screen.getByLabelText(t('vocab.deckDetail.filterLabel')),
      t('vocab.deckDetail.filterOptions.WEAK'),
    )

    await waitFor(() =>
      expect(getVocabCards).toHaveBeenCalledWith(DECK_ID, 'WEAK', 'REGISTERED', undefined),
    )
  })

  it('re-fetches with the chosen sort', async () => {
    const user = userEvent.setup()
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)
    await waitFor(() =>
      expect(getVocabCards).toHaveBeenCalledWith(DECK_ID, 'ALL', 'REGISTERED', undefined),
    )

    await user.selectOptions(
      screen.getByLabelText(t('vocab.deckDetail.sortLabel')),
      t('vocab.deckDetail.sortOptions.ACCURACY_ASC'),
    )

    await waitFor(() =>
      expect(getVocabCards).toHaveBeenCalledWith(DECK_ID, 'ALL', 'ACCURACY_ASC', undefined),
    )
  })
})

describe('VocabCardList の追加', () => {
  it('creates a card with null aliases/note when left blank', async () => {
    const user = userEvent.setup()
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)

    await user.click(await screen.findByRole('button', { name: t('vocab.deckDetail.addCardTitle') }))
    await user.type(screen.getByLabelText(t('vocab.deckDetail.termLabel')), '用語B')
    await user.type(screen.getByLabelText(t('vocab.deckDetail.meaningLabel')), '意味B')
    await user.click(screen.getByRole('button', { name: t('common.action.save') }))

    await waitFor(() => expect(createVocabCard).toHaveBeenCalledOnce())
    expect(createVocabCard).toHaveBeenCalledWith(DECK_ID, {
      term: '用語B',
      meaning: '意味B',
      aliases: null,
      note: null,
      card_type: 'TERM',
    })
  })

  it('includes aliases and note when provided', async () => {
    const user = userEvent.setup()
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)

    await user.click(await screen.findByRole('button', { name: t('vocab.deckDetail.addCardTitle') }))
    await user.type(screen.getByLabelText(t('vocab.deckDetail.termLabel')), '用語B')
    await user.type(screen.getByLabelText(t('vocab.deckDetail.meaningLabel')), '意味B')
    await user.type(screen.getByLabelText(t('vocab.deckDetail.aliasesLabel')), '別名B')
    await user.type(screen.getByLabelText(t('vocab.deckDetail.noteLabel')), '補足B')
    await user.click(screen.getByRole('button', { name: t('common.action.save') }))

    await waitFor(() =>
      expect(createVocabCard).toHaveBeenCalledWith(DECK_ID, {
        term: '用語B',
        meaning: '意味B',
        aliases: '別名B',
        note: '補足B',
        card_type: 'TERM',
      }),
    )
  })

  it('shows situation fields and hides term/aliases fields after switching the type', async () => {
    const user = userEvent.setup()
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)

    await user.click(await screen.findByRole('button', { name: t('vocab.deckDetail.addCardTitle') }))
    await user.selectOptions(
      screen.getByLabelText(t('vocab.deckDetail.cardTypeLabel')),
      t('vocab.deckDetail.cardTypeOptions.SITUATION'),
    )

    expect(screen.getByLabelText(t('vocab.deckDetail.headingLabel'))).toBeTruthy()
    expect(screen.getByLabelText(t('vocab.deckDetail.situationTextLabel'))).toBeTruthy()
    expect(screen.getByLabelText(t('vocab.deckDetail.bestActionLabel'))).toBeTruthy()
    expect(screen.queryByLabelText(t('vocab.deckDetail.aliasesLabel'))).toBeNull()
  })

  it('creates a situation card with the situation fields', async () => {
    const user = userEvent.setup()
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)

    await user.click(await screen.findByRole('button', { name: t('vocab.deckDetail.addCardTitle') }))
    await user.selectOptions(
      screen.getByLabelText(t('vocab.deckDetail.cardTypeLabel')),
      t('vocab.deckDetail.cardTypeOptions.SITUATION'),
    )
    await user.type(screen.getByLabelText(t('vocab.deckDetail.headingLabel')), '見出しB')
    await user.type(screen.getByLabelText(t('vocab.deckDetail.situationTextLabel')), '状況B')
    await user.type(screen.getByLabelText(t('vocab.deckDetail.questionTextLabel')), '問いB')
    await user.type(screen.getByLabelText(t('vocab.deckDetail.bestActionLabel')), '最善の対応B')
    await user.type(screen.getByLabelText(t('vocab.deckDetail.explanationLabel')), '解説B')
    await user.click(screen.getByRole('button', { name: t('common.action.save') }))

    await waitFor(() =>
      expect(createVocabCard).toHaveBeenCalledWith(DECK_ID, {
        term: '見出しB',
        meaning: '最善の対応B',
        note: '解説B',
        situation_text: '状況B',
        question_text: '問いB',
        card_type: 'SITUATION',
      }),
    )
  })

  it('creates a situation card with null question/explanation when left blank', async () => {
    const user = userEvent.setup()
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)

    await user.click(await screen.findByRole('button', { name: t('vocab.deckDetail.addCardTitle') }))
    await user.selectOptions(
      screen.getByLabelText(t('vocab.deckDetail.cardTypeLabel')),
      t('vocab.deckDetail.cardTypeOptions.SITUATION'),
    )
    await user.type(screen.getByLabelText(t('vocab.deckDetail.headingLabel')), '見出しC')
    await user.type(screen.getByLabelText(t('vocab.deckDetail.situationTextLabel')), '状況C')
    await user.type(screen.getByLabelText(t('vocab.deckDetail.bestActionLabel')), '最善の対応C')
    await user.click(screen.getByRole('button', { name: t('common.action.save') }))

    await waitFor(() =>
      expect(createVocabCard).toHaveBeenCalledWith(DECK_ID, {
        term: '見出しC',
        meaning: '最善の対応C',
        note: null,
        situation_text: '状況C',
        question_text: null,
        card_type: 'SITUATION',
      }),
    )
  })

  it('closes the form without creating anything on cancel', async () => {
    const user = userEvent.setup()
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)

    await user.click(await screen.findByRole('button', { name: t('vocab.deckDetail.addCardTitle') }))
    await user.click(screen.getByRole('button', { name: t('common.action.cancel') }))

    expect(createVocabCard).not.toHaveBeenCalled()
  })
})

describe('VocabCardList の編集・チェック・削除', () => {
  it('pre-fills the edit form and sends the update', async () => {
    const user = userEvent.setup()
    getVocabCards.mockResolvedValue([makeCard()])
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)

    await user.click(await screen.findByRole('button', { name: t('common.action.edit') }))
    const termInput = screen.getByLabelText(t('vocab.deckDetail.termLabel')) as HTMLInputElement
    expect(termInput.value).toBe('用語A')
    await user.clear(termInput)
    await user.type(termInput, '用語A改')
    await user.click(screen.getByRole('button', { name: t('common.action.save') }))

    await waitFor(() =>
      expect(updateVocabCard).toHaveBeenCalledWith(1, {
        term: '用語A改',
        meaning: '意味A',
        aliases: null,
        note: null,
      }),
    )
  })

  it('shows the fixed-type notice (no selector) when editing a situation card', async () => {
    const user = userEvent.setup()
    getVocabCards.mockResolvedValue([
      makeCard({
        card_type: 'SITUATION',
        term: '見出しA',
        meaning: '最善の対応A',
        situation_text: '状況A',
        aliases: null,
      }),
    ])
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)

    await user.click(await screen.findByRole('button', { name: t('common.action.edit') }))

    expect(screen.queryByLabelText(t('vocab.deckDetail.cardTypeLabel'))).toBeNull()
    expect(screen.getByLabelText(t('vocab.deckDetail.headingLabel'))).toBeTruthy()
  })

  it('toggles the checked state', async () => {
    const user = userEvent.setup()
    getVocabCards.mockResolvedValue([makeCard({ is_checked: false })])
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)

    await user.click(await screen.findByRole('checkbox'))

    await waitFor(() => expect(checkVocabCard).toHaveBeenCalledWith(1, true))
  })

  it('deletes only after the confirmation is accepted', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    getVocabCards.mockResolvedValue([makeCard()])
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)

    await user.click(await screen.findByRole('button', { name: t('common.action.delete') }))

    await waitFor(() => expect(deleteVocabCard).toHaveBeenCalledWith(1))
  })

  it('does not delete when the confirmation is dismissed', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    getVocabCards.mockResolvedValue([makeCard()])
    renderWithProviders(<VocabCardList deckId={DECK_ID} />)

    await user.click(await screen.findByRole('button', { name: t('common.action.delete') }))

    expect(deleteVocabCard).not.toHaveBeenCalled()
  })
})
