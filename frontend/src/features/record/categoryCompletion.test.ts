import { describe, expect, it } from 'vitest'
import { isAllCategoriesReported } from './categoryCompletion'

describe('isAllCategoriesReported', () => {
  it('returns false when no category has any active goal', () => {
    expect(
      isAllCategoriesReported(
        { hasExamCategory: false, hasReadingCategory: false, hasWorkCategory: false },
        { isExamReported: false, isReadingReported: false, isWorkReported: false },
      ),
    ).toBe(false)
  })

  it('returns true when the only existing category is reported', () => {
    expect(
      isAllCategoriesReported(
        { hasExamCategory: true, hasReadingCategory: false, hasWorkCategory: false },
        { isExamReported: true, isReadingReported: false, isWorkReported: false },
      ),
    ).toBe(true)
  })

  it('returns false when the only existing category is not yet reported', () => {
    expect(
      isAllCategoriesReported(
        { hasExamCategory: true, hasReadingCategory: false, hasWorkCategory: false },
        { isExamReported: false, isReadingReported: false, isWorkReported: false },
      ),
    ).toBe(false)
  })

  it('returns false when only one of three existing categories is reported (regression: must not treat the unselected tabs as absent)', () => {
    expect(
      isAllCategoriesReported(
        { hasExamCategory: true, hasReadingCategory: true, hasWorkCategory: true },
        { isExamReported: true, isReadingReported: false, isWorkReported: false },
      ),
    ).toBe(false)
  })

  it('returns true only once all three existing categories are reported', () => {
    expect(
      isAllCategoriesReported(
        { hasExamCategory: true, hasReadingCategory: true, hasWorkCategory: true },
        { isExamReported: true, isReadingReported: true, isWorkReported: true },
      ),
    ).toBe(true)
  })

  it('ignores a category with no active goal even if it is not reported', () => {
    // EXAM・WORKのみ目標があり、READINGは目標が無い日。READINGが未確定のままでも
    // EXAM・WORKが確定済みなら全体として確定済みとみなす。
    expect(
      isAllCategoriesReported(
        { hasExamCategory: true, hasReadingCategory: false, hasWorkCategory: true },
        { isExamReported: true, isReadingReported: false, isWorkReported: true },
      ),
    ).toBe(true)
  })
})
