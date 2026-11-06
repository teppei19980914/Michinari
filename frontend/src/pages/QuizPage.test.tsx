import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { renderWithProviders } from '../test/renderWithProviders'
import { QuizPage } from './QuizPage'

const getTodayQuiz = vi.hoisted(() => vi.fn())
const answerQuiz = vi.hoisted(() => vi.fn())
vi.mock('../api/quiz', () => ({ getTodayQuiz, answerQuiz }))

const getAiStatus = vi.hoisted(() => vi.fn())
vi.mock('../api/ai', () => ({ getAiStatus }))

describe('QuizPage', () => {
  beforeEach(() => {
    getTodayQuiz.mockReset()
    answerQuiz.mockReset()
    getAiStatus.mockReset()
    getAiStatus.mockResolvedValue({ authenticated: true, model_status: {}, login_in_progress: false })
  })

  it('shows the AI-required notice instead of the quiz session when AI is not configured', async () => {
    getAiStatus.mockResolvedValue({
      authenticated: false,
      model_status: {},
      login_in_progress: false,
    })
    getTodayQuiz.mockResolvedValue([])
    renderWithProviders(<QuizPage />)

    expect(await screen.findByText(t('quiz.aiRequiredDescription'))).toBeDefined()
    expect(screen.queryByText(t('quiz.completedTitle'))).toBeNull()
  })

  it('shows the loading text while fetching', () => {
    getTodayQuiz.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<QuizPage />)

    expect(screen.getByText(t('common.loading'))).toBeDefined()
  })

  it('shows the error message when fetching fails', async () => {
    const error = new Error('取得失敗')
    getTodayQuiz.mockRejectedValue(error)
    renderWithProviders(<QuizPage />)

    expect(await screen.findByText(apiErrorMessage(error))).toBeDefined()
  })

  it('shows the completed message when there is nothing due today', async () => {
    getTodayQuiz.mockResolvedValue([])
    renderWithProviders(<QuizPage />)

    expect(await screen.findByText(t('quiz.completedTitle'))).toBeDefined()
  })

  it('finishes the session after answering every question', async () => {
    const user = userEvent.setup()
    getTodayQuiz.mockResolvedValue([
      { id: 1, theme_id: 1, theme_name: 'テーマ', question_text: '問題', choices: ['A', 'B'] },
    ])
    answerQuiz.mockResolvedValue({
      is_correct: true,
      correct_choice_index: 0,
      explanation: '説明',
      citation_date: '2026-03-09',
      next_due_date: '2026-03-12',
    })
    renderWithProviders(<QuizPage />)

    await user.click(await screen.findByRole('button', { name: 'A' }))
    await user.click(await screen.findByRole('button', { name: t('quiz.nextButton') }))

    expect(await screen.findByText(t('quiz.completedTitle'))).toBeDefined()
  })
})
