import type { RefObject } from 'react'
import { ScheduleDataRow } from './ScheduleDataRow'
import { ScheduleFixedColumnsHeader } from './ScheduleFixedColumnsHeader'
import { ScheduleGanttHeader } from './ScheduleGanttHeader'
import { ScheduleOverlaidRows } from './ScheduleOverlaidRows'
import { buildScheduleRowProps } from './buildScheduleRowProps'
import type { DateRangeIso, DayTypeRun } from './scheduleGanttGeometry'
import type {
  ScheduleDraft,
  ScheduleDraftFieldKey,
  ScheduleDraftItem,
} from './scheduleDraftTypes'
import type { ScheduleItemFieldErrors } from './scheduleValidation'

type ScheduleGridBodyProps = {
  scrollRef: RefObject<HTMLDivElement | null>
  draft: ScheduleDraft
  readOnly: boolean
  frozenRowCount: number
  range: DateRangeIso
  dayWidthRem: number
  ganttWidthRem: number
  fixedAreaWidthRem: number
  dayTypeRuns: DayTypeRun[]
  todayLineLeftRem: number
  holidayIsoDates: ReadonlySet<string>
  holidayYearFrom: number | null
  holidayYearTo: number | null
  rowActionsLeftRem: number | null
  columnLeftOffsetsRem: (number | null)[]
  fieldErrorsByItemKey: Record<string, ScheduleItemFieldErrors>
  columnErrorsByKey: Record<string, 'NAME_REQUIRED' | 'DUPLICATE_NAME'>
  columnHasAnyValue: (columnKey: string) => boolean
  today: string
  proposedBandByItemId: Record<number, { start: string; end: string }>
  onMoveRow: (itemKey: string, offset: number) => void
  onInsertRowBelow: (itemKey: string) => void
  onRemoveRow: (itemKey: string) => void
  onFieldChange: (itemKey: string, field: ScheduleDraftFieldKey, value: string | null) => void
  onStatusChange: (itemKey: string, status: ScheduleDraftItem['status']) => void
  onCellChange: (itemKey: string, columnKey: string, value: string) => void
  onRenameColumn: (columnKey: string, name: string) => void
  onMoveColumn: (columnKey: string, offset: number) => void
  onRemoveColumn: (columnKey: string) => void
}

/** `ScheduleGrid`の描画部分（算出済みの座標一式を受け取るだけ）。複雑度対策で分離。 */
export function ScheduleGridBody({
  scrollRef,
  draft,
  readOnly,
  frozenRowCount,
  range,
  dayWidthRem,
  ganttWidthRem,
  fixedAreaWidthRem,
  dayTypeRuns,
  todayLineLeftRem,
  holidayIsoDates,
  holidayYearFrom,
  holidayYearTo,
  rowActionsLeftRem,
  columnLeftOffsetsRem,
  fieldErrorsByItemKey,
  columnErrorsByKey,
  columnHasAnyValue,
  today,
  proposedBandByItemId,
  onMoveRow,
  onInsertRowBelow,
  onRemoveRow,
  onFieldChange,
  onStatusChange,
  onCellChange,
  onRenameColumn,
  onMoveColumn,
  onRemoveColumn,
}: ScheduleGridBodyProps) {
  const frozenItems = draft.items.slice(0, frozenRowCount)
  const scrollableItems = draft.items.slice(frozenRowCount)

  const rowProps = (item: ScheduleDraftItem, index: number) =>
    buildScheduleRowProps({
      item,
      index,
      itemCount: draft.items.length,
      customColumns: draft.columns,
      readOnly,
      fieldErrorsByItemKey,
      rowActionsLeftRem,
      columnLeftOffsetsRem,
      rangeStartIso: range.startIso,
      dayWidthRem,
      ganttWidthRem,
      today,
      proposedBandByItemId,
      onMoveRow,
      onInsertRowBelow,
      onRemoveRow,
      onFieldChange,
      onStatusChange,
      onCellChange,
    })

  return (
    <div ref={scrollRef} className="overflow-x-auto" data-testid="schedule-grid-scroll">
      <div className="sticky top-0 z-20 bg-surface">
        <div className="flex">
          <ScheduleFixedColumnsHeader
            customColumns={draft.columns}
            readOnly={readOnly}
            rowActionsLeftRem={rowActionsLeftRem}
            columnLeftOffsetsRem={columnLeftOffsetsRem}
            columnErrorsByKey={columnErrorsByKey}
            columnHasAnyValue={columnHasAnyValue}
            onRenameColumn={onRenameColumn}
            onMoveColumn={onMoveColumn}
            onRemoveColumn={onRemoveColumn}
          />
          <ScheduleGanttHeader
            rangeStartIso={range.startIso}
            rangeEndIso={range.endIso}
            dayWidthRem={dayWidthRem}
            holidayIsoDates={holidayIsoDates}
            holidayYearFrom={holidayYearFrom}
            holidayYearTo={holidayYearTo}
          />
        </div>
        <ScheduleOverlaidRows
          fixedAreaWidthRem={fixedAreaWidthRem}
          dayTypeRuns={dayTypeRuns}
          todayLineLeftRem={todayLineLeftRem}
        >
          {frozenItems.map((item, index) => (
            <ScheduleDataRow key={item.key} {...rowProps(item, index)} />
          ))}
        </ScheduleOverlaidRows>
      </div>

      <ScheduleOverlaidRows
        fixedAreaWidthRem={fixedAreaWidthRem}
        dayTypeRuns={dayTypeRuns}
        todayLineLeftRem={todayLineLeftRem}
      >
        {scrollableItems.map((item, index) => (
          <ScheduleDataRow key={item.key} {...rowProps(item, index + frozenRowCount)} />
        ))}
      </ScheduleOverlaidRows>
    </div>
  )
}
