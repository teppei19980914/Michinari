import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../locales/t'
import { renderWithProviders } from '../test/renderWithProviders'
import { VocabQuizPage } from './VocabQuizPage'
import type { VocabDeck } from '../api/vocab'

const getVocabDeck = vi.hoisted(() => vi.fn())
const startVocabQuizSession = vi.hoisted(() => vi.fn())
const answerVocabCard = vi.hoisted(() => vi.fn())
const checkVocabCard = vi.hoisted(() => vi.fn())
vi.mock('../api/vocab', () => ({
  getVocabDeck,
  startVocabQuizSession,
  answerVocabCard,
  checkVocabCard,
}))

function makeDeck(overrides: Partial<VocabDeck> = {}): VocabDeck {
  return {
    id: 5,
    goal_id: 1,
    name: '資格デッキ',
    description: null,
    use_in_ai: true,
    display_order: 0,
    card_count: 10,
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  getVocabDeck.mockResolvedValue(makeDeck())
})

afterEach(() => {
  cleanup()
})

describe('VocabQuizPage', () => {
  it('shows the setup form first, then the question, then the summary', async () => {
    const user = userEvent.setup()
    startVocabQuizSession.mockResolvedValue({
      questions: [{ card_id: 1, prompt: '用語A', reveal: '意味A' }],
      excluded_count: 0,
    })
    answerVocabCard.mockResolvedValue({ is_correct: true })
    renderWithProviders(<VocabQuizPage />)

    await screen.findByRole('button', { name: t('vocab.quiz.startButton') })
    await user.click(screen.getByRole('button', { name: t('vocab.quiz.startButton') }))

    await user.click(await screen.findByRole('button', { name: t('vocab.quiz.revealButton') }))
    await user.click(screen.getByRole('button', { name: t('vocab.quiz.knewItButton') }))

    expect(await screen.findByText(t('vocab.quiz.completedTitle'))).toBeDefined()
    expect(screen.getByText(t('vocab.quiz.scoreLabel', { correct: 1, total: 1 }))).toBeDefined()
  })

  it('shows a notice when the session has no questions', async () => {
    const user = userEvent.setup()
    startVocabQuizSession.mockResolvedValue({ questions: [], excluded_count: 0 })
    renderWithProviders(<VocabQuizPage />)

    await user.click(await screen.findByRole('button', { name: t('vocab.quiz.startButton') }))

    expect(await screen.findByText(t('vocab.quiz.noQuestionsNotice'))).toBeDefined()
  })
})
