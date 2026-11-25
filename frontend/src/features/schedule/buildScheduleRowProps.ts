import type {
  ScheduleDraftColumn,
  ScheduleDraftFieldKey,
  ScheduleDraftItem,
} from './scheduleDraftTypes'
import type { ScheduleItemFieldErrors } from './scheduleValidation'

/** `ScheduleDataRow`へ渡すprops一式を組み立てる（`ScheduleGrid`から分離、複雑度対策）。 */
export function buildScheduleRowProps(params: {
  item: ScheduleDraftItem
  index: number
  itemCount: number
  customColumns: ScheduleDraftColumn[]
  readOnly: boolean
  fieldErrorsByItemKey: Record<string, ScheduleItemFieldErrors>
  rowActionsLeftRem: number | null
  columnLeftOffsetsRem: (number | null)[]
  rangeStartIso: string
  dayWidthRem: number
  ganttWidthRem: number
  today: string
  //: schedule_item_id（ScheduleDraftItem.id）→ 未判断の修正案の日付（単位5・D-57）。
  proposedBandByItemId: Record<number, { start: string; end: string }>
  onMoveRow: (itemKey: string, offset: number) => void
  onInsertRowBelow: (itemKey: string) => void
  onRemoveRow: (itemKey: string) => void
  onFieldChange: (itemKey: string, field: ScheduleDraftFieldKey, value: string | null) => void
  onStatusChange: (itemKey: string, status: ScheduleDraftItem['status']) => void
  onCellChange: (itemKey: string, columnKey: string, value: string) => void
}) {
  const { item, index, itemCount } = params
  return {
    item,
    customColumns: params.customColumns,
    readOnly: params.readOnly,
    canMoveUp: index > 0,
    canMoveDown: index < itemCount - 1,
    fieldErrors: params.fieldErrorsByItemKey[item.key],
    rowActionsLeftRem: params.rowActionsLeftRem,
    columnLeftOffsetsRem: params.columnLeftOffsetsRem,
    rangeStartIso: params.rangeStartIso,
    dayWidthRem: params.dayWidthRem,
    ganttWidthRem: params.ganttWidthRem,
    today: params.today,
    proposedBand: item.id !== null ? params.proposedBandByItemId[item.id] ?? null : null,
    onMoveUp: () => params.onMoveRow(item.key, -1),
    onMoveDown: () => params.onMoveRow(item.key, 1),
    onInsertBelow: () => params.onInsertRowBelow(item.key),
    onDelete: () => params.onRemoveRow(item.key),
    onFieldChange: (field: ScheduleDraftFieldKey, value: string | null) =>
      params.onFieldChange(item.key, field, value),
    onStatusChange: (status: ScheduleDraftItem['status']) => params.onStatusChange(item.key, status),
    onCellChange: (columnKey: string, value: string) =>
      params.onCellChange(item.key, columnKey, value),
  }
}
