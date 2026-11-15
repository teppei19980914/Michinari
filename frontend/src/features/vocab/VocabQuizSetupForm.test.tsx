import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { VocabQuizSetupForm } from './VocabQuizSetupForm'

afterEach(() => {
  cleanup()
})

describe('VocabQuizSetupForm の4択の可否', () => {
  it('shows the notice and disables choice modes when fewer than 4 cards', () => {
    renderWithProviders(<VocabQuizSetupForm cardCount={3} onStart={vi.fn()} />)

    expect(screen.getByText(t('vocab.quiz.choiceUnavailableNotice'))).toBeDefined()
    const option = screen.getByRole('option', {
      name: t('vocab.quiz.modeOptions.CHOICE_TERM_TO_MEANING'),
    }) as HTMLOptionElement
    expect(option.disabled).toBe(true)
  })

  it('does not show the notice and enables choice modes with 4 or more cards', () => {
    renderWithProviders(<VocabQuizSetupForm cardCount={4} onStart={vi.fn()} />)

    expect(screen.queryByText(t('vocab.quiz.choiceUnavailableNotice'))).toBeNull()
    const option = screen.getByRole('option', {
      name: t('vocab.quiz.modeOptions.CHOICE_TERM_TO_MEANING'),
    }) as HTMLOptionElement
    expect(option.disabled).toBe(false)
  })
})

describe('VocabQuizSetupForm の開始', () => {
  it('starts with the default parameters', async () => {
    const user = userEvent.setup()
    const onStart = vi.fn()
    renderWithProviders(<VocabQuizSetupForm cardCount={10} onStart={onStart} />)

    await user.click(screen.getByRole('button', { name: t('vocab.quiz.startButton') }))

    expect(onStart).toHaveBeenCalledWith({
      mode: 'FLASH_TERM_TO_MEANING',
      filter: 'ALL',
      order: 'RANDOM',
      question_count: 10,
    })
  })

  it('starts with the chosen mode, filter, order and question count', async () => {
    const user = userEvent.setup()
    const onStart = vi.fn()
    renderWithProviders(<VocabQuizSetupForm cardCount={10} onStart={onStart} />)

    await user.selectOptions(
      screen.getByLabelText(t('vocab.quiz.modeLabel')),
      t('vocab.quiz.modeOptions.TYPED_MEANING_TO_TERM'),
    )
    await user.selectOptions(
      screen.getByLabelText(t('vocab.deckDetail.filterLabel')),
      t('vocab.deckDetail.filterOptions.CHECKED'),
    )
    await user.selectOptions(
      screen.getByLabelText(t('vocab.quiz.orderLabel')),
      t('vocab.quiz.orderOptions.WEAK_ORDER'),
    )
    const countInput = screen.getByLabelText(t('vocab.quiz.questionCountLabel'))
    await user.clear(countInput)
    await user.type(countInput, '5')
    await user.click(screen.getByRole('button', { name: t('vocab.quiz.startButton') }))

    expect(onStart).toHaveBeenCalledWith({
      mode: 'TYPED_MEANING_TO_TERM',
      filter: 'CHECKED',
      order: 'WEAK_ORDER',
      question_count: 5,
    })
  })
})
