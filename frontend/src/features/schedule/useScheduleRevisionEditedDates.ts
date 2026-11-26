import { useState } from 'react'
import type { ScheduleRevisionProposalItemRead } from '../../api/schedule'

export type EditedDates = { start: string; end: string }

/**
 * 修正案の変更行で、承認前に利用者が修正した日付（D-56）を保持する。`ScheduleTab`が
 * 一元管理し、`ScheduleRevisionPanel`（入力欄）とガントの点線重ね表示（D-57「日付を
 * 修正した場合は修正後の値で表示」）の両方へ同じ値を渡す（CLAUDE.md DRYの原則）。
 */
export function useScheduleRevisionEditedDates() {
  const [editedDates, setEditedDates] = useState<Record<number, EditedDates>>({})

  function datesFor(item: ScheduleRevisionProposalItemRead): EditedDates {
    return (
      editedDates[item.id] ?? {
        start: item.proposed_planned_start_date ?? '',
        end: item.proposed_planned_end_date ?? '',
      }
    )
  }

  function setDates(itemId: number, dates: EditedDates) {
    setEditedDates((prev) => ({ ...prev, [itemId]: dates }))
  }

  function reset() {
    setEditedDates({})
  }

  return { datesFor, setDates, reset }
}
