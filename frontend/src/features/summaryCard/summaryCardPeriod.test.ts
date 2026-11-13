import { describe, expect, it } from 'vitest'
import { closedGoalPeriod, defaultOpenPeriod } from './summaryCardPeriod'

describe('defaultOpenPeriod', () => {
  it('当年1/1から論理日までを返す', () => {
    expect(defaultOpenPeriod('2026-11-13')).toEqual({ dateFrom: '2026-01-01', dateTo: '2026-11-13' })
  })
})

describe('closedGoalPeriod', () => {
  it('開始日からクローズ日（日付部分）までを返す', () => {
    expect(closedGoalPeriod('2026-01-05', '2026-10-20T09:30:00+00:00')).toEqual({
      dateFrom: '2026-01-05',
      dateTo: '2026-10-20',
    })
  })
})
