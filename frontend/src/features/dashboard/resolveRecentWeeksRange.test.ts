import { describe, expect, it } from 'vitest'
import { resolveRecentWeeksRange } from './resolveRecentWeeksRange'

describe('resolveRecentWeeksRange', () => {
  it('returns a 4-week (28 day), Sunday-start range ending with the current week', () => {
    // 2026-09-16は水曜日（週は日曜始まりのため、当週は09-13(日)〜09-19(土)）。
    const result = resolveRecentWeeksRange(new Date(2026, 8, 16))

    expect(result).toEqual({ dateFrom: '2026-08-23', dateTo: '2026-09-19' })
  })

  it('returns the same range regardless of which day of the current week "today" falls on', () => {
    const sunday = resolveRecentWeeksRange(new Date(2026, 8, 13))
    const saturday = resolveRecentWeeksRange(new Date(2026, 8, 19))

    expect(sunday).toEqual({ dateFrom: '2026-08-23', dateTo: '2026-09-19' })
    expect(saturday).toEqual(sunday)
  })
})
