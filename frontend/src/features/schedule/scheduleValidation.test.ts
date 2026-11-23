import { describe, expect, it } from 'vitest'
import {
  hasScheduleFieldErrors,
  validateScheduleItemFields,
  type ScheduleItemFieldsInput,
} from './scheduleValidation'

const TODAY = '2026-11-23'

function fields(overrides: Partial<ScheduleItemFieldsInput>): ScheduleItemFieldsInput {
  return {
    title: '作業A',
    plannedStartDate: '2026-11-01',
    plannedEndDate: '2026-11-10',
    status: 'NOT_STARTED',
    actualStartDate: null,
    actualEndDate: null,
    ...overrides,
  }
}

describe('validateScheduleItemFields', () => {
  it('全て正しい入力ならエラーが無い', () => {
    const errors = validateScheduleItemFields(fields({}), TODAY)
    expect(hasScheduleFieldErrors(errors)).toBe(false)
  })

  it('作業項目が空白のみなら必須エラー', () => {
    const errors = validateScheduleItemFields(fields({ title: '   ' }), TODAY)
    expect(errors.title).toBe('TITLE_REQUIRED')
  })

  it('予定開始日が予定終了日より後なら両方にエラー', () => {
    const errors = validateScheduleItemFields(
      fields({ plannedStartDate: '2026-11-10', plannedEndDate: '2026-11-01' }),
      TODAY,
    )
    expect(errors.plannedStartDate).toBe('PLANNED_RANGE_INVALID')
    expect(errors.plannedEndDate).toBe('PLANNED_RANGE_INVALID')
  })

  describe('未着手（NOT_STARTED）', () => {
    it('実績開始日・実績終了日とも無ければ正しい', () => {
      const errors = validateScheduleItemFields(fields({ status: 'NOT_STARTED' }), TODAY)
      expect(hasScheduleFieldErrors(errors)).toBe(false)
    })

    it('実績開始日があればエラー', () => {
      const errors = validateScheduleItemFields(
        fields({ status: 'NOT_STARTED', actualStartDate: '2026-11-05' }),
        TODAY,
      )
      expect(errors.actualStartDate).toBe('ACTUAL_NOT_ALLOWED')
    })

    it('実績終了日があればエラー', () => {
      const errors = validateScheduleItemFields(
        fields({ status: 'NOT_STARTED', actualEndDate: '2026-11-05' }),
        TODAY,
      )
      expect(errors.actualEndDate).toBe('ACTUAL_NOT_ALLOWED')
    })
  })

  describe('進行中（IN_PROGRESS）', () => {
    it('実績開始日のみあれば正しい', () => {
      const errors = validateScheduleItemFields(
        fields({ status: 'IN_PROGRESS', actualStartDate: '2026-11-05' }),
        TODAY,
      )
      expect(hasScheduleFieldErrors(errors)).toBe(false)
    })

    it('実績開始日が無ければ必須エラー', () => {
      const errors = validateScheduleItemFields(fields({ status: 'IN_PROGRESS' }), TODAY)
      expect(errors.actualStartDate).toBe('ACTUAL_START_REQUIRED')
    })

    it('実績終了日があれば入力不可エラー', () => {
      const errors = validateScheduleItemFields(
        fields({
          status: 'IN_PROGRESS',
          actualStartDate: '2026-11-05',
          actualEndDate: '2026-11-06',
        }),
        TODAY,
      )
      expect(errors.actualEndDate).toBe('ACTUAL_END_NOT_ALLOWED')
    })
  })

  describe('完了（DONE）', () => {
    it('実績開始日・実績終了日の両方があれば正しい', () => {
      const errors = validateScheduleItemFields(
        fields({
          status: 'DONE',
          actualStartDate: '2026-11-05',
          actualEndDate: '2026-11-06',
        }),
        TODAY,
      )
      expect(hasScheduleFieldErrors(errors)).toBe(false)
    })

    it('実績開始日が無ければ必須エラー', () => {
      const errors = validateScheduleItemFields(
        fields({ status: 'DONE', actualEndDate: '2026-11-06' }),
        TODAY,
      )
      expect(errors.actualStartDate).toBe('ACTUAL_START_REQUIRED')
    })

    it('実績終了日が無ければ必須エラー', () => {
      const errors = validateScheduleItemFields(
        fields({ status: 'DONE', actualStartDate: '2026-11-05' }),
        TODAY,
      )
      expect(errors.actualEndDate).toBe('ACTUAL_END_REQUIRED')
    })
  })

  describe('中止（CANCELLED）', () => {
    it('実績日が両方無くても正しい', () => {
      const errors = validateScheduleItemFields(fields({ status: 'CANCELLED' }), TODAY)
      expect(hasScheduleFieldErrors(errors)).toBe(false)
    })

    it('実績開始日のみあれば正しい', () => {
      const errors = validateScheduleItemFields(
        fields({ status: 'CANCELLED', actualStartDate: '2026-11-05' }),
        TODAY,
      )
      expect(hasScheduleFieldErrors(errors)).toBe(false)
    })

    it('実績終了日のみはエラー', () => {
      const errors = validateScheduleItemFields(
        fields({ status: 'CANCELLED', actualEndDate: '2026-11-05' }),
        TODAY,
      )
      expect(errors.actualEndDate).toBe('ACTUAL_END_ONLY_NOT_ALLOWED')
    })
  })

  it('実績開始日が実績終了日より後なら両方にエラー', () => {
    const errors = validateScheduleItemFields(
      fields({
        status: 'DONE',
        actualStartDate: '2026-11-10',
        actualEndDate: '2026-11-05',
      }),
      TODAY,
    )
    expect(errors.actualStartDate).toBe('ACTUAL_RANGE_INVALID')
    expect(errors.actualEndDate).toBe('ACTUAL_RANGE_INVALID')
  })

  it('実績開始日が本日より未来なら未来日エラー', () => {
    const errors = validateScheduleItemFields(
      fields({ status: 'IN_PROGRESS', actualStartDate: '2026-11-24' }),
      TODAY,
    )
    expect(errors.actualStartDate).toBe('ACTUAL_DATE_IN_FUTURE')
  })

  it('実績終了日が本日より未来なら未来日エラー', () => {
    const errors = validateScheduleItemFields(
      fields({
        status: 'DONE',
        actualStartDate: '2026-11-05',
        actualEndDate: '2026-11-24',
      }),
      TODAY,
    )
    expect(errors.actualEndDate).toBe('ACTUAL_DATE_IN_FUTURE')
  })

  it('実績日が本日と同じなら許容する（境界値）', () => {
    const errors = validateScheduleItemFields(
      fields({ status: 'IN_PROGRESS', actualStartDate: TODAY }),
      TODAY,
    )
    expect(hasScheduleFieldErrors(errors)).toBe(false)
  })
})
