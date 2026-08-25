import { describe, expect, it } from 'vitest'
import { computeLatestQualityValue } from './knowledgeExportSummary'

describe('computeLatestQualityValue', () => {
  it('returns null when there are no entries', () => {
    expect(computeLatestQualityValue([])).toBeNull()
  })

  it('returns null when entries have empty series', () => {
    expect(computeLatestQualityValue([{ material: '教材A', cycle: 1, series: [] }])).toBeNull()
  })

  it('picks the value from the most recent date within a single series', () => {
    const entries = [
      {
        material: '教材A',
        cycle: 1,
        series: [
          { date: '2026-01-01', value: 60 },
          { date: '2026-03-01', value: 80 },
          { date: '2026-02-01', value: 70 },
        ],
      },
    ]
    expect(computeLatestQualityValue(entries)).toBe(80)
  })

  it('picks the most recent date across multiple materials and cycles', () => {
    const entries = [
      { material: '教材A', cycle: 1, series: [{ date: '2026-01-01', value: 60 }] },
      { material: '教材A', cycle: 2, series: [{ date: '2026-04-01', value: 90 }] },
      { material: '教材B', cycle: 1, series: [{ date: '2026-02-01', value: 75 }] },
    ]
    expect(computeLatestQualityValue(entries)).toBe(90)
  })
})
