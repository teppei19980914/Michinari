import { describe, expect, it } from 'vitest'
import { isSubjectRangeStartInPast } from './subjectWarnings'

describe('isSubjectRangeStartInPast', () => {
  it('returns true when the RANGE start date is before today', () => {
    expect(
      isSubjectRangeStartInPast(
        { exam_date_type: 'RANGE', exam_date_from: '2026-01-01' },
        '2026-08-24',
      ),
    ).toBe(true)
  })

  it('returns false when the RANGE start date is today or later', () => {
    expect(
      isSubjectRangeStartInPast(
        { exam_date_type: 'RANGE', exam_date_from: '2026-08-24' },
        '2026-08-24',
      ),
    ).toBe(false)
    expect(
      isSubjectRangeStartInPast(
        { exam_date_type: 'RANGE', exam_date_from: '2027-01-01' },
        '2026-08-24',
      ),
    ).toBe(false)
  })

  it('returns false for FIXED-type subjects regardless of dates', () => {
    expect(
      isSubjectRangeStartInPast(
        { exam_date_type: 'FIXED', exam_date_from: null },
        '2026-08-24',
      ),
    ).toBe(false)
  })

  it('returns false when exam_date_from or today is not yet available', () => {
    expect(
      isSubjectRangeStartInPast({ exam_date_type: 'RANGE', exam_date_from: null }, '2026-08-24'),
    ).toBe(false)
    expect(
      isSubjectRangeStartInPast(
        { exam_date_type: 'RANGE', exam_date_from: '2026-01-01' },
        undefined,
      ),
    ).toBe(false)
  })
})
