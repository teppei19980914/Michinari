import { describe, expect, it } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useScheduleGridGeometry } from './useScheduleGridGeometry'

describe('useScheduleGridGeometry', () => {
  it('表示期間・1日分の幅・ガント全幅・本日線位置をまとめて返す', () => {
    const { result } = renderHook(() =>
      useScheduleGridGeometry(
        [
          {
            status: 'NOT_STARTED',
            planned_start_date: '2026-11-01',
            planned_end_date: '2026-11-10',
            actual_start_date: null,
            actual_end_date: null,
          },
        ],
        '2026-11-05',
        1.75,
        4.5,
        new Set<string>(),
        100,
        30,
      ),
    )

    expect(result.current.range).toEqual({ startIso: '2026-11-01', endIso: '2026-11-10' })
    expect(result.current.dayWidthRem).toBeGreaterThanOrEqual(1.75)
    expect(result.current.dayWidthRem).toBeLessThanOrEqual(4.5)
    expect(result.current.ganttWidthRem).toBeCloseTo(10 * result.current.dayWidthRem)
    expect(result.current.todayLineLeftRem).toBeGreaterThan(0)
  })
})
