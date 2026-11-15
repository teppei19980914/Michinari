import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { VocabQuizQuestionView } from './VocabQuizQuestionView'
import type { VocabQuizQuestion } from '../../api/vocab'

afterEach(() => {
  cleanup()
})

describe('VocabQuizQuestionView のカードをめくる形式', () => {
  const question: VocabQuizQuestion = { card_id: 1, prompt: '用語A', reveal: '意味A' }

  it('reveals the answer only after clicking the reveal button', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <VocabQuizQuestionView
        mode="FLASH_TERM_TO_MEANING"
        question={question}
        lastResult={null}
        onSubmit={vi.fn()}
        onNext={vi.fn()}
      />,
    )

    expect(screen.queryByText('意味A')).toBeNull()
    await user.click(screen.getByRole('button', { name: t('vocab.quiz.revealButton') }))
    expect(screen.getByText('意味A')).toBeDefined()
  })

  it('submits self_judged_correct true/false for the respective buttons', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderWithProviders(
      <VocabQuizQuestionView
        mode="FLASH_TERM_TO_MEANING"
        question={question}
        lastResult={null}
        onSubmit={onSubmit}
        onNext={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: t('vocab.quiz.revealButton') }))
    await user.click(screen.getByRole('button', { name: t('vocab.quiz.knewItButton') }))
    expect(onSubmit).toHaveBeenCalledWith({ self_judged_correct: true })

    await user.click(screen.getByRole('button', { name: t('vocab.quiz.revealButton') }))
    await user.click(screen.getByRole('button', { name: t('vocab.quiz.didntKnowButton') }))
    expect(onSubmit).toHaveBeenCalledWith({ self_judged_correct: false })
  })
})

describe('VocabQuizQuestionView の4択形式', () => {
  const question: VocabQuizQuestion = {
    card_id: 1,
    prompt: '用語A',
    options: [
      { card_id: 1, text: '意味A' },
      { card_id: 2, text: '意味B' },
      { card_id: 3, text: '意味C' },
      { card_id: 4, text: '意味D' },
    ],
  }

  it('submits the selected option card id', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderWithProviders(
      <VocabQuizQuestionView
        mode="CHOICE_TERM_TO_MEANING"
        question={question}
        lastResult={null}
        onSubmit={onSubmit}
        onNext={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: '意味C' }))

    expect(onSubmit).toHaveBeenCalledWith({ selected_card_id: 3 })
  })

  it('shows the result and advances on next when a result is given', async () => {
    const user = userEvent.setup()
    const onNext = vi.fn()
    renderWithProviders(
      <VocabQuizQuestionView
        mode="CHOICE_TERM_TO_MEANING"
        question={question}
        lastResult={{ is_correct: false }}
        onSubmit={vi.fn()}
        onNext={onNext}
      />,
    )

    expect(screen.getByText(t('vocab.quiz.incorrectLabel'))).toBeDefined()
    await user.click(screen.getByRole('button', { name: t('vocab.quiz.nextButton') }))
    expect(onNext).toHaveBeenCalledOnce()
  })
})

describe('VocabQuizQuestionView の入力式', () => {
  const question: VocabQuizQuestion = { card_id: 1, prompt: '意味A' }

  it('submits the typed answer and clears the input', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderWithProviders(
      <VocabQuizQuestionView
        mode="TYPED_MEANING_TO_TERM"
        question={question}
        lastResult={null}
        onSubmit={onSubmit}
        onNext={vi.fn()}
      />,
    )

    const input = screen.getByLabelText(t('vocab.quiz.answerInputLabel'))
    await user.type(input, '用語A')
    await user.click(screen.getByRole('button', { name: t('vocab.quiz.submitButton') }))

    expect(onSubmit).toHaveBeenCalledWith({ answer_text: '用語A' })
  })

  it('shows the correct result label', () => {
    renderWithProviders(
      <VocabQuizQuestionView
        mode="TYPED_MEANING_TO_TERM"
        question={question}
        lastResult={{ is_correct: true }}
        onSubmit={vi.fn()}
        onNext={vi.fn()}
      />,
    )

    expect(screen.getByText(t('vocab.quiz.correctLabel'))).toBeDefined()
  })
})
