import { Input } from '../../components/Input'
import { CUSTOM_COLUMN_WIDTH_REM, stickyStyle } from './scheduleColumnLayout'
import type { ScheduleDraftColumn, ScheduleDraftItem } from './scheduleDraftTypes'

/** 追加列の値セル（D-12）。`ScheduleDataRow`から分離（1関数100行の上限）。 */
export function ScheduleCustomValueCells({
  item,
  customColumns,
  readOnly,
  columnLeftOffsetsRem,
  onCellChange,
}: {
  item: ScheduleDraftItem
  customColumns: ScheduleDraftColumn[]
  readOnly: boolean
  columnLeftOffsetsRem: (number | null)[]
  onCellChange: (columnKey: string, value: string) => void
}) {
  return (
    <>
      {customColumns.map((column, customIndex) => (
        <div
          key={column.key}
          className="shrink-0 bg-surface p-1"
          style={{
            width: `${CUSTOM_COLUMN_WIDTH_REM}rem`,
            ...stickyStyle(columnLeftOffsetsRem[7 + customIndex]),
          }}
        >
          <Input
            value={item.cells[column.key] ?? ''}
            disabled={readOnly}
            aria-label={column.name}
            onChange={(event) => onCellChange(column.key, event.target.value)}
            className="text-xs"
          />
        </div>
      ))}
    </>
  )
}
