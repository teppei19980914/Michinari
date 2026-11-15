import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { VocabQuizSummaryView } from './VocabQuizSummaryView'

afterEach(() => {
  cleanup()
})

describe('VocabQuizSummaryView', () => {
  it('shows the score', () => {
    renderWithProviders(
      <VocabQuizSummaryView
        deckId={1}
        summary={{ correctCount: 2, totalCount: 3, accuracyPercent: 66.6, wrongCards: [] }}
        onCheckWrongCards={vi.fn()}
        isChecking={false}
      />,
    )

    expect(screen.getByText(t('vocab.quiz.scoreLabel', { correct: 2, total: 3 }))).toBeDefined()
  })

  it('hides the wrong-terms section when everything was correct', () => {
    renderWithProviders(
      <VocabQuizSummaryView
        deckId={1}
        summary={{ correctCount: 3, totalCount: 3, accuracyPercent: 100, wrongCards: [] }}
        onCheckWrongCards={vi.fn()}
        isChecking={false}
      />,
    )

    expect(screen.queryByText(t('vocab.quiz.wrongTermsTitle'))).toBeNull()
  })

  it('lists wrong terms and checks them on click', async () => {
    const user = userEvent.setup()
    const onCheckWrongCards = vi.fn()
    renderWithProviders(
      <VocabQuizSummaryView
        deckId={1}
        summary={{
          correctCount: 1,
          totalCount: 2,
          accuracyPercent: 50,
          wrongCards: [{ cardId: 7, term: '苦手な用語' }],
        }}
        onCheckWrongCards={onCheckWrongCards}
        isChecking={false}
      />,
    )

    expect(screen.getByText('苦手な用語')).toBeDefined()
    await user.click(screen.getByRole('button', { name: t('vocab.quiz.checkWrongButton') }))
    expect(onCheckWrongCards).toHaveBeenCalledOnce()
  })

  it('disables the check button while checking is in progress', () => {
    renderWithProviders(
      <VocabQuizSummaryView
        deckId={1}
        summary={{
          correctCount: 0,
          totalCount: 1,
          accuracyPercent: 0,
          wrongCards: [{ cardId: 1, term: 'A' }],
        }}
        onCheckWrongCards={vi.fn()}
        isChecking
      />,
    )

    expect(
      (screen.getByRole('button', { name: t('vocab.quiz.checkWrongButton') }) as HTMLButtonElement)
        .disabled,
    ).toBe(true)
  })
})
