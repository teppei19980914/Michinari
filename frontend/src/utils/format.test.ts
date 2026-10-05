import { describe, expect, it } from 'vitest'
import { formatPercent } from './format'

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
