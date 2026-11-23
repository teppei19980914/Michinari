import { ScheduleCustomValueCells } from './ScheduleCustomValueCells'
import { ScheduleDefaultCells } from './ScheduleDefaultCells'
import { ScheduleRowActionsCell } from './ScheduleRowActionsCell'
import { ScheduleGanttRow } from './ScheduleGanttRow'
import { ROW_ACTIONS_WIDTH_REM, stickyStyle } from './scheduleColumnLayout'
import type { ScheduleDraftColumn, ScheduleDraftItem } from './scheduleDraftTypes'
import type { ScheduleItemFieldErrors } from './scheduleValidation'

/**
 * 1行分（D-02の「一体型グリッド」の1行）。既定7列は`ScheduleDefaultCells`、行操作列は
 * `ScheduleRowActionsCell`、ガントは`ScheduleGanttRow`へ分離している。固定列は`position:
 * sticky`（左位置は呼び出し側の`scheduleColumnLayout.computeStickyLeftOffsetsRem`で算出
 * 済み）、行の高さは`flex`の兄弟要素として自然に揃う（D-16、別途の高さ合わせ不要）。
 */
export function ScheduleDataRow({
  item,
  customColumns,
  readOnly,
  canMoveUp,
  canMoveDown,
  fieldErrors,
  rowActionsLeftRem,
  columnLeftOffsetsRem,
  rangeStartIso,
  dayWidthRem,
  ganttWidthRem,
  today,
  onMoveUp,
  onMoveDown,
  onInsertBelow,
  onDelete,
  onFieldChange,
  onStatusChange,
  onCellChange,
}: {
  item: ScheduleDraftItem
  customColumns: ScheduleDraftColumn[]
  readOnly: boolean
  canMoveUp: boolean
  canMoveDown: boolean
  fieldErrors: ScheduleItemFieldErrors | undefined
  rowActionsLeftRem: number | null
  columnLeftOffsetsRem: (number | null)[]
  rangeStartIso: string
  dayWidthRem: number
  ganttWidthRem: number
  today: string
  onMoveUp: () => void
  onMoveDown: () => void
  onInsertBelow: () => void
  onDelete: () => void
  onFieldChange: Parameters<typeof ScheduleDefaultCells>[0]['onFieldChange']
  onStatusChange: (status: ScheduleDraftItem['status']) => void
  onCellChange: (columnKey: string, value: string) => void
}) {
  return (
    <div
      className="flex items-stretch border-b border-border"
      data-testid="schedule-data-row"
      data-item-key={item.key}
    >
      <div
        className="flex shrink-0 items-center bg-surface p-1"
        style={{ width: `${ROW_ACTIONS_WIDTH_REM}rem`, ...stickyStyle(rowActionsLeftRem) }}
      >
        <ScheduleRowActionsCell
          readOnly={readOnly}
          canMoveUp={canMoveUp}
          canMoveDown={canMoveDown}
          onMoveUp={onMoveUp}
          onMoveDown={onMoveDown}
          onInsertBelow={onInsertBelow}
          onDelete={onDelete}
        />
      </div>

      <ScheduleDefaultCells
        item={item}
        readOnly={readOnly}
        errors={fieldErrors ?? {}}
        leftOffsetsRem={columnLeftOffsetsRem}
        onFieldChange={onFieldChange}
        onStatusChange={onStatusChange}
      />

      <ScheduleCustomValueCells
        item={item}
        customColumns={customColumns}
        readOnly={readOnly}
        columnLeftOffsetsRem={columnLeftOffsetsRem}
        onCellChange={onCellChange}
      />

      <div className="relative shrink-0 bg-surface" style={{ width: `${ganttWidthRem}rem` }}>
        <ScheduleGanttRow
          title={item.title}
          item={{
            status: item.status,
            planned_start_date: item.plannedStartDate,
            planned_end_date: item.plannedEndDate,
            actual_start_date: item.actualStartDate,
            actual_end_date: item.actualEndDate,
          }}
          rangeStartIso={rangeStartIso}
          dayWidthRem={dayWidthRem}
          today={today}
        />
      </div>
    </div>
  )
}
