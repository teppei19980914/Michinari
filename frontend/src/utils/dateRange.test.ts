import { describe, expect, it } from 'vitest'
import { daysBetween } from './dateRange'

describe('daysBetween', () => {
  it('同じ日なら0を返す', () => {
    expect(daysBetween('2026-11-23', '2026-11-23')).toBe(0)
  })

  it('後の日付までの日数を正の値で返す', () => {
    expect(daysBetween('2026-11-23', '2026-11-30')).toBe(7)
  })

  it('前の日付までの日数を負の値で返す', () => {
    expect(daysBetween('2026-11-23', '2026-11-20')).toBe(-3)
  })

  it('年をまたぐ日数も正しく計算する', () => {
    expect(daysBetween('2026-12-30', '2027-01-02')).toBe(3)
  })
})
