import { describe, expect, it } from 'vitest'
import { formatAxisNumber, formatDateTick, formatPeriodLabel } from './formatPeriod'

describe('formatPeriodLabel', () => {
  it('formats a DAY period as month/day', () => {
    expect(formatPeriodLabel('2026-03-05', 'DAY')).toBe('3/5')
  })

  it('formats a WEEK period as the week-start date with a range marker', () => {
    expect(formatPeriodLabel('2026-03-02', 'WEEK')).toBe('3/2〜')
  })

  it('formats a MONTH period as year + month', () => {
    expect(formatPeriodLabel('2026-03-01', 'MONTH')).toBe('2026年3月')
  })
})

describe('formatDateTick', () => {
  it('formats an ISO date as month/day', () => {
    expect(formatDateTick('2026-08-25')).toBe('8/25')
  })
})

describe('formatAxisNumber', () => {
  it('rounds a near-integer float to a clean integer string', () => {
    expect(formatAxisNumber(219.99999999999997)).toBe('220')
  })

  it('formats a plain integer unchanged', () => {
    expect(formatAxisNumber(0)).toBe('0')
  })
})
