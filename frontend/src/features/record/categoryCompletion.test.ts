import { describe, expect, it } from 'vitest'
import type { DailyRecordRead } from '../../api/records'
import { isAllCategoriesReported, toCategoryReportedState } from './categoryCompletion'

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

describe('toCategoryReportedState', () => {
  function buildRecord(states: Partial<DailyRecordRead>): DailyRecordRead {
    return {
      exam_record_state: null,
      reading_record_state: null,
      work_record_state: null,
      ...states,
    } as DailyRecordRead
  }

  it('treats a record that has not been fetched yet as nothing reported', () => {
    // 取得前に確定済みとみなすと、未確定カテゴリの入力欄が一瞬だけ読み取り専用になる。
    expect(toCategoryReportedState(undefined)).toEqual({
      isExamReported: false,
      isReadingReported: false,
      isWorkReported: false,
    })
  })

  it('maps each category state independently', () => {
    expect(
      toCategoryReportedState(
        buildRecord({ exam_record_state: 'REPORTED', reading_record_state: 'PROGRESS_ONLY' }),
      ),
    ).toEqual({ isExamReported: true, isReadingReported: false, isWorkReported: false })
  })

  it('marks every category as reported once all three are finalized', () => {
    expect(
      toCategoryReportedState(
        buildRecord({
          exam_record_state: 'REPORTED',
          reading_record_state: 'REPORTED',
          work_record_state: 'REPORTED',
        }),
      ),
    ).toEqual({ isExamReported: true, isReadingReported: true, isWorkReported: true })
  })
})
