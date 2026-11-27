import { useState } from 'react'
import type {
  ScheduleRevisionDecisionInput,
  ScheduleRevisionProposalItemRead,
} from '../../api/schedule'
import type { EditedDates } from './useScheduleRevisionEditedDates'

/**
 * `ScheduleRevisionPanel`の判断ハンドラ（承認・却下・確認済み・すべて承認・すべて却下）。
 * JSXから分離し、`ScheduleRevisionPanel`を1関数100行以内に収める
 * （CODING_RULES.md「保守性（複雑度）」）。
 */
export function useScheduleRevisionPanelActions(
  pendingChangeItems: ScheduleRevisionProposalItemRead[],
  datesFor: (item: ScheduleRevisionProposalItemRead) => EditedDates,
  onDecide: (decisions: ScheduleRevisionDecisionInput[]) => void,
  blockedReasonFor: (itemId: number) => string | null = () => null,
) {
  const [rejectReasons, setRejectReasons] = useState<Record<number, string>>({})

  function setRejectReason(itemId: number, reason: string) {
    setRejectReasons((prev) => ({ ...prev, [itemId]: reason }))
  }

  function approve(item: ScheduleRevisionProposalItemRead) {
    const dates = datesFor(item)
    onDecide([
      {
        proposal_item_id: item.id,
        decision: 'APPROVED',
        planned_start_date: dates.start,
        planned_end_date: dates.end,
      },
    ])
  }

  function reject(item: ScheduleRevisionProposalItemRead) {
    onDecide([
      {
        proposal_item_id: item.id,
        decision: 'REJECTED',
        reject_reason: rejectReasons[item.id] || null,
      },
    ])
  }

  function acknowledge(item: ScheduleRevisionProposalItemRead) {
    onDecide([{ proposal_item_id: item.id, decision: 'ACKNOWLEDGED' }])
  }

  function approveAll() {
    // 直前の承認が13.5の制約でブロックされた行（修正1）も、stale行と同様に対象から除く。
    const decisions: ScheduleRevisionDecisionInput[] = pendingChangeItems
      .filter((item) => !item.is_stale && !blockedReasonFor(item.id))
      .map((item) => {
        const dates = datesFor(item)
        return {
          proposal_item_id: item.id,
          decision: 'APPROVED',
          planned_start_date: dates.start,
          planned_end_date: dates.end,
        }
      })
    if (decisions.length > 0) onDecide(decisions)
  }

  function rejectAll() {
    const decisions: ScheduleRevisionDecisionInput[] = pendingChangeItems
      .filter((item) => !item.is_stale)
      .map((item) => ({
        proposal_item_id: item.id,
        decision: 'REJECTED',
        reject_reason: rejectReasons[item.id] || null,
      }))
    if (decisions.length > 0) onDecide(decisions)
  }

  return { rejectReasons, setRejectReason, approve, reject, acknowledge, approveAll, rejectAll }
}
