import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { apiErrorMessage } from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { QuizAccuracyTab } from './QuizAccuracyTab'

const getQuizAccuracyAnalytics = vi.hoisted(() => vi.fn())
vi.mock('../../api/analytics', () => ({ getQuizAccuracyAnalytics }))

describe('QuizAccuracyTab', () => {
  beforeEach(() => {
    getQuizAccuracyAnalytics.mockReset()
  })

  it('shows the loading text while fetching', () => {
    getQuizAccuracyAnalytics.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<QuizAccuracyTab goalId={1} />)

    expect(screen.getByText(t('common.loading'))).toBeDefined()
  })

  it('shows the error message when fetching fails', async () => {
    const error = new Error('取得失敗')
    getQuizAccuracyAnalytics.mockRejectedValue(error)
    renderWithProviders(<QuizAccuracyTab goalId={1} />)

    expect(await screen.findByText(apiErrorMessage(error))).toBeDefined()
  })

  it('shows the empty message when there is no trend data', async () => {
    getQuizAccuracyAnalytics.mockResolvedValue({ trend: [], weak_themes: [] })
    renderWithProviders(<QuizAccuracyTab goalId={1} />)

    expect(await screen.findByText(t('analytics.quizAccuracy.empty'))).toBeDefined()
  })

  it('shows the weekly trend and weak themes', async () => {
    getQuizAccuracyAnalytics.mockResolvedValue({
      trend: [
        { period_start: '2026-03-09', period_end: '2026-03-15', answer_count: 4, correct_count: 1 },
      ],
      weak_themes: [{ theme_id: 5, theme_name: '苦手テーマ', answer_count: 2, correct_count: 0 }],
    })
    renderWithProviders(<QuizAccuracyTab goalId={1} />)

    expect(await screen.findByText('苦手テーマ')).toBeDefined()
    expect(screen.getByText('25%（1/4）')).toBeDefined()
    expect(screen.getByText('0%（0/2）')).toBeDefined()
  })
})
