import { describe, expect, it } from 'vitest'
import {
  buildWorkLogPayload,
  combineWorkBody,
  getWorkLogQuestions,
  hasAnyWorkLogInput,
  initWorkLogFormValues,
  type WorkLogFormValue,
} from './workLogForm'
import type { WorkAssignmentRead } from '../../api/goals'
import type { components } from '../../types/api.d.ts'

type WorkLogRead = components['schemas']['WorkLogRead']

const WORK_ASSIGNMENT: WorkAssignmentRead = {
  id: 1,
  goal_id: 10,
  client_name: 'NewtonX',
  expected_content: '要件定義支援',
  start_date: '2026-01-01',
  elapsed_days: 20,
  last_work_date: null,
  current_streak: 0,
  has_recent_monthly_report: false,
}

describe('initWorkLogFormValues', () => {
  it('defaults to empty values when no existing log', () => {
    const values = initWorkLogFormValues([WORK_ASSIGNMENT], [])
    expect(values[1]).toEqual({ questionAnswers: ['', ''], freeText: '' })
  })

  it('prefills the free-write field from an existing work log', () => {
    const existing: WorkLogRead = {
      id: 100,
      work_assignment_id: 1,
      body: '要件ヒアリングを実施した',
    }
    const values = initWorkLogFormValues([WORK_ASSIGNMENT], [existing])
    expect(values[1]).toEqual({ questionAnswers: ['', ''], freeText: '要件ヒアリングを実施した' })
  })
})

describe('hasAnyWorkLogInput', () => {
  it('is false when every row is untouched', () => {
    const values: Record<number, WorkLogFormValue> = {
      1: { questionAnswers: ['', ''], freeText: '' },
    }
    expect(hasAnyWorkLogInput(values)).toBe(false)
  })

  it('is true once a row has free-write text', () => {
    const values: Record<number, WorkLogFormValue> = {
      1: { questionAnswers: ['', ''], freeText: '今日の業務内容' },
    }
    expect(hasAnyWorkLogInput(values)).toBe(true)
  })

  it('is true once a row has a question answer', () => {
    const values: Record<number, WorkLogFormValue> = {
      1: { questionAnswers: ['回答', ''], freeText: '' },
    }
    expect(hasAnyWorkLogInput(values)).toBe(true)
  })
})

describe('combineWorkBody', () => {
  it('returns the free-write text as-is when no question is answered (backward compatibility)', () => {
    expect(combineWorkBody({ questionAnswers: ['', ''], freeText: '今日の業務内容' })).toBe(
      '今日の業務内容',
    )
  })

  it('labels answered questions and appends the free-write text', () => {
    const [question1] = getWorkLogQuestions()
    expect(combineWorkBody({ questionAnswers: ['回答1', ''], freeText: '自由記述' })).toBe(
      `【${question1}】\n回答1\n\n自由記述`,
    )
  })
})

describe('buildWorkLogPayload', () => {
  it('excludes rows with no input entered', () => {
    const values: Record<number, WorkLogFormValue> = {
      1: { questionAnswers: ['', ''], freeText: '' },
      2: { questionAnswers: ['', ''], freeText: '業務内容の記録' },
    }
    expect(buildWorkLogPayload(values)).toEqual([
      { work_assignment_id: 2, body: '業務内容の記録' },
    ])
  })
})
