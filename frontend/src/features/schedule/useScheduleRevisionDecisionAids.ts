import { useScheduleRevisionBlockedReasons } from './useScheduleRevisionBlockedReasons'
import { useScheduleRevisionEditedDates } from './useScheduleRevisionEditedDates'
import type { ScheduleRevisionDecisionsResponse } from '../../api/schedule'

/**
 * `ScheduleRevisionPanel`へ渡す日付編集（D-56）とブロック理由（修正1、開発Todo_
 * スケジュール・ガントチャート_検証修正_v1.0.md）をまとめる。日付を直すと、同じ行の
 * ブロック理由も消える（再承認できることを示すため）。`ScheduleTab`を1関数100行以内に
 * 収めるための分離（CODING_RULES.md「保守性（複雑度）」、`useScheduleTabErrorToasts`等と
 * 同じ方針）。
 */
export function useScheduleRevisionDecisionAids(
  outcomes: ScheduleRevisionDecisionsResponse['outcomes'] | undefined,
) {
  const { datesFor, setDates } = useScheduleRevisionEditedDates()
  const { reasonFor: blockedReasonFor, clearReason: clearBlockedReason } =
    useScheduleRevisionBlockedReasons(outcomes)

  function setDatesAndClearBlockedReason(itemId: number, dates: { start: string; end: string }) {
    clearBlockedReason(itemId)
    setDates(itemId, dates)
  }

  return { datesFor, setDates: setDatesAndClearBlockedReason, blockedReasonFor }
}
