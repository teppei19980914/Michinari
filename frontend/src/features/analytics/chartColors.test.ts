import { describe, expect, it } from 'vitest'
import { CYCLE_SERIES_COLORS, cycleSeriesColor } from './chartColors'

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
