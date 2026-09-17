import { describe, expect, it } from 'vitest'
import { resolveZeroRecordCategories } from './resolveZeroRecordCategories'
import type { CategoryPresence } from './categoryCompletion'
import type { DailyRecordRead } from '../../api/records'

const ALL_PRESENT: CategoryPresence = {
  hasExamCategory: true,
  hasReadingCategory: true,
  hasWorkCategory: true,
}

type RecordStates = Pick<
  DailyRecordRead,
  'exam_record_state' | 'reading_record_state' | 'work_record_state'
>

const UNTOUCHED: RecordStates = {
  exam_record_state: null,
  reading_record_state: null,
  work_record_state: null,
}

describe('resolveZeroRecordCategories', () => {
  it('includes every active-and-untouched category', () => {
    expect(resolveZeroRecordCategories(ALL_PRESENT, UNTOUCHED)).toEqual([
      'EXAM',
      'READING',
      'WORK',
    ])
  })

  it('excludes a category with no active goal that day', () => {
    const presence: CategoryPresence = { ...ALL_PRESENT, hasReadingCategory: false }
    expect(resolveZeroRecordCategories(presence, UNTOUCHED)).toEqual(['EXAM', 'WORK'])
  })

  it('excludes a category that already has progress-only data', () => {
    const record: RecordStates = { ...UNTOUCHED, exam_record_state: 'PROGRESS_ONLY' }
    expect(resolveZeroRecordCategories(ALL_PRESENT, record)).toEqual(['READING', 'WORK'])
  })

  it('excludes an already-reported category', () => {
    const record: RecordStates = { ...UNTOUCHED, work_record_state: 'REPORTED' }
    expect(resolveZeroRecordCategories(ALL_PRESENT, record)).toEqual(['EXAM', 'READING'])
  })

  it('returns an empty list when nothing is eligible', () => {
    const presence: CategoryPresence = {
      hasExamCategory: false,
      hasReadingCategory: false,
      hasWorkCategory: false,
    }
    expect(resolveZeroRecordCategories(presence, UNTOUCHED)).toEqual([])
  })
})
