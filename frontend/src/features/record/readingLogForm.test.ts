import { describe, expect, it } from 'vitest'
import {
  buildReadingLogPayload,
  hasAnyReadingLogInput,
  initReadingLogFormValues,
  type ReadingLogFormValue,
} from './readingLogForm'
import type { BookRead } from '../../api/goals'
import type { components } from '../../types/api.d.ts'

type ReadingLogRead = components['schemas']['ReadingLogRead']

const BOOK: BookRead = {
  id: 1,
  goal_id: 10,
  title: '達人プログラマー',
  author: null,
  total_pages: 300,
  start_date: '2026-01-01',
  due_date: '2026-06-30',
  remaining_days: 20,
  last_reading_date: null,
  current_streak: 0,
  current_page: null,
  progress_rate: null,
}

describe('initReadingLogFormValues', () => {
  it('defaults to empty values when no existing log', () => {
    const values = initReadingLogFormValues([BOOK], [])
    expect(values[1]).toEqual({ slotMinutes: {}, recallBody: '', currentPage: '' })
  })

  it('prefills from an existing reading log, including the per-slot reading minutes', () => {
    const existing: ReadingLogRead = {
      id: 100,
      book_id: 1,
      recall_body: '第1章を読んだ',
      minutes_spent: 25,
      slot_minutes: [{ slot_id: 10, slot_name: '夜', minutes: 25 }],
      current_page: 20,
    }
    const values = initReadingLogFormValues([BOOK], [existing])
    expect(values[1]).toEqual({
      recallBody: '第1章を読んだ',
      slotMinutes: { 10: '25' },
      currentPage: '20',
    })
  })

  it('leaves the page field blank when the existing log has no current page', () => {
    // 現在ページは任意入力のため、未登録（null）を '0' ではなく空欄として復元する。
    const existing: ReadingLogRead = {
      id: 101,
      book_id: 1,
      recall_body: 'ページは記録していない',
      minutes_spent: 15,
      slot_minutes: [],
      current_page: null,
    }
    const values = initReadingLogFormValues([BOOK], [existing])
    expect(values[1].currentPage).toBe('')
  })
})

describe('hasAnyReadingLogInput', () => {
  it('is false when every row is untouched', () => {
    const values: Record<number, ReadingLogFormValue> = {
      1: { slotMinutes: {}, recallBody: '', currentPage: '' },
    }
    expect(hasAnyReadingLogInput(values)).toBe(false)
  })

  it('is true once a row has a recall body', () => {
    const values: Record<number, ReadingLogFormValue> = {
      1: { slotMinutes: {}, recallBody: '今日読んだ', currentPage: '' },
    }
    expect(hasAnyReadingLogInput(values)).toBe(true)
  })
})

describe('buildReadingLogPayload', () => {
  it('excludes rows with no recall_body entered', () => {
    const values: Record<number, ReadingLogFormValue> = {
      1: { slotMinutes: {}, recallBody: '', currentPage: '10' },
      2: { slotMinutes: {}, recallBody: '想起本文', currentPage: '25' },
    }
    expect(buildReadingLogPayload(values)).toEqual([
      { book_id: 2, recall_body: '想起本文', slot_minutes: [], current_page: 25 },
    ])
  })

  it('converts blank optional fields to null', () => {
    const values: Record<number, ReadingLogFormValue> = {
      1: { slotMinutes: {}, recallBody: '想起本文', currentPage: '' },
    }
    expect(buildReadingLogPayload(values)).toEqual([
      { book_id: 1, recall_body: '想起本文', slot_minutes: [], current_page: null },
    ])
  })
})
