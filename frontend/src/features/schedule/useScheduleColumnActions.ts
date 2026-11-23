import { useRef } from 'react'
import { moveByOffset } from './scheduleRowOrdering'
import { columnKey, type ScheduleDraft, type ScheduleDraftColumn } from './scheduleDraftTypes'

/** 追加列の編集操作（D-12）。`useScheduleEditorState`から分離（複雑度対策）。 */
export function useScheduleColumnActions(
  draft: ScheduleDraft | null,
  setDraft: (updater: (prev: ScheduleDraft | null) => ScheduleDraft | null) => void,
) {
  const nextTempId = useRef(0)
  const generateTempKey = (prefix: string) => `${prefix}-${(nextTempId.current += 1)}`

  function addColumn() {
    const tempKey = generateTempKey('col')
    const newColumn: ScheduleDraftColumn = {
      key: columnKey(null, tempKey),
      id: null,
      tempKey,
      name: '',
    }
    setDraft((prev) =>
      prev
        ? {
            ...prev,
            columns: [...prev.columns, newColumn],
            items: prev.items.map((item) => ({
              ...item,
              cells: { ...item.cells, [newColumn.key]: '' },
            })),
          }
        : prev,
    )
  }

  function renameColumn(columnKeyValue: string, name: string) {
    setDraft((prev) =>
      prev
        ? {
            ...prev,
            columns: prev.columns.map((column) =>
              column.key === columnKeyValue ? { ...column, name } : column,
            ),
          }
        : prev,
    )
  }

  function moveColumn(columnKeyValue: string, offset: number) {
    setDraft((prev) => {
      if (!prev) return prev
      const index = prev.columns.findIndex((column) => column.key === columnKeyValue)
      if (index === -1) return prev
      return { ...prev, columns: moveByOffset(prev.columns, index, offset) }
    })
  }

  function removeColumn(columnKeyValue: string) {
    setDraft((prev) =>
      prev
        ? { ...prev, columns: prev.columns.filter((column) => column.key !== columnKeyValue) }
        : prev,
    )
  }

  function columnHasAnyValue(columnKeyValue: string): boolean {
    return (draft?.items ?? []).some((item) => (item.cells[columnKeyValue] ?? '').trim() !== '')
  }

  return { addColumn, renameColumn, moveColumn, removeColumn, columnHasAnyValue }
}
