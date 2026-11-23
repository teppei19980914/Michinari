import { describe, expect, it } from 'vitest'
import { applyScheduleStatusAutoFill } from './scheduleStatusAutoFill'

const TODAY = '2026-11-23'

describe('applyScheduleStatusAutoFill', () => {
  it('進行中へ変更：実績開始日が空なら本日を入れ、実績終了日は消す', () => {
    const result = applyScheduleStatusAutoFill(
      'IN_PROGRESS',
      { actualStartDate: null, actualEndDate: '2026-11-20' },
      TODAY,
    )
    expect(result).toEqual({ actualStartDate: TODAY, actualEndDate: null })
  })

  it('進行中へ変更：実績開始日が既にあれば変更しない', () => {
    const result = applyScheduleStatusAutoFill(
      'IN_PROGRESS',
      { actualStartDate: '2026-11-10', actualEndDate: null },
      TODAY,
    )
    expect(result).toEqual({ actualStartDate: '2026-11-10', actualEndDate: null })
  })

  it('完了へ変更：実績開始日・実績終了日とも空なら両方に本日を入れる', () => {
    const result = applyScheduleStatusAutoFill(
      'DONE',
      { actualStartDate: null, actualEndDate: null },
      TODAY,
    )
    expect(result).toEqual({ actualStartDate: TODAY, actualEndDate: TODAY })
  })

  it('完了へ変更：既にある値は変更しない', () => {
    const result = applyScheduleStatusAutoFill(
      'DONE',
      { actualStartDate: '2026-11-10', actualEndDate: '2026-11-15' },
      TODAY,
    )
    expect(result).toEqual({ actualStartDate: '2026-11-10', actualEndDate: '2026-11-15' })
  })

  it('未着手へ変更：実績日を両方消す', () => {
    const result = applyScheduleStatusAutoFill(
      'NOT_STARTED',
      { actualStartDate: '2026-11-10', actualEndDate: '2026-11-15' },
      TODAY,
    )
    expect(result).toEqual({ actualStartDate: null, actualEndDate: null })
  })

  it('中止へ変更：現在の値を変更しない', () => {
    const current = { actualStartDate: '2026-11-10', actualEndDate: null }
    expect(applyScheduleStatusAutoFill('CANCELLED', current, TODAY)).toEqual(current)
  })
})
