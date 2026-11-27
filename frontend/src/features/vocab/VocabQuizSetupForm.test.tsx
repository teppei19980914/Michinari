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
    renderWithProviders(
      <VocabQuizSetupForm
        termCardCount={3}
        defaultQuestionCount={10}
        maxQuestionCount={100}
        onStart={vi.fn()}
      />,
    )

    expect(screen.getByText(t('vocab.quiz.choiceUnavailableNotice'))).toBeDefined()
    const option = screen.getByRole('option', {
      name: t('vocab.quiz.modeOptions.CHOICE_TERM_TO_MEANING'),
    }) as HTMLOptionElement
    expect(option.disabled).toBe(true)
  })

  it('does not show the notice and enables choice modes with 4 or more cards', () => {
    renderWithProviders(
      <VocabQuizSetupForm
        termCardCount={4}
        defaultQuestionCount={10}
        maxQuestionCount={100}
        onStart={vi.fn()}
      />,
    )

    expect(screen.queryByText(t('vocab.quiz.choiceUnavailableNotice'))).toBeNull()
    const option = screen.getByRole('option', {
      name: t('vocab.quiz.modeOptions.CHOICE_TERM_TO_MEANING'),
    }) as HTMLOptionElement
    expect(option.disabled).toBe(false)
  })

  it('disables CHOICE_RANDOM too when fewer than 4 cards (開発Todo_単語帳_出題導線改修_v1.0 D4)', () => {
    renderWithProviders(
      <VocabQuizSetupForm
        termCardCount={3}
        defaultQuestionCount={10}
        maxQuestionCount={100}
        onStart={vi.fn()}
      />,
    )

    const option = screen.getByRole('option', {
      name: t('vocab.quiz.modeOptions.CHOICE_RANDOM'),
    }) as HTMLOptionElement
    expect(option.disabled).toBe(true)
  })

  it('enables CHOICE_RANDOM with 4 or more cards', () => {
    renderWithProviders(
      <VocabQuizSetupForm
        termCardCount={4}
        defaultQuestionCount={10}
        maxQuestionCount={100}
        onStart={vi.fn()}
      />,
    )

    const option = screen.getByRole('option', {
      name: t('vocab.quiz.modeOptions.CHOICE_RANDOM'),
    }) as HTMLOptionElement
    expect(option.disabled).toBe(false)
  })
})

describe('VocabQuizSetupForm の問題数の初期値・上限（軽微1の修正、2026-11-22）', () => {
  it('uses defaultQuestionCount as the initial question count', async () => {
    const user = userEvent.setup()
    const onStart = vi.fn()
    renderWithProviders(
      <VocabQuizSetupForm
        termCardCount={10}
        defaultQuestionCount={7}
        maxQuestionCount={100}
        onStart={onStart}
      />,
    )

    await user.click(screen.getByRole('button', { name: t('vocab.quiz.startButton') }))

    expect(onStart).toHaveBeenCalledWith(
      expect.objectContaining({ question_count: 7 }),
    )
  })

  it('sets maxQuestionCount as the input max attribute', () => {
    renderWithProviders(
      <VocabQuizSetupForm
        termCardCount={10}
        defaultQuestionCount={10}
        maxQuestionCount={50}
        onStart={vi.fn()}
      />,
    )

    const countInput = screen.getByLabelText(t('vocab.quiz.questionCountLabel'))
    expect(countInput.getAttribute('max')).toBe('50')
  })
})

describe('VocabQuizSetupForm の開始', () => {
  it('starts with the default parameters', async () => {
    const user = userEvent.setup()
    const onStart = vi.fn()
    renderWithProviders(
      <VocabQuizSetupForm
        termCardCount={10}
        defaultQuestionCount={10}
        maxQuestionCount={100}
        onStart={onStart}
      />,
    )

    await user.click(screen.getByRole('button', { name: t('vocab.quiz.startButton') }))

    expect(onStart).toHaveBeenCalledWith({
      mode: 'FLASH_TERM_TO_MEANING',
      filter: 'ALL',
      order: 'RANDOM',
      question_count: 10,
      card_type: 'ALL',
    })
  })

  it('starts with the chosen mode, filter, order and question count', async () => {
    const user = userEvent.setup()
    const onStart = vi.fn()
    renderWithProviders(
      <VocabQuizSetupForm
        termCardCount={10}
        defaultQuestionCount={10}
        maxQuestionCount={100}
        onStart={onStart}
      />,
    )

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
      card_type: 'ALL',
    })
  })

  it('starts with the chosen card type', async () => {
    const user = userEvent.setup()
    const onStart = vi.fn()
    renderWithProviders(
      <VocabQuizSetupForm
        termCardCount={10}
        defaultQuestionCount={10}
        maxQuestionCount={100}
        onStart={onStart}
      />,
    )

    await user.selectOptions(
      screen.getByLabelText(t('vocab.deckDetail.cardTypeFilterLabel')),
      t('vocab.deckDetail.cardTypeOptions.SITUATION'),
    )
    await user.click(screen.getByRole('button', { name: t('vocab.quiz.startButton') }))

    expect(onStart).toHaveBeenCalledWith(expect.objectContaining({ card_type: 'SITUATION' }))
  })

  it('starts with FLASH_RANDOM when selected (開発Todo_単語帳_出題導線改修_v1.0 U5)', async () => {
    const user = userEvent.setup()
    const onStart = vi.fn()
    renderWithProviders(
      <VocabQuizSetupForm
        termCardCount={10}
        defaultQuestionCount={10}
        maxQuestionCount={100}
        onStart={onStart}
      />,
    )

    await user.selectOptions(
      screen.getByLabelText(t('vocab.quiz.modeLabel')),
      t('vocab.quiz.modeOptions.FLASH_RANDOM'),
    )
    await user.click(screen.getByRole('button', { name: t('vocab.quiz.startButton') }))

    expect(onStart).toHaveBeenCalledWith(expect.objectContaining({ mode: 'FLASH_RANDOM' }))
  })

  it('starts with CHOICE_RANDOM when selected', async () => {
    const user = userEvent.setup()
    const onStart = vi.fn()
    renderWithProviders(
      <VocabQuizSetupForm
        termCardCount={10}
        defaultQuestionCount={10}
        maxQuestionCount={100}
        onStart={onStart}
      />,
    )

    await user.selectOptions(
      screen.getByLabelText(t('vocab.quiz.modeLabel')),
      t('vocab.quiz.modeOptions.CHOICE_RANDOM'),
    )
    await user.click(screen.getByRole('button', { name: t('vocab.quiz.startButton') }))

    expect(onStart).toHaveBeenCalledWith(expect.objectContaining({ mode: 'CHOICE_RANDOM' }))
  })
})
