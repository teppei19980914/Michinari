import { useRef } from 'react'
import type { ScheduleItemStatus } from '../../api/schedule'
import { applyScheduleStatusAutoFill } from './scheduleStatusAutoFill'
import { insertBelow, moveByOffset, removeAt } from './scheduleRowOrdering'
import { columnKey, type ScheduleDraft, type ScheduleDraftItem } from './scheduleDraftTypes'

/** 行・セルの編集操作（D-05〜D-11・D-13）。`useScheduleEditorState`から分離（複雑度対策）。 */
export function useScheduleRowActions(
  draft: ScheduleDraft | null,
  setDraft: (updater: (prev: ScheduleDraft | null) => ScheduleDraft | null) => void,
  today: string | null,
) {
  const nextTempId = useRef(0)
  const generateTempKey = (prefix: string) => `${prefix}-${(nextTempId.current += 1)}`

  function updateItem(itemKey: string, patch: Partial<ScheduleDraftItem>) {
    setDraft((prev) =>
      prev
        ? {
            ...prev,
            items: prev.items.map((item) => (item.key === itemKey ? { ...item, ...patch } : item)),
          }
        : prev,
    )
  }

  function changeStatus(itemKey: string, status: ScheduleItemStatus) {
    if (!draft || !today) return
    const item = draft.items.find((candidate) => candidate.key === itemKey)
    if (!item) return
    const filled = applyScheduleStatusAutoFill(
      status,
      { actualStartDate: item.actualStartDate, actualEndDate: item.actualEndDate },
      today,
    )
    updateItem(itemKey, { status, ...filled })
  }

  function updateCell(itemKey: string, columnKeyValue: string, value: string) {
    setDraft((prev) =>
      prev
        ? {
            ...prev,
            items: prev.items.map((item) =>
              item.key === itemKey
                ? { ...item, cells: { ...item.cells, [columnKeyValue]: value } }
                : item,
            ),
          }
        : prev,
    )
  }

  function buildNewItem(): ScheduleDraftItem {
    const tempKey = generateTempKey('row')
    const baseDate = today ?? ''
    return {
      key: columnKey(null, tempKey),
      id: null,
      tempKey,
      title: '',
      description: null,
      plannedStartDate: baseDate,
      plannedEndDate: baseDate,
      status: 'NOT_STARTED',
      actualStartDate: null,
      actualEndDate: null,
      cells: Object.fromEntries((draft?.columns ?? []).map((column) => [column.key, ''])),
    }
  }

  function addRow() {
    setDraft((prev) => (prev ? { ...prev, items: [...prev.items, buildNewItem()] } : prev))
  }

  function insertRowBelow(itemKey: string) {
    setDraft((prev) => {
      if (!prev) return prev
      const index = prev.items.findIndex((item) => item.key === itemKey)
      if (index === -1) return prev
      return { ...prev, items: insertBelow(prev.items, index, buildNewItem()) }
    })
  }

  function moveRow(itemKey: string, offset: number) {
    setDraft((prev) => {
      if (!prev) return prev
      const index = prev.items.findIndex((item) => item.key === itemKey)
      if (index === -1) return prev
      return { ...prev, items: moveByOffset(prev.items, index, offset) }
    })
  }

  function removeRow(itemKey: string) {
    setDraft((prev) => {
      if (!prev) return prev
      const index = prev.items.findIndex((item) => item.key === itemKey)
      if (index === -1) return prev
      return { ...prev, items: removeAt(prev.items, index) }
    })
  }

  return { updateItem, changeStatus, updateCell, addRow, insertRowBelow, moveRow, removeRow }
}
