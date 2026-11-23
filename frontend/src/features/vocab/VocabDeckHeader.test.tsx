import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { VocabDeckHeader } from './VocabDeckHeader'
import type { VocabDeck } from '../../api/vocab'

const updateVocabDeck = vi.hoisted(() => vi.fn())
const deleteVocabDeck = vi.hoisted(() => vi.fn())
const generateVocabDeckQuiz = vi.hoisted(() => vi.fn())
vi.mock('../../api/vocab', () => ({ updateVocabDeck, deleteVocabDeck, generateVocabDeckQuiz }))

const getAiStatus = vi.hoisted(() => vi.fn())
vi.mock('../../api/ai', () => ({ getAiStatus }))

function makeDeck(overrides: Partial<VocabDeck> = {}): VocabDeck {
  return {
    id: 1,
    goal_id: 10,
    name: 'デッキA',
    description: '説明A',
    use_in_ai: true,
    display_order: 0,
    card_count: 0,
    mastered_card_count: 0,
    session_default_questions: 10,
    session_max_questions: 100,
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  updateVocabDeck.mockResolvedValue(makeDeck())
  deleteVocabDeck.mockResolvedValue(undefined)
  getAiStatus.mockResolvedValue({ authenticated: true, model_status: {}, login_in_progress: false })
})

afterEach(() => {
  cleanup()
})

describe('VocabDeckHeader の表示', () => {
  it('shows the name and description', () => {
    renderWithProviders(<VocabDeckHeader deck={makeDeck()} />)

    expect(screen.getByText('デッキA')).toBeDefined()
    expect(screen.getByText('説明A')).toBeDefined()
  })

  it('omits the description paragraph when there is none', () => {
    renderWithProviders(<VocabDeckHeader deck={makeDeck({ description: null })} />)

    expect(screen.queryByText('説明A')).toBeNull()
  })

  it('shows the mastered count summary', () => {
    renderWithProviders(
      <VocabDeckHeader deck={makeDeck({ card_count: 10, mastered_card_count: 3 })} />,
    )

    expect(
      screen.getByText(t('vocab.deckDetail.masteredCount', { mastered: 3, total: 10 })),
    ).toBeDefined()
  })
})

describe('VocabDeckHeader の編集', () => {
  it('sends the edited name and a null description when cleared', async () => {
    const user = userEvent.setup()
    renderWithProviders(<VocabDeckHeader deck={makeDeck()} />)

    await user.click(screen.getByRole('button', { name: t('common.action.edit') }))
    const nameInput = screen.getByLabelText(t('vocab.deckList.nameLabel'))
    await user.clear(nameInput)
    await user.type(nameInput, '新しい名前')
    await user.clear(screen.getByLabelText(t('vocab.deckList.descriptionLabel')))
    await user.click(screen.getByRole('button', { name: t('common.action.save') }))

    await waitFor(() => expect(updateVocabDeck).toHaveBeenCalledOnce())
    expect(updateVocabDeck).toHaveBeenCalledWith(1, { name: '新しい名前', description: null })
  })

  it('leaves edit mode without sending anything on cancel', async () => {
    const user = userEvent.setup()
    renderWithProviders(<VocabDeckHeader deck={makeDeck()} />)

    await user.click(screen.getByRole('button', { name: t('common.action.edit') }))
    await user.click(screen.getByRole('button', { name: t('common.action.cancel') }))

    expect(updateVocabDeck).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: t('common.action.edit') })).toBeDefined()
  })
})

describe('VocabDeckHeader のAI利用切替', () => {
  it('toggles use_in_ai immediately', async () => {
    const user = userEvent.setup()
    renderWithProviders(<VocabDeckHeader deck={makeDeck({ use_in_ai: true })} />)

    await user.click(screen.getByRole('checkbox'))

    await waitFor(() => expect(updateVocabDeck).toHaveBeenCalledWith(1, { use_in_ai: false }))
  })
})

describe('VocabDeckHeader の今日の復習の問題作り', () => {
  it('shows the AI-unconfigured notice instead of the button when AI is not configured', async () => {
    getAiStatus.mockResolvedValue({
      authenticated: false,
      model_status: {},
      login_in_progress: false,
    })
    renderWithProviders(<VocabDeckHeader deck={makeDeck()} />)

    expect(await screen.findByText(t('aiUnconfigured.message'))).toBeDefined()
    expect(
      screen.queryByRole('button', { name: t('vocab.deckDetail.generateQuizButton') }),
    ).toBeNull()
  })

  it('shows a toast with the created count on success', async () => {
    const user = userEvent.setup()
    generateVocabDeckQuiz.mockResolvedValue({ created: 3 })
    renderWithProviders(<VocabDeckHeader deck={makeDeck()} />)

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
    generateVocabDeckQuiz.mockResolvedValue({ created: 0 })
    renderWithProviders(<VocabDeckHeader deck={makeDeck()} />)

    await user.click(
      await screen.findByRole('button', { name: t('vocab.deckDetail.generateQuizButton') }),
    )

    expect(
      await screen.findByText(t('vocab.deckDetail.quizGenerateSucceededNone')),
    ).toBeDefined()
  })
})

describe('VocabDeckHeader の削除', () => {
  it('does not delete when the confirmation is dismissed', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderWithProviders(<VocabDeckHeader deck={makeDeck()} />)

    await user.click(screen.getByRole('button', { name: t('common.action.delete') }))

    expect(deleteVocabDeck).not.toHaveBeenCalled()
  })

  it('deletes after the confirmation is accepted', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderWithProviders(<VocabDeckHeader deck={makeDeck()} />)

    await user.click(screen.getByRole('button', { name: t('common.action.delete') }))

    await waitFor(() => expect(deleteVocabDeck).toHaveBeenCalledWith(1))
  })
})
