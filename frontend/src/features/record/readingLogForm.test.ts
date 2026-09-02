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
    expect(values[1]).toEqual({ recallBody: '', pagesRead: '', currentPage: '' })
  })

  it('prefills from an existing reading log', () => {
    const existing: ReadingLogRead = {
      id: 100,
      book_id: 1,
      recall_body: '第1章を読んだ',
      pages_read: 20,
      current_page: 20,
    }
    const values = initReadingLogFormValues([BOOK], [existing])
    expect(values[1]).toEqual({
      recallBody: '第1章を読んだ',
      pagesRead: '20',
      currentPage: '20',
    })
  })
})

describe('hasAnyReadingLogInput', () => {
  it('is false when every row is untouched', () => {
    const values: Record<number, ReadingLogFormValue> = {
      1: { recallBody: '', pagesRead: '', currentPage: '' },
    }
    expect(hasAnyReadingLogInput(values)).toBe(false)
  })

  it('is true once a row has a recall body', () => {
    const values: Record<number, ReadingLogFormValue> = {
      1: { recallBody: '今日読んだ', pagesRead: '', currentPage: '' },
    }
    expect(hasAnyReadingLogInput(values)).toBe(true)
  })
})

describe('buildReadingLogPayload', () => {
  it('excludes rows with no recall_body entered', () => {
    const values: Record<number, ReadingLogFormValue> = {
      1: { recallBody: '', pagesRead: '10', currentPage: '10' },
      2: { recallBody: '想起本文', pagesRead: '5', currentPage: '25' },
    }
    expect(buildReadingLogPayload(values)).toEqual([
      { book_id: 2, recall_body: '想起本文', pages_read: 5, current_page: 25 },
    ])
  })

  it('converts blank optional fields to null', () => {
    const values: Record<number, ReadingLogFormValue> = {
      1: { recallBody: '想起本文', pagesRead: '', currentPage: '' },
    }
    expect(buildReadingLogPayload(values)).toEqual([
      { book_id: 1, recall_body: '想起本文', pages_read: null, current_page: null },
    ])
  })
})
