/** `use*.ts`はカバレッジ閾値の対象外（vite.config.ts）だが、非自明な状態遷移（判断APIの
 * 応答からブロック理由を保持・消去する）を持つため直接テストする
 * （useDailyReportScheduleRevisionBanner.test.tsと同じ方針）。 */
import { describe, expect, it } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useScheduleRevisionBlockedReasons } from './useScheduleRevisionBlockedReasons'
import type { ScheduleRevisionDecisionsResponse } from '../../api/schedule'

type Outcomes = ScheduleRevisionDecisionsResponse['outcomes']

describe('useScheduleRevisionBlockedReasons', () => {
  it('outcomesが無ければ理由を持たない', () => {
    const { result } = renderHook(() => useScheduleRevisionBlockedReasons(undefined))

    expect(result.current.reasonFor(1)).toBe(null)
  })

  it('INVALID_PLANNED_DATEの行だけ理由を保持する（修正1）', () => {
    const outcomes: Outcomes = [
      { proposal_item_id: 1, applied: false, blocked_reason: 'INVALID_PLANNED_DATE' },
      { proposal_item_id: 2, applied: true, blocked_reason: null },
    ]
    const { result, rerender } = renderHook(
      ({ outcomes }: { outcomes: Outcomes | undefined }) =>
        useScheduleRevisionBlockedReasons(outcomes),
      { initialProps: { outcomes: undefined as Outcomes | undefined } },
    )

    rerender({ outcomes })

    expect(result.current.reasonFor(1)).toBe('INVALID_PLANNED_DATE')
    expect(result.current.reasonFor(2)).toBe(null)
  })

  it('STALE_BEFORE_VALUE等、INVALID_PLANNED_DATE以外は保持しない', () => {
    const outcomes: Outcomes = [
      { proposal_item_id: 1, applied: false, blocked_reason: 'STALE_BEFORE_VALUE' },
    ]
    const { result, rerender } = renderHook(
      ({ outcomes }: { outcomes: Outcomes | undefined }) =>
        useScheduleRevisionBlockedReasons(outcomes),
      { initialProps: { outcomes: undefined as Outcomes | undefined } },
    )

    rerender({ outcomes })

    expect(result.current.reasonFor(1)).toBe(null)
  })

  it('次の判断で解消された行（applied=true）は理由を消す', () => {
    const blocked: Outcomes = [
      { proposal_item_id: 1, applied: false, blocked_reason: 'INVALID_PLANNED_DATE' },
    ]
    const resolved: Outcomes = [{ proposal_item_id: 1, applied: true, blocked_reason: null }]
    const { result, rerender } = renderHook(
      ({ outcomes }: { outcomes: Outcomes | undefined }) =>
        useScheduleRevisionBlockedReasons(outcomes),
      { initialProps: { outcomes: undefined as Outcomes | undefined } },
    )
    rerender({ outcomes: blocked })
    expect(result.current.reasonFor(1)).toBe('INVALID_PLANNED_DATE')

    rerender({ outcomes: resolved })

    expect(result.current.reasonFor(1)).toBe(null)
  })

  it('clearReasonで日付修正時に理由を消せる', () => {
    const outcomes: Outcomes = [
      { proposal_item_id: 1, applied: false, blocked_reason: 'INVALID_PLANNED_DATE' },
    ]
    const { result, rerender } = renderHook(
      ({ outcomes }: { outcomes: Outcomes | undefined }) =>
        useScheduleRevisionBlockedReasons(outcomes),
      { initialProps: { outcomes: undefined as Outcomes | undefined } },
    )
    rerender({ outcomes })
    expect(result.current.reasonFor(1)).toBe('INVALID_PLANNED_DATE')

    act(() => {
      result.current.clearReason(1)
    })

    expect(result.current.reasonFor(1)).toBe(null)
  })
})
