import { describe, expect, it } from 'vitest'
import { resolveCalendarDateAction } from './resolveCalendarDateAction'

const TODAY = '2026-08-24'
const YESTERDAY = '2026-08-23'
const TWO_DAYS_AGO = '2026-08-22'
const FOUR_DAYS_AGO = '2026-08-20'
const TOMORROW = '2026-08-25'

describe('resolveCalendarDateAction', () => {
  it('routes to the report/progress choice for an unreported yesterday', () => {
    expect(
      resolveCalendarDateAction({ targetDate: YESTERDAY, today: TODAY, recordState: null }),
    ).toBe('CHOOSE_REPORT_TYPE')
  })

  it('routes straight to progress-only registration for an unreported date 2+ days ago', () => {
    // 確定は当日・前日のみ（仕様書7.2）。以前は日次報告との選択モーダルを出していたため、
    // 日次報告を選ぶと確定時にBACKDATE_LIMIT_EXCEEDEDとなり入力内容が失われていた。
    expect(
      resolveCalendarDateAction({ targetDate: FOUR_DAYS_AGO, today: TODAY, recordState: null }),
    ).toBe('REGISTER_PROGRESS_ONLY')
  })

  it('routes to promotion when progress-only and exactly yesterday', () => {
    expect(
      resolveCalendarDateAction({
        targetDate: YESTERDAY,
        today: TODAY,
        recordState: 'PROGRESS_ONLY',
      }),
    ).toBe('PROMOTE_TO_REPORT')
  })

  it('routes to view-only when progress-only and 2+ days ago', () => {
    expect(
      resolveCalendarDateAction({
        targetDate: TWO_DAYS_AGO,
        today: TODAY,
        recordState: 'PROGRESS_ONLY',
      }),
    ).toBe('VIEW_ONLY')
  })

  it('still routes to the daily report when reported but within the finalizable window (regression: a day with only one category finalized aggregates to REPORTED, and the remaining categories must stay reportable)', () => {
    expect(
      resolveCalendarDateAction({ targetDate: TODAY, today: TODAY, recordState: 'REPORTED' }),
    ).toBe('REPORT_TODAY')
    expect(
      resolveCalendarDateAction({ targetDate: YESTERDAY, today: TODAY, recordState: 'REPORTED' }),
    ).toBe('PROMOTE_TO_REPORT')
  })

  it('routes to the read-only view when reported and outside the finalizable window', () => {
    expect(
      resolveCalendarDateAction({
        targetDate: TWO_DAYS_AGO,
        today: TODAY,
        recordState: 'REPORTED',
      }),
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
    expect(resolveCalendarDateAction({ targetDate: TODAY, today: TODAY, recordState: null })).toBe(
      'REPORT_TODAY',
    )
    expect(
      resolveCalendarDateAction({
        targetDate: TODAY,
        today: TODAY,
        recordState: 'PROGRESS_ONLY',
      }),
    ).toBe('REPORT_TODAY')
  })

  it('allows only a day-type change for future dates, even if a record state somehow exists', () => {
    expect(
      resolveCalendarDateAction({ targetDate: TOMORROW, today: TODAY, recordState: null }),
    ).toBe('DAY_TYPE_ONLY')
    expect(
      resolveCalendarDateAction({ targetDate: TOMORROW, today: TODAY, recordState: 'REPORTED' }),
    ).toBe('DAY_TYPE_ONLY')
  })
})
