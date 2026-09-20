/** 直近4週間カレンダー（仕様書6.1、S-4 4-5）の表示条件を固定する。
 *
 * 日付範囲の算出自体はresolveRecentWeeksRange.test.tsで、日種別背景色・記録状態
 * マーカーの描画自体はCalendarGrid.test.tsx・calendarCellStyle.test.tsで検証済みのため、
 * ここでは「取得した範囲・データがCalendarGridへ正しく渡り、読み取り専用として
 * 描画されること」のみを確認する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, screen } from '@testing-library/react'
import { t } from '../../locales/t'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { CalendarDayRead } from '../../api/calendar'
import { RecentActivityCalendarSection } from './RecentActivityCalendarSection'

const getCalendar = vi.hoisted(() => vi.fn())
vi.mock('../../api/calendar', () => ({ getCalendar }))

// 2026-09-16(水)なので、直近4週間は2026-08-23〜2026-09-19になる（resolveRecentWeeksRange参照）。
const TODAY = '2026-09-16'

beforeEach(() => {
  vi.clearAllMocks()
  getCalendar.mockResolvedValue([])
})

afterEach(() => {
  cleanup()
})

describe('RecentActivityCalendarSection', () => {
  it('renders nothing while the calendar data has not loaded yet', () => {
    getCalendar.mockReturnValue(new Promise(() => undefined))
    const { container } = renderWithProviders(<RecentActivityCalendarSection today={TODAY} />)

    expect(container.textContent).toBe('')
  })

  it('fetches exactly the 4-week range derived from today', async () => {
    renderWithProviders(<RecentActivityCalendarSection today={TODAY} />)

    await screen.findByText(t('dashboard.recentActivityCalendar.title'))
    expect(getCalendar).toHaveBeenCalledWith('2026-08-23', '2026-09-19')
  })

  it('shows the title and a link to the full calendar page', async () => {
    renderWithProviders(<RecentActivityCalendarSection today={TODAY} />)

    expect(await screen.findByText(t('dashboard.recentActivityCalendar.title'))).toBeDefined()
    const link = screen.getByRole('link', {
      name: t('dashboard.recentActivityCalendar.viewCalendarLink'),
    })
    expect(link.getAttribute('href')).toBe('/calendar')
  })

  it('renders the fetched days as read-only cells (no click-to-navigate)', async () => {
    const day: CalendarDayRead = {
      target_date: '2026-09-13',
      day_type: 'PLAN',
      record_state: 'REPORTED',
    }
    getCalendar.mockResolvedValue([day])
    renderWithProviders(<RecentActivityCalendarSection today={TODAY} />)

    await screen.findByText(t('dashboard.recentActivityCalendar.title'))
    expect(screen.getByText(t('calendar.marker.reported'))).toBeDefined()
    expect(screen.queryByRole('button', { name: '13' })).toBeNull()
  })
})
