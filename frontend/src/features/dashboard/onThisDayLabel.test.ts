import { describe, expect, it } from 'vitest'
import { t } from '../../locales/t'
import { resolveOnThisDayPeriodLabel } from './onThisDayLabel'

describe('resolveOnThisDayPeriodLabel', () => {
  it('returns "半年前" for 6 months', () => {
    expect(resolveOnThisDayPeriodLabel(6)).toBe(t('dashboard.onThisDay.halfYearAgo'))
  })

  it('returns a year-based label for multiples of 12', () => {
    expect(resolveOnThisDayPeriodLabel(12)).toBe(t('dashboard.onThisDay.yearsAgo', { count: 1 }))
    expect(resolveOnThisDayPeriodLabel(24)).toBe(t('dashboard.onThisDay.yearsAgo', { count: 2 }))
  })

  it('returns a month-based label for other values', () => {
    expect(resolveOnThisDayPeriodLabel(1)).toBe(t('dashboard.onThisDay.monthsAgo', { count: 1 }))
    expect(resolveOnThisDayPeriodLabel(3)).toBe(t('dashboard.onThisDay.monthsAgo', { count: 3 }))
  })
})
