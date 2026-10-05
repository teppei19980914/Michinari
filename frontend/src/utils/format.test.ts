import { describe, expect, it } from 'vitest'
import { formatMonthKey, formatPercent } from './format'

describe('formatPercent', () => {
  it('renders a ratio as a rounded percentage', () => {
    expect(formatPercent(0.5)).toBe('50%')
    expect(formatPercent(0)).toBe('0%')
    expect(formatPercent(1)).toBe('100%')
  })

  it('rounds to the nearest whole percent', () => {
    expect(formatPercent(0.1234)).toBe('12%')
    expect(formatPercent(0.125)).toBe('13%')
  })
})

describe('formatMonthKey', () => {
  it('renders a YYYY-MM period key as a Japanese year and month', () => {
    expect(formatMonthKey('2026-09')).toBe('2026年9月')
    expect(formatMonthKey('2026-12')).toBe('2026年12月')
  })

  it('returns an unexpected format unchanged', () => {
    expect(formatMonthKey('2026-H1')).toBe('2026-H1')
    expect(formatMonthKey('')).toBe('')
  })
})
