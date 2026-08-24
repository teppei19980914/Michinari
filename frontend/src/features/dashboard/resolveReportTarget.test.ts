import { describe, expect, it } from 'vitest'
import { resolveReportTarget } from './resolveReportTarget'

describe('resolveReportTarget', () => {
  it('routes to the daily report screen when unreported', () => {
    expect(resolveReportTarget(null, '2026-08-24')).toBe('/records/2026-08-24/report')
  })

  it('routes to the daily report screen (promotion) when progress-only', () => {
    expect(resolveReportTarget('PROGRESS_ONLY', '2026-08-24')).toBe('/records/2026-08-24/report')
  })

  it('routes to the read-only view when already reported', () => {
    expect(resolveReportTarget('REPORTED', '2026-08-24')).toBe('/records/2026-08-24/view')
  })
})
