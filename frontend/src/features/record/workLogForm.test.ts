import { describe, expect, it } from 'vitest'
import {
  buildWorkLogPayload,
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
    expect(values[1]).toEqual({ body: '' })
  })

  it('prefills from an existing work log', () => {
    const existing: WorkLogRead = {
      id: 100,
      work_assignment_id: 1,
      body: '要件ヒアリングを実施した',
    }
    const values = initWorkLogFormValues([WORK_ASSIGNMENT], [existing])
    expect(values[1]).toEqual({ body: '要件ヒアリングを実施した' })
  })
})

describe('hasAnyWorkLogInput', () => {
  it('is false when every row is untouched', () => {
    const values: Record<number, WorkLogFormValue> = { 1: { body: '' } }
    expect(hasAnyWorkLogInput(values)).toBe(false)
  })

  it('is true once a row has a body', () => {
    const values: Record<number, WorkLogFormValue> = { 1: { body: '今日の業務内容' } }
    expect(hasAnyWorkLogInput(values)).toBe(true)
  })
})

describe('buildWorkLogPayload', () => {
  it('excludes rows with no body entered', () => {
    const values: Record<number, WorkLogFormValue> = {
      1: { body: '' },
      2: { body: '業務内容の記録' },
    }
    expect(buildWorkLogPayload(values)).toEqual([
      { work_assignment_id: 2, body: '業務内容の記録' },
    ])
  })
})
