import { describe, expect, it } from 'vitest'
import { isFinalizableDate } from './finalizableDate'

const TODAY = '2026-08-24'

describe('isFinalizableDate', () => {
  it('accepts today', () => {
    expect(isFinalizableDate(TODAY, TODAY)).toBe(true)
  })

  it('accepts yesterday', () => {
    expect(isFinalizableDate('2026-08-23', TODAY)).toBe(true)
  })

  it('rejects 2 days ago', () => {
    expect(isFinalizableDate('2026-08-22', TODAY)).toBe(false)
  })

  it('rejects future dates', () => {
    expect(isFinalizableDate('2026-08-25', TODAY)).toBe(false)
  })

  it('counts calendar days across a month boundary', () => {
    expect(isFinalizableDate('2026-07-31', '2026-08-01')).toBe(true)
    expect(isFinalizableDate('2026-07-30', '2026-08-01')).toBe(false)
  })
})
