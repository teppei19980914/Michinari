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
  slot_defaults: [{ slot_id: 10, slot_name: '夜', minutes: 45 }],
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
  slot_defaults: [{ slot_id: 10, slot_name: '夜', minutes: 20 }],
}

describe('initStudyLogFormValues', () => {
  it('defaults the cycle number and the per-slot minutes from the allocation', () => {
    const values = initStudyLogFormValues([QUOTA_PERCENT], [])
    expect(values[1]).toEqual({
      slotMinutes: { 10: '45' },
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
      slot_minutes: [{ slot_id: 10, slot_name: '夜', minutes: 30 }],
      amount_completed: 5,
      cycle_number: 1,
      quality_value: 80,
    }
    const values = initStudyLogFormValues([QUOTA_SUBJECTIVE], [existing])
    expect(values[2]).toEqual({
      slotMinutes: { 10: '30' },
      amountCompleted: '5',
      cycleNumber: '1',
      qualityValue: '4',
    })
  })

  it('keeps an objective quality value as-is', () => {
    const existing: StudyLogRead = {
      id: 101,
      material_id: 1,
      minutes_spent: 45,
      slot_minutes: [{ slot_id: 10, slot_name: '夜', minutes: 45 }],
      amount_completed: 8,
      cycle_number: 2,
      quality_value: 72,
    }
    // OBJECTIVE は正規化せずそのまま表示する（1〜5への逆変換は SUBJECTIVE のみ）。
    expect(initStudyLogFormValues([QUOTA_PERCENT], [existing])[1].qualityValue).toBe('72')
  })

  it('leaves the quality field blank when the existing log has no quality value', () => {
    const existing: StudyLogRead = {
      id: 102,
      material_id: 1,
      minutes_spent: 45,
      slot_minutes: [],
      amount_completed: 8,
      cycle_number: 2,
      quality_value: null,
    }
    expect(initStudyLogFormValues([QUOTA_PERCENT], [existing])[1].qualityValue).toBe('')
  })

  it('blanks a subjective value that does not map back onto the 1-5 scale', () => {
    // 主観スケールは 20/40/60/80/100 のみが 1〜5 に逆変換できる。それ以外の保存値
    // （方式変更の前後などで混ざり得る）は選択欄に出せないため空欄にする。
    const existing: StudyLogRead = {
      id: 103,
      material_id: 2,
      minutes_spent: 30,
      slot_minutes: [],
      amount_completed: 5,
      cycle_number: 1,
      quality_value: 75,
    }
    expect(initStudyLogFormValues([QUOTA_SUBJECTIVE], [existing])[2].qualityValue).toBe('')
  })
})

describe('hasAnyStudyLogInput', () => {
  it('is false when every row is untouched', () => {
    const values: Record<number, StudyLogFormValue> = {
      1: { slotMinutes: {}, amountCompleted: '', cycleNumber: '2', qualityValue: '' },
    }
    expect(hasAnyStudyLogInput(values)).toBe(false)
  })

  it('is true once a row has an amount', () => {
    const values: Record<number, StudyLogFormValue> = {
      1: { slotMinutes: {}, amountCompleted: '3', cycleNumber: '2', qualityValue: '' },
    }
    expect(hasAnyStudyLogInput(values)).toBe(true)
  })
})

describe('buildStudyLogPayload', () => {
  it('excludes rows with no amount_completed entered', () => {
    const values: Record<number, StudyLogFormValue> = {
      1: { slotMinutes: {}, amountCompleted: '', cycleNumber: '2', qualityValue: '' },
      2: { slotMinutes: { 10: '30' }, amountCompleted: '5', cycleNumber: '1', qualityValue: '4' },
    }
    expect(buildStudyLogPayload(values)).toEqual([
      {
        material_id: 2,
        slot_minutes: [{ slot_id: 10, minutes: 30 }],
        amount_completed: 5,
        cycle_number: 1,
        quality_value: 4,
      },
    ])
  })

  it('converts blank optional fields to null and sends no slot minutes when all are blank', () => {
    const values: Record<number, StudyLogFormValue> = {
      1: { slotMinutes: { 10: '' }, amountCompleted: '0', cycleNumber: '', qualityValue: '' },
    }
    expect(buildStudyLogPayload(values)).toEqual([
      {
        material_id: 1,
        slot_minutes: [],
        amount_completed: 0,
        cycle_number: null,
        quality_value: null,
      },
    ])
  })

  it('sends minutes per slot when several time slots were used for one material', () => {
    const values: Record<number, StudyLogFormValue> = {
      1: {
        slotMinutes: { 10: '30', 11: '15' },
        amountCompleted: '8',
        cycleNumber: '1',
        qualityValue: '',
      },
    }
    expect(buildStudyLogPayload(values)[0].slot_minutes).toEqual([
      { slot_id: 10, minutes: 30 },
      { slot_id: 11, minutes: 15 },
    ])
  })
})
