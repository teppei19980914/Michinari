import { describe, expect, it } from 'vitest'
import { mergeProgressSeries } from './mergeProgressSeries'

describe('mergeProgressSeries', () => {
  it('merges actual and plan points that share the same date into one row', () => {
    const rows = mergeProgressSeries(
      [{ record_date: '2026-01-01', cumulative_completed: 10 }],
      [{ record_date: '2026-01-01', cumulative_completed: 15 }],
    )

    expect(rows).toEqual([{ date: '2026-01-01', actual: 10, plan: 15 }])
  })

  it('keeps dates that only appear in one of the two series (plan line extends beyond actuals)', () => {
    const rows = mergeProgressSeries(
      [{ record_date: '2026-01-01', cumulative_completed: 10 }],
      [
        { record_date: '2026-01-01', cumulative_completed: 15 },
        { record_date: '2026-01-02', cumulative_completed: 30 },
      ],
    )

    expect(rows).toEqual([
      { date: '2026-01-01', actual: 10, plan: 15 },
      { date: '2026-01-02', plan: 30 },
    ])
  })

  it('sorts rows chronologically regardless of input order', () => {
    const rows = mergeProgressSeries(
      [
        { record_date: '2026-01-05', cumulative_completed: 50 },
        { record_date: '2026-01-01', cumulative_completed: 10 },
      ],
      [],
    )

    expect(rows.map((r) => r.date)).toEqual(['2026-01-01', '2026-01-05'])
  })

  it('returns an empty array when both series are empty', () => {
    expect(mergeProgressSeries([], [])).toEqual([])
  })
})
