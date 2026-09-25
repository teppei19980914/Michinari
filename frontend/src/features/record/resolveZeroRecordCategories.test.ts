import { describe, expect, it } from 'vitest'
import { resolveZeroRecordCategories, type VisibleCategorySections } from './resolveZeroRecordCategories'
import type { CategoryPresence } from './categoryCompletion'
import type { DailyRecordRead } from '../../api/records'

const ALL_PRESENT: CategoryPresence = {
  hasExamCategory: true,
  hasReadingCategory: true,
  hasWorkCategory: true,
}

const ALL_VISIBLE: VisibleCategorySections = {
  showExamSection: true,
  showReadingSection: true,
  showWorkSection: true,
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
  it('includes every active-and-untouched category that is visible', () => {
    expect(resolveZeroRecordCategories(ALL_PRESENT, UNTOUCHED, ALL_VISIBLE)).toEqual([
      'EXAM',
      'READING',
      'WORK',
    ])
  })

  it('excludes a category with no active goal that day', () => {
    const presence: CategoryPresence = { ...ALL_PRESENT, hasReadingCategory: false }
    expect(resolveZeroRecordCategories(presence, UNTOUCHED, ALL_VISIBLE)).toEqual(['EXAM', 'WORK'])
  })

  it('excludes a category that already has progress-only data', () => {
    const record: RecordStates = { ...UNTOUCHED, exam_record_state: 'PROGRESS_ONLY' }
    expect(resolveZeroRecordCategories(ALL_PRESENT, record, ALL_VISIBLE)).toEqual(['READING', 'WORK'])
  })

  it('excludes an already-reported category', () => {
    const record: RecordStates = { ...UNTOUCHED, work_record_state: 'REPORTED' }
    expect(resolveZeroRecordCategories(ALL_PRESENT, record, ALL_VISIBLE)).toEqual(['EXAM', 'READING'])
  })

  it('returns an empty list when nothing is eligible', () => {
    const presence: CategoryPresence = {
      hasExamCategory: false,
      hasReadingCategory: false,
      hasWorkCategory: false,
    }
    expect(resolveZeroRecordCategories(presence, UNTOUCHED, ALL_VISIBLE)).toEqual([])
  })

  it('excludes categories that are ACTIVE and untouched but not the currently selected tab', () => {
    // 目標タブで読書のみ選択中（資格試験・仕事はACTIVEかつ未操作だが非表示）を想定。
    // 2026-09-26報告: この絞り込みが無いと、読書タブでの操作が他カテゴリも確定させてしまう。
    const visibility: VisibleCategorySections = {
      showExamSection: false,
      showReadingSection: true,
      showWorkSection: false,
    }
    expect(resolveZeroRecordCategories(ALL_PRESENT, UNTOUCHED, visibility)).toEqual(['READING'])
  })

  it('returns an empty list when the eligible category is not the visible tab', () => {
    const visibility: VisibleCategorySections = {
      showExamSection: false,
      showReadingSection: false,
      showWorkSection: true,
    }
    const presence: CategoryPresence = { ...ALL_PRESENT, hasWorkCategory: false }
    expect(resolveZeroRecordCategories(presence, UNTOUCHED, visibility)).toEqual([])
  })
})
