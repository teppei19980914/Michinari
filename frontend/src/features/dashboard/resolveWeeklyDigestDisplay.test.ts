import { describe, expect, it } from 'vitest'
import { resolveWeeklyDigestDisplay } from './resolveWeeklyDigestDisplay'

describe('resolveWeeklyDigestDisplay', () => {
  it('prefers the AI summary text when present', () => {
    const result = resolveWeeklyDigestDisplay({
      ai_summary_text: '先週はよく頑張りました。',
      recorded_days: 0,
      total_minutes: null,
    })

    expect(result).toEqual({ kind: 'ai_summary', text: '先週はよく頑張りました。' })
  })

  it('falls back to a "no records" result when there is no AI summary and no records', () => {
    const result = resolveWeeklyDigestDisplay({
      ai_summary_text: null,
      recorded_days: 0,
      total_minutes: null,
    })

    expect(result).toEqual({ kind: 'no_records' })
  })

  it('falls back to the non-AI record summary when there is no AI summary but there are records', () => {
    const result = resolveWeeklyDigestDisplay({
      ai_summary_text: null,
      recorded_days: 3,
      total_minutes: 120,
    })

    expect(result).toEqual({ kind: 'record_summary', recordedDays: 3, totalMinutes: 120 })
  })

  it('keeps totalMinutes null for categories that do not track time (reading/work)', () => {
    const result = resolveWeeklyDigestDisplay({
      ai_summary_text: null,
      recorded_days: 2,
      total_minutes: null,
    })

    expect(result).toEqual({ kind: 'record_summary', recordedDays: 2, totalMinutes: null })
  })
})
