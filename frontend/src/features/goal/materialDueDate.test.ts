import { describe, expect, it } from 'vitest'
import { computeAutoDueDate } from './materialDueDate'

describe('computeAutoDueDate', () => {
  const subjects = [
    { id: 1, exam_date_type: 'RANGE' as const, exam_date_from: '2026-10-17', exam_date_fixed: null },
    { id: 2, exam_date_type: 'RANGE' as const, exam_date_from: '2026-08-27', exam_date_fixed: null },
    { id: 3, exam_date_type: 'FIXED' as const, exam_date_from: null, exam_date_fixed: '2026-09-01' },
  ]

  it('returns the day before the earliest effective exam date among selected subjects', () => {
    expect(computeAutoDueDate(subjects, [1, 2])).toBe('2026-08-26')
  })

  it('uses exam_date_fixed for FIXED-type subjects', () => {
    expect(computeAutoDueDate(subjects, [3])).toBe('2026-08-31')
  })

  it('returns null when no subject is selected or no exam date resolves', () => {
    expect(computeAutoDueDate(subjects, [])).toBeNull()
    expect(computeAutoDueDate([{ id: 4, exam_date_type: 'RANGE', exam_date_from: null, exam_date_fixed: null }], [4])).toBeNull()
  })
})
