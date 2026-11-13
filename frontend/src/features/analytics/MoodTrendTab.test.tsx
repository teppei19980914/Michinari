import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { apiErrorMessage } from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { MoodTrendTab } from './MoodTrendTab'

const getMoodAnalytics = vi.hoisted(() => vi.fn())
vi.mock('../../api/analytics', () => ({ getMoodAnalytics }))

describe('MoodTrendTab', () => {
  beforeEach(() => {
    getMoodAnalytics.mockReset()
  })

  it('shows the loading text while fetching', () => {
    getMoodAnalytics.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<MoodTrendTab goalId={1} />)

    expect(screen.getByText(t('common.loading'))).toBeDefined()
  })

  it('shows the error message when fetching fails', async () => {
    const error = new Error('取得失敗')
    getMoodAnalytics.mockRejectedValue(error)
    renderWithProviders(<MoodTrendTab goalId={1} />)

    expect(await screen.findByText(apiErrorMessage(error))).toBeDefined()
  })

  it('shows the empty message when there is no mood data', async () => {
    getMoodAnalytics.mockResolvedValue([])
    renderWithProviders(<MoodTrendTab goalId={1} />)

    expect(await screen.findByText(t('analytics.mood.empty'))).toBeDefined()
  })

  it('shows each recorded mood stamp by date', async () => {
    getMoodAnalytics.mockResolvedValue([
      { record_date: '2026-09-01', mood_value: 4 },
      { record_date: '2026-09-02', mood_value: 2 },
    ])
    renderWithProviders(<MoodTrendTab goalId={1} />)

    await screen.findByText(t('analytics.mood.trendTitle'))

    expect(screen.getByText('2026-09-01')).toBeDefined()
    expect(screen.getByText(t('dailyReport.quickRecord.moodStamps.4'))).toBeDefined()
    expect(screen.getByText('2026-09-02')).toBeDefined()
    expect(screen.getByText(t('dailyReport.quickRecord.moodStamps.2'))).toBeDefined()
  })
})
