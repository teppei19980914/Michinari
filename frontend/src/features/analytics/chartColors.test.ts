import { afterEach, describe, expect, it } from 'vitest'
import {
  CYCLE_SERIES_COLORS,
  cycleSeriesColor,
  resolveAxisLineColor,
  resolveGridLineColor,
  resolvePlanLineColor,
} from './chartColors'

describe('cycleSeriesColor', () => {
  it('assigns the palette in a fixed order', () => {
    expect(cycleSeriesColor(0)).toBe(CYCLE_SERIES_COLORS[0])
    expect(cycleSeriesColor(2)).toBe(CYCLE_SERIES_COLORS[2])
  })

  it('wraps around once the palette is exhausted', () => {
    // 周回数がパレット長を超えても色が undefined にならないことを固定する。
    expect(cycleSeriesColor(CYCLE_SERIES_COLORS.length)).toBe(CYCLE_SERIES_COLORS[0])
    expect(cycleSeriesColor(CYCLE_SERIES_COLORS.length + 3)).toBe(CYCLE_SERIES_COLORS[3])
  })
})

afterEach(() => {
  document.documentElement.removeAttribute('data-theme')
})

describe('テーマに追従する中立色（UIリッチ化、ダークモードで埋没しないための明暗切替）', () => {
  it('uses the light value by default', () => {
    expect(resolveGridLineColor()).toBe('#e1e0d9')
    expect(resolveAxisLineColor()).toBe('#c3c2b7')
    expect(resolvePlanLineColor()).toBe('#898781')
  })

  it('switches to a dark-mode-safe value when data-theme="dark"', () => {
    document.documentElement.setAttribute('data-theme', 'dark')

    expect(resolveGridLineColor()).toBe('#374151')
    expect(resolveAxisLineColor()).toBe('#4b5563')
    expect(resolvePlanLineColor()).toBe('#9ca3af')
  })
})
