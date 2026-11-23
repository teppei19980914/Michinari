import { describe, expect, it } from 'vitest'
import { computeDelayDays, isDelayed } from './scheduleDelay'

describe('computeDelayDays', () => {
  it('未着手で本日が予定終了日と同じ日は遅れていない（境界値）', () => {
    const item = {
      status: 'NOT_STARTED' as const,
      planned_end_date: '2026-11-23',
      actual_end_date: null,
    }
    expect(computeDelayDays(item, '2026-11-23')).toBeNull()
  })

  it('未着手で本日が予定終了日の翌日なら1日の遅れ（境界値）', () => {
    const item = {
      status: 'NOT_STARTED' as const,
      planned_end_date: '2026-11-23',
      actual_end_date: null,
    }
    expect(computeDelayDays(item, '2026-11-24')).toBe(1)
  })

  it('進行中で本日が予定終了日を過ぎていれば遅れ日数を返す', () => {
    const item = {
      status: 'IN_PROGRESS' as const,
      planned_end_date: '2026-11-20',
      actual_end_date: null,
    }
    expect(computeDelayDays(item, '2026-11-23')).toBe(3)
  })

  it('完了していても実績終了日が無ければnull（データ上は発生しない想定の防御的分岐）', () => {
    const item = {
      status: 'DONE' as const,
      planned_end_date: '2026-11-20',
      actual_end_date: null,
    }
    expect(computeDelayDays(item, '2026-12-01')).toBeNull()
  })

  it('完了していて実績終了日が予定終了日より後なら遅れ日数を返す', () => {
    const item = {
      status: 'DONE' as const,
      planned_end_date: '2026-11-20',
      actual_end_date: '2026-11-25',
    }
    expect(computeDelayDays(item, '2026-12-01')).toBe(5)
  })

  it('完了していて実績終了日が予定終了日以前なら遅れていない', () => {
    const item = {
      status: 'DONE' as const,
      planned_end_date: '2026-11-20',
      actual_end_date: '2026-11-18',
    }
    expect(computeDelayDays(item, '2026-12-01')).toBeNull()
  })

  it('中止の行は対象外', () => {
    const item = {
      status: 'CANCELLED' as const,
      planned_end_date: '2026-11-20',
      actual_end_date: null,
    }
    expect(computeDelayDays(item, '2026-12-01')).toBeNull()
  })

  it('isDelayedはcomputeDelayDaysがnullでないときにtrueを返す', () => {
    const delayed = {
      status: 'IN_PROGRESS' as const,
      planned_end_date: '2026-11-20',
      actual_end_date: null,
    }
    const onTime = {
      status: 'IN_PROGRESS' as const,
      planned_end_date: '2026-12-20',
      actual_end_date: null,
    }
    expect(isDelayed(delayed, '2026-11-23')).toBe(true)
    expect(isDelayed(onTime, '2026-11-23')).toBe(false)
  })
})
