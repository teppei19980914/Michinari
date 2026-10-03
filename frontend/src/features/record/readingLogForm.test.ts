import { describe, expect, it } from 'vitest'
import {
  buildReadingLogPayload,
  combineRecallBody,
  getReadingLogQuestions,
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
    expect(values[1]).toEqual({
      questionAnswers: ['', ''],
      freeText: '',
      slotMinutes: {},
      currentPage: '',
    })
  })

  it('prefills the free-write field from an existing reading log, including the per-slot reading minutes', () => {
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
      questionAnswers: ['', ''],
      freeText: '第1章を読んだ',
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
      1: { questionAnswers: ['', ''], freeText: '', slotMinutes: {}, currentPage: '' },
    }
    expect(hasAnyReadingLogInput(values)).toBe(false)
  })

  it('is true once a row has free-write text', () => {
    const values: Record<number, ReadingLogFormValue> = {
      1: { questionAnswers: ['', ''], freeText: '今日読んだ', slotMinutes: {}, currentPage: '' },
    }
    expect(hasAnyReadingLogInput(values)).toBe(true)
  })

  it('is true once a row has a question answer', () => {
    const values: Record<number, ReadingLogFormValue> = {
      1: { questionAnswers: ['回答', ''], freeText: '', slotMinutes: {}, currentPage: '' },
    }
    expect(hasAnyReadingLogInput(values)).toBe(true)
  })
})

describe('combineRecallBody', () => {
  it('returns the free-write text as-is when no question is answered (backward compatibility)', () => {
    expect(
      combineRecallBody({ questionAnswers: ['', ''], freeText: '今日読んだ', slotMinutes: {}, currentPage: '' }),
    ).toBe('今日読んだ')
  })

  it('labels answered questions and appends the free-write text', () => {
    const [question1] = getReadingLogQuestions()
    expect(
      combineRecallBody({
        questionAnswers: ['回答1', ''],
        freeText: '自由記述',
        slotMinutes: {},
        currentPage: '',
      }),
    ).toBe(`【${question1}】\n回答1\n\n自由記述`)
  })
})

describe('buildReadingLogPayload', () => {
  it('excludes rows with no input entered', () => {
    const values: Record<number, ReadingLogFormValue> = {
      1: { questionAnswers: ['', ''], freeText: '', slotMinutes: {}, currentPage: '10' },
      2: { questionAnswers: ['', ''], freeText: '想起本文', slotMinutes: {}, currentPage: '25' },
    }
    expect(buildReadingLogPayload(values)).toEqual([
      { book_id: 2, recall_body: '想起本文', slot_minutes: [], current_page: 25 },
    ])
  })

  it('converts blank optional fields to null', () => {
    const values: Record<number, ReadingLogFormValue> = {
      1: { questionAnswers: ['', ''], freeText: '想起本文', slotMinutes: {}, currentPage: '' },
    }
    expect(buildReadingLogPayload(values)).toEqual([
      { book_id: 1, recall_body: '想起本文', slot_minutes: [], current_page: null },
    ])
  })
})
