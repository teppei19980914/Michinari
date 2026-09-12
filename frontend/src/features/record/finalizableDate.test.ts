/** 入力可能期間（仕様書7.2）の判定テスト。サーバが拒否する日付で入力させないための事前判定で
 * あり、境界を誤るとBACKDATE_LIMIT_EXCEEDED等で入力内容が失われる（再発防止のため境界日を
 * 明示的に固定する）。 */
import { describe, expect, it } from 'vitest'
import { isFinalizableDate, isFutureDate } from './finalizableDate'

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

describe('isFutureDate', () => {
  it('treats tomorrow as future', () => {
    expect(isFutureDate('2026-08-25', TODAY)).toBe(true)
  })

  it('does not treat today as future', () => {
    expect(isFutureDate(TODAY, TODAY)).toBe(false)
  })

  it('does not treat past dates as future', () => {
    expect(isFutureDate('2026-08-23', TODAY)).toBe(false)
    expect(isFutureDate('2026-01-01', TODAY)).toBe(false)
  })

  it('counts calendar days across a month boundary', () => {
    expect(isFutureDate('2026-09-01', '2026-08-31')).toBe(true)
  })
})
