import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { apiErrorMessage } from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { QuizSession } from './QuizSession'
import type { QuizQuestion } from '../../api/quiz'

const answerQuiz = vi.hoisted(() => vi.fn())
vi.mock('../../api/quiz', () => ({ answerQuiz }))

const QUESTIONS: QuizQuestion[] = [
  {
    id: 1,
    theme_id: 10,
    theme_name: 'メール関連',
    question_text: 'SMTPの役割は？',
    choices: ['送信', '受信のみ', '暗号化', '圧縮'],
  },
  {
    id: 2,
    theme_id: 10,
    theme_name: 'メール関連',
    question_text: 'SPFの役割は？',
    choices: ['送信元検証', '暗号化', '圧縮', '受信'],
  },
]

describe('QuizSession', () => {
  beforeEach(() => {
    answerQuiz.mockReset()
  })

  it('shows the result and advances to the next question', async () => {
    const user = userEvent.setup()
    answerQuiz.mockResolvedValue({
      is_correct: true,
      correct_choice_index: 0,
      explanation: 'SMTPは送信を担う',
      citation_date: '2026-03-09',
      next_due_date: '2026-03-12',
    })
    const onFinished = vi.fn()
    renderWithProviders(<QuizSession questions={QUESTIONS} onFinished={onFinished} />)

    await user.click(screen.getByRole('button', { name: '送信' }))

    expect(await screen.findByText(t('quiz.correctLabel'))).toBeDefined()
    expect(screen.getByText('SMTPは送信を担う')).toBeDefined()
    expect(answerQuiz).toHaveBeenCalledWith(1, 0)

    await user.click(screen.getByRole('button', { name: t('quiz.nextButton') }))

    expect(screen.getByText('SPFの役割は？')).toBeDefined()
    expect(onFinished).not.toHaveBeenCalled()
  })

  it('calls onFinished after the last question', async () => {
    const user = userEvent.setup()
    answerQuiz.mockResolvedValue({
      is_correct: false,
      correct_choice_index: 0,
      explanation: '説明',
      citation_date: '2026-03-09',
      next_due_date: '2026-03-10',
    })
    const onFinished = vi.fn()
    renderWithProviders(
      <QuizSession questions={[QUESTIONS[0]]} onFinished={onFinished} />,
    )

    await user.click(screen.getByRole('button', { name: '受信のみ' }))
    await screen.findByText(t('quiz.incorrectLabel'))
    await user.click(screen.getByRole('button', { name: t('quiz.nextButton') }))

    expect(onFinished).toHaveBeenCalledTimes(1)
  })

  it('shows an error message when answering fails', async () => {
    const user = userEvent.setup()
    const error = new Error('送信失敗')
    answerQuiz.mockRejectedValue(error)
    renderWithProviders(<QuizSession questions={QUESTIONS} onFinished={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: '送信' }))

    expect(await screen.findByText(apiErrorMessage(error))).toBeDefined()
  })

  it('disables choices once a result has been shown', async () => {
    const user = userEvent.setup()
    answerQuiz.mockResolvedValue({
      is_correct: true,
      correct_choice_index: 0,
      explanation: '説明',
      citation_date: '2026-03-09',
      next_due_date: '2026-03-12',
    })
    renderWithProviders(<QuizSession questions={QUESTIONS} onFinished={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: '送信' }))
    await screen.findByText(t('quiz.correctLabel'))

    expect((screen.getByRole('button', { name: '圧縮' }) as HTMLButtonElement).disabled).toBe(true)
  })
})
