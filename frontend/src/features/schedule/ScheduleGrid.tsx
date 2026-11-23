import { useMemo, useRef } from 'react'
import { ScheduleGridBody } from './ScheduleGridBody'
import { computeStickyLeftOffsetsRem, totalFixedAreaWidthRem } from './scheduleColumnLayout'
import { useScheduleGridGeometry } from './useScheduleGridGeometry'
import { useScrollToToday } from './useScrollToToday'
import { useViewportWidthRem } from './useViewportWidthRem'
import type { ScheduleDraft, ScheduleDraftFieldKey, ScheduleDraftItem } from './scheduleDraftTypes'
import type { ScheduleItemFieldErrors } from './scheduleValidation'

function toGanttItems(items: ScheduleDraftItem[]) {
  return items.map((item) => ({
    status: item.status,
    planned_start_date: item.plannedStartDate,
    planned_end_date: item.plannedEndDate,
    actual_start_date: item.actualStartDate,
    actual_end_date: item.actualEndDate,
  }))
}

/** ガントの座標に影響する値（予定・実績日・状況）だけを連結した文字列。作業項目名・
 * 作業内容・追加列の値のような無関係な入力のたびに座標を再計算しないための
 * `useMemo`の依存値（パフォーマンスレビュー指摘、`draft.items`は毎回新しい配列になるため
 * 参照比較ではメモ化できない）。 */
function ganttRelevantSignature(items: ScheduleDraftItem[]): string {
  return items
    .map((item) =>
      [item.key, item.status, item.plannedStartDate, item.plannedEndDate, item.actualStartDate, item.actualEndDate].join(
        '|',
      ),
    )
    .join(';')
}

export type ScheduleGridProps = {
  draft: ScheduleDraft
  readOnly: boolean
  frozenRowCount: number
  frozenColumnCount: number
  today: string
  ganttDayWidthMinRem: number
  ganttDayWidthMaxRem: number
  holidayIsoDates: ReadonlySet<string>
  holidayYearFrom: number | null
  holidayYearTo: number | null
  fieldErrorsByItemKey: Record<string, ScheduleItemFieldErrors>
  columnErrorsByKey: Record<string, 'NAME_REQUIRED' | 'DUPLICATE_NAME'>
  columnHasAnyValue: (columnKey: string) => boolean
  goToTodaySignal: number
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

/**
 * 一体型グリッド本体（D-02）。見出し2段＋固定行は`position: sticky; top: 0`の1つの
 * ブロックにまとめて重ねる（高さの実測なしに複数行の固定を正しく積み上げるため）。
 * 固定列は各セル（`ScheduleDataRow`等）側で`position: sticky; left: Xrem`を適用する
 * （列と行のsticky位置は独立に効くため、角のセルは両方が重なって正しく固定される）。
 * 座標の算出は`useScheduleGridGeometry`、描画は`ScheduleGridBody`へ分離している
 * （複雑度対策）。
 */
export function ScheduleGrid({
  draft,
  readOnly,
  frozenRowCount,
  frozenColumnCount,
  today,
  ganttDayWidthMinRem,
  ganttDayWidthMaxRem,
  holidayIsoDates,
  holidayYearFrom,
  holidayYearTo,
  fieldErrorsByItemKey,
  columnErrorsByKey,
  columnHasAnyValue,
  goToTodaySignal,
  onMoveRow,
  onInsertRowBelow,
  onRemoveRow,
  onFieldChange,
  onStatusChange,
  onCellChange,
  onRenameColumn,
  onMoveColumn,
  onRemoveColumn,
}: ScheduleGridProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const viewportWidthRem = useViewportWidthRem()
  const showRowActions = !readOnly
  const fixedAreaWidthRem = totalFixedAreaWidthRem(draft.columns.length, showRowActions)

  const ganttRelevantKey = ganttRelevantSignature(draft.items)
  // eslint-disable-next-line react-hooks/exhaustive-deps -- ganttRelevantKeyが実質的な依存値
  const ganttItems = useMemo(() => toGanttItems(draft.items), [ganttRelevantKey])
  const { range, dayWidthRem, ganttWidthRem, dayTypeRuns, todayLineLeftRem } =
    useScheduleGridGeometry(
      ganttItems,
      today,
      ganttDayWidthMinRem,
      ganttDayWidthMaxRem,
      holidayIsoDates,
      viewportWidthRem,
      fixedAreaWidthRem,
    )
  useScrollToToday(
    scrollRef,
    goToTodaySignal,
    viewportWidthRem,
    fixedAreaWidthRem,
    ganttWidthRem,
    todayLineLeftRem,
  )

  const { rowActionsLeftRem, columnLeftOffsetsRem } = computeStickyLeftOffsetsRem(
    draft.columns.length,
    frozenColumnCount,
    showRowActions,
  )

  return (
    <ScheduleGridBody
      scrollRef={scrollRef}
      draft={draft}
      readOnly={readOnly}
      frozenRowCount={frozenRowCount}
      range={range}
      dayWidthRem={dayWidthRem}
      ganttWidthRem={ganttWidthRem}
      fixedAreaWidthRem={fixedAreaWidthRem}
      dayTypeRuns={dayTypeRuns}
      todayLineLeftRem={todayLineLeftRem}
      holidayIsoDates={holidayIsoDates}
      holidayYearFrom={holidayYearFrom}
      holidayYearTo={holidayYearTo}
      rowActionsLeftRem={rowActionsLeftRem}
      columnLeftOffsetsRem={columnLeftOffsetsRem}
      fieldErrorsByItemKey={fieldErrorsByItemKey}
      columnErrorsByKey={columnErrorsByKey}
      columnHasAnyValue={columnHasAnyValue}
      today={today}
      onMoveRow={onMoveRow}
      onInsertRowBelow={onInsertRowBelow}
      onRemoveRow={onRemoveRow}
      onFieldChange={onFieldChange}
      onStatusChange={onStatusChange}
      onCellChange={onCellChange}
      onRenameColumn={onRenameColumn}
      onMoveColumn={onMoveColumn}
      onRemoveColumn={onRemoveColumn}
    />
  )
}
