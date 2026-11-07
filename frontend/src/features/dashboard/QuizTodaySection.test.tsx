import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import { QuizTodaySection } from './QuizTodaySection'

describe('QuizTodaySection', () => {
  it('renders nothing when there is nothing due today', () => {
    renderWithProviders(<QuizTodaySection count={0} />)

    expect(screen.queryByText(t('quiz.dashboardTitle'))).toBeNull()
  })

  it('shows the count and a start button when questions are due', () => {
    renderWithProviders(<QuizTodaySection count={3} />)

    expect(screen.getByText(t('quiz.dashboardCount', { count: 3 }))).toBeDefined()
    expect(screen.getByRole('link', { name: t('quiz.startButton') })).toBeDefined()
  })
})
