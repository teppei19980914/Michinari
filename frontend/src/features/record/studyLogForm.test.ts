import { describe, expect, it } from 'vitest'
import {
  buildStudyLogPayload,
  hasAnyStudyLogInput,
  initStudyLogFormValues,
  type StudyLogFormValue,
} from './studyLogForm'
import type { QuotaItemRead } from '../../api/records'
import type { components } from '../../types/api.d.ts'

type StudyLogRead = components['schemas']['StudyLogRead']

const QUOTA_PERCENT: QuotaItemRead = {
  material_id: 1,
  material_name: '教材A',
  unit_label: 'ページ',
  current_cycle: 2,
  planned_cycles: 3,
  daily_quota: 5,
  quality_metric_type: 'OBJECTIVE',
  goal_id: 1,
  goal_name: '目標A',
}

const QUOTA_SUBJECTIVE: QuotaItemRead = {
  material_id: 2,
  material_name: '教材B',
  unit_label: '問',
  current_cycle: 1,
  planned_cycles: 1,
  daily_quota: 10,
  quality_metric_type: 'SUBJECTIVE',
  goal_id: 1,
  goal_name: '目標A',
}

describe('initStudyLogFormValues', () => {
  it('defaults the cycle number to the quota current_cycle when no existing log', () => {
    const values = initStudyLogFormValues([QUOTA_PERCENT], [])
    expect(values[1]).toEqual({
      minutesSpent: '',
      amountCompleted: '',
      cycleNumber: '2',
      qualityValue: '',
    })
  })

  it('prefills from an existing study log, converting a normalized subjective value back to 1-5', () => {
    const existing: StudyLogRead = {
      id: 100,
      material_id: 2,
      minutes_spent: 30,
      amount_completed: 5,
      cycle_number: 1,
      quality_value: 80,
    }
    const values = initStudyLogFormValues([QUOTA_SUBJECTIVE], [existing])
    expect(values[2]).toEqual({
      minutesSpent: '30',
      amountCompleted: '5',
      cycleNumber: '1',
      qualityValue: '4',
    })
  })
})

describe('hasAnyStudyLogInput', () => {
  it('is false when every row is untouched', () => {
    const values: Record<number, StudyLogFormValue> = {
      1: { minutesSpent: '', amountCompleted: '', cycleNumber: '2', qualityValue: '' },
    }
    expect(hasAnyStudyLogInput(values)).toBe(false)
  })

  it('is true once a row has an amount', () => {
    const values: Record<number, StudyLogFormValue> = {
      1: { minutesSpent: '', amountCompleted: '3', cycleNumber: '2', qualityValue: '' },
    }
    expect(hasAnyStudyLogInput(values)).toBe(true)
  })
})

describe('buildStudyLogPayload', () => {
  it('excludes rows with no amount_completed entered', () => {
    const values: Record<number, StudyLogFormValue> = {
      1: { minutesSpent: '', amountCompleted: '', cycleNumber: '2', qualityValue: '' },
      2: { minutesSpent: '30', amountCompleted: '5', cycleNumber: '1', qualityValue: '4' },
    }
    expect(buildStudyLogPayload(values)).toEqual([
      {
        material_id: 2,
        minutes_spent: 30,
        amount_completed: 5,
        cycle_number: 1,
        quality_value: 4,
      },
    ])
  })

  it('converts blank optional fields to null', () => {
    const values: Record<number, StudyLogFormValue> = {
      1: { minutesSpent: '', amountCompleted: '0', cycleNumber: '', qualityValue: '' },
    }
    expect(buildStudyLogPayload(values)).toEqual([
      {
        material_id: 1,
        minutes_spent: null,
        amount_completed: 0,
        cycle_number: null,
        quality_value: null,
      },
    ])
  })
})
