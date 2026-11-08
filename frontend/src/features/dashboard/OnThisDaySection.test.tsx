import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { ROUTES } from '../../constants/routes'
import { renderWithProviders } from '../../test/renderWithProviders'
import { OnThisDaySection } from './OnThisDaySection'
import type { DashboardRead } from '../../api/dashboard'

const ENTRY: DashboardRead['on_this_day'] = {
  record_date: '2025-11-08',
  goal_id: 1,
  goal_name: '資格目標A',
  category: 'EXAM',
  excerpt: '今日は過去問を解いた',
  months_ago: 12,
}

describe('OnThisDaySection', () => {
  it('renders nothing when there is no entry', () => {
    renderWithProviders(<OnThisDaySection onThisDay={null} />)

    expect(screen.queryByText(t('dashboard.onThisDay.title'))).toBeNull()
  })

  it('shows the goal name, period label, and excerpt, linking to the daily report view', () => {
    renderWithProviders(<OnThisDaySection onThisDay={ENTRY} />)

    expect(screen.getByText(t('dashboard.onThisDay.title'))).toBeDefined()
    expect(
      screen.getByText(
        t('dashboard.onThisDay.goalLabel', {
          goalName: '資格目標A',
          periodLabel: t('dashboard.onThisDay.yearsAgo', { count: 1 }),
        }),
      ),
    ).toBeDefined()
    expect(screen.getByText('今日は過去問を解いた')).toBeDefined()

    const link = screen.getByRole('link')
    expect(link.getAttribute('href')).toBe(ROUTES.dailyReportView('2025-11-08'))
  })
})
