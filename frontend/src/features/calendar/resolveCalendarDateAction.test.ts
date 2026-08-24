import { describe, expect, it } from 'vitest'
import { resolveCalendarDateAction } from './resolveCalendarDateAction'

const TODAY = '2026-08-24'

describe('resolveCalendarDateAction', () => {
  it('routes to the report/progress choice for an unreported past date', () => {
    expect(
      resolveCalendarDateAction({ targetDate: '2026-08-20', today: TODAY, recordState: null }),
    ).toBe('CHOOSE_REPORT_TYPE')
  })

  it('routes to promotion when progress-only and exactly yesterday', () => {
    expect(
      resolveCalendarDateAction({
        targetDate: '2026-08-23',
        today: TODAY,
        recordState: 'PROGRESS_ONLY',
      }),
    ).toBe('PROMOTE_TO_REPORT')
  })

  it('routes to view-only when progress-only and 2+ days ago', () => {
    expect(
      resolveCalendarDateAction({
        targetDate: '2026-08-22',
        today: TODAY,
        recordState: 'PROGRESS_ONLY',
      }),
    ).toBe('VIEW_ONLY')
  })

  it('routes to the read-only view whenever reported, regardless of date', () => {
    expect(
      resolveCalendarDateAction({ targetDate: TODAY, today: TODAY, recordState: 'REPORTED' }),
    ).toBe('VIEW_REPORT')
    expect(
      resolveCalendarDateAction({
        targetDate: '2026-08-01',
        today: TODAY,
        recordState: 'REPORTED',
      }),
    ).toBe('VIEW_REPORT')
  })

  it('routes to the daily report for today regardless of existing record state', () => {
    expect(
      resolveCalendarDateAction({ targetDate: TODAY, today: TODAY, recordState: null }),
    ).toBe('REPORT_TODAY')
    expect(
      resolveCalendarDateAction({
        targetDate: TODAY,
        today: TODAY,
        recordState: 'PROGRESS_ONLY',
      }),
    ).toBe('REPORT_TODAY')
  })

  it('allows only a day-type change for future dates', () => {
    expect(
      resolveCalendarDateAction({ targetDate: '2026-08-25', today: TODAY, recordState: null }),
    ).toBe('DAY_TYPE_ONLY')
  })
})
