import { describe, expect, it } from 'vitest'
import { computeDelayDays, computeDelayInfo, isDelayed } from './scheduleDelay'

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

describe('computeDelayInfo（開始の遅れ、単位5・13.2・14章補足4）', () => {
  it('未着手で本日が予定開始日と同じ日は開始の遅れではない（境界値）', () => {
    const item = {
      status: 'NOT_STARTED' as const,
      planned_start_date: '2026-11-10',
      planned_end_date: '2026-12-31',
      actual_end_date: null,
    }
    expect(computeDelayInfo(item, '2026-11-10')).toBeNull()
  })

  it('未着手で本日が予定開始日の翌日なら開始の遅れ1日（境界値）', () => {
    const item = {
      status: 'NOT_STARTED' as const,
      planned_start_date: '2026-11-10',
      planned_end_date: '2026-12-31',
      actual_end_date: null,
    }
    expect(computeDelayInfo(item, '2026-11-11')).toEqual({ kind: 'START_DELAY', days: 1 })
  })

  it('予定終了日も過ぎている場合は終了の遅れを優先する', () => {
    const item = {
      status: 'NOT_STARTED' as const,
      planned_start_date: '2026-11-10',
      planned_end_date: '2026-11-20',
      actual_end_date: null,
    }
    expect(computeDelayInfo(item, '2026-12-01')).toEqual({ kind: 'END_DELAY', days: 11 })
  })

  it('進行中の行は開始の遅れの対象外（既に着手済み）', () => {
    const item = {
      status: 'IN_PROGRESS' as const,
      planned_start_date: '2026-11-10',
      planned_end_date: '2026-12-31',
      actual_end_date: null,
    }
    expect(computeDelayInfo(item, '2026-11-15')).toBeNull()
  })

  it('planned_start_dateを省略した場合は開始の遅れを判定しない（既存の呼び出し元向けの後方互換）', () => {
    const item = {
      status: 'NOT_STARTED' as const,
      planned_end_date: '2026-12-31',
      actual_end_date: null,
    }
    expect(computeDelayInfo(item, '2026-11-15')).toBeNull()
  })
})
