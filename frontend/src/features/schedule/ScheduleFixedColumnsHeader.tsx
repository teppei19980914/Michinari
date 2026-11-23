import { t } from '../../locales/t'
import {
  DEFAULT_COLUMN_KEYS,
  DEFAULT_COLUMN_WIDTH_REM,
  CUSTOM_COLUMN_WIDTH_REM,
  ROW_ACTIONS_WIDTH_REM,
  stickyStyle,
} from './scheduleColumnLayout'
import { ScheduleCustomColumnHeaderCell } from './ScheduleCustomColumnHeaderCell'
import type { ScheduleDraftColumn } from './scheduleDraftTypes'

/**
 * 既定7列・追加列の見出し行（D-08・D-12、D-21「見出し行と一緒に固定」）。行操作列の幅は
 * 見出しが無いため空のまま幅だけ確保する。
 */
export function ScheduleFixedColumnsHeader({
  customColumns,
  readOnly,
  rowActionsLeftRem,
  columnLeftOffsetsRem,
  columnErrorsByKey,
  columnHasAnyValue,
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
  onRenameColumn: (columnKey: string, name: string) => void
  onMoveColumn: (columnKey: string, offset: number) => void
  onRemoveColumn: (columnKey: string) => void
}) {
  return (
    <div className="flex items-stretch border-b border-border-strong bg-surface-muted">
      <div
        className="shrink-0"
        style={{ width: `${ROW_ACTIONS_WIDTH_REM}rem`, ...stickyStyle(rowActionsLeftRem, 2) }}
      />
      {DEFAULT_COLUMN_KEYS.map((key, index) => (
        <div
          key={key}
          className="shrink-0 p-1 text-xs font-medium text-text-primary"
          style={{
            width: `${DEFAULT_COLUMN_WIDTH_REM[key]}rem`,
            ...stickyStyle(columnLeftOffsetsRem[index], 2),
          }}
        >
          {t(`schedule.columns.${key}`)}
        </div>
      ))}
      {customColumns.map((column, customIndex) => (
        <div
          key={column.key}
          className="shrink-0 p-1"
          style={{
            width: `${CUSTOM_COLUMN_WIDTH_REM}rem`,
            ...stickyStyle(columnLeftOffsetsRem[7 + customIndex], 2),
          }}
        >
          <ScheduleCustomColumnHeaderCell
            name={column.name}
            readOnly={readOnly}
            hasError={Boolean(columnErrorsByKey[column.key])}
            canMoveLeft={customIndex > 0}
            canMoveRight={customIndex < customColumns.length - 1}
            hasAnyValue={columnHasAnyValue(column.key)}
            onRename={(name) => onRenameColumn(column.key, name)}
            onMoveLeft={() => onMoveColumn(column.key, -1)}
            onMoveRight={() => onMoveColumn(column.key, 1)}
            onDelete={() => onRemoveColumn(column.key)}
          />
        </div>
      ))}
    </div>
  )
}
