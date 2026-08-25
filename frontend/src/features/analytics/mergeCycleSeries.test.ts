import { describe, expect, it } from 'vitest'
import { cycleSeriesKey, mergeCycleSeries } from './mergeCycleSeries'

describe('mergeCycleSeries', () => {
  it('merges points from multiple cycles into one row per x-value', () => {
    const { rows, cycleNumbers } = mergeCycleSeries([
      { cycleNumber: 1, points: [{ x: '2026-01-01', value: 60 }] },
      { cycleNumber: 2, points: [{ x: '2026-02-01', value: 90 }] },
    ])

    expect(rows).toEqual([
      { x: '2026-01-01', [cycleSeriesKey(1)]: 60 },
      { x: '2026-02-01', [cycleSeriesKey(2)]: 90 },
    ])
    expect(cycleNumbers).toEqual([1, 2])
  })

  it('combines values from different cycles that share the same x-value into one row', () => {
    const { rows } = mergeCycleSeries([
      { cycleNumber: 1, points: [{ x: '2026-01-01', value: 10 }] },
      { cycleNumber: 2, points: [{ x: '2026-01-01', value: 20 }] },
    ])

    expect(rows).toEqual([{ x: '2026-01-01', [cycleSeriesKey(1)]: 10, [cycleSeriesKey(2)]: 20 }])
  })

  it('sorts rows by x-value regardless of input order', () => {
    const { rows } = mergeCycleSeries([
      { cycleNumber: 1, points: [{ x: '2026-03-01', value: 1 }, { x: '2026-01-01', value: 2 }] },
    ])

    expect(rows.map((r) => r.x)).toEqual(['2026-01-01', '2026-03-01'])
  })

  it('returns empty rows and cycle numbers when no series are given', () => {
    expect(mergeCycleSeries([])).toEqual({ rows: [], cycleNumbers: [] })
  })
})
