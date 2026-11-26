import { ScheduleFixedColumnsHeader } from './ScheduleFixedColumnsHeader'
import { ScheduleGanttHeader } from './ScheduleGanttHeader'
import type { DateRangeIso } from './scheduleGanttGeometry'
import type { ScheduleDraftColumn } from './scheduleDraftTypes'

/** `ScheduleGridBody`のヘッダ行（固定列ヘッダ＋ガントヘッダ）。`ScheduleGridBody`を
 * 1関数100行以内に収めるための分離（CODING_RULES.md「保守性（複雑度）」）。 */
export function ScheduleGridHeaderRow({
  customColumns,
  readOnly,
  rowActionsLeftRem,
  columnLeftOffsetsRem,
  columnErrorsByKey,
  columnHasAnyValue,
  range,
  dayWidthRem,
  holidayIsoDates,
  holidayYearFrom,
  holidayYearTo,
  onRenameColumn,
  onMoveColumn,
  onRemoveColumn,
}: {
  customColumns: ScheduleDraftColumn[]
  readOnly: boolean
  rowActionsLeftRem: number | null
  columnLeftOffsetsRem: (number | null)[]
  columnErrorsByKey: Record<string, 'NAME_REQUIRED' | 'DUPLICATE_NAME'>
  columnHasAnyValue: (columnKey: string) => boolean
  range: DateRangeIso
  dayWidthRem: number
  holidayIsoDates: ReadonlySet<string>
  holidayYearFrom: number | null
  holidayYearTo: number | null
  onRenameColumn: (columnKey: string, name: string) => void
  onMoveColumn: (columnKey: string, offset: number) => void
  onRemoveColumn: (columnKey: string) => void
}) {
  return (
    <div className="flex">
      <ScheduleFixedColumnsHeader
        customColumns={customColumns}
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
  )
}
