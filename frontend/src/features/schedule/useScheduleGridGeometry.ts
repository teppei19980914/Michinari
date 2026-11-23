import { useMemo } from 'react'
import {
  computeDayTypeRuns,
  computeDayWidthRem,
  computeDisplayRange,
  computeTodayLineLeftRem,
  countDaysInclusive,
  type ScheduleGanttItemInput,
} from './scheduleGanttGeometry'

/** `ScheduleGrid`が使うガントの座標一式をまとめて計算する（複雑度対策で分離）。
 * `fixedAreaWidthRem`は行操作列＋既定7列＋追加列の実際の合計幅
 * （`scheduleColumnLayout.totalFixedAreaWidthRem`）を呼び出し側が渡す。
 *
 * 行数×表示日数の計算を伴うため、`useMemo`で依存値が変わらない限り再計算しない
 * （パフォーマンスレビュー指摘。作業項目名等、座標に無関係な入力のたびに走らせない）。
 * `items`は呼び出し側（`ScheduleGrid`）が座標に関係する値だけを見て参照を安定化させている
 * 前提で、ここでは参照同一性だけを見る。 */
export function useScheduleGridGeometry(
  items: ScheduleGanttItemInput[],
  today: string,
  ganttDayWidthMinRem: number,
  ganttDayWidthMaxRem: number,
  holidayIsoDates: ReadonlySet<string>,
  viewportWidthRem: number,
  fixedAreaWidthRem: number,
) {
  return useMemo(() => {
    const range = computeDisplayRange(items, today)
    const totalDays = countDaysInclusive(range)
    const availableWidthRem = Math.max(0, viewportWidthRem - fixedAreaWidthRem)
    const dayWidthRem = computeDayWidthRem(
      totalDays,
      availableWidthRem,
      ganttDayWidthMinRem,
      ganttDayWidthMaxRem,
    )
    const ganttWidthRem = totalDays * dayWidthRem
    const dayTypeRuns = computeDayTypeRuns(
      range.startIso,
      range.endIso,
      holidayIsoDates,
      dayWidthRem,
    )
    const todayLineLeftRem = computeTodayLineLeftRem(range.startIso, today, dayWidthRem)

    return { range, dayWidthRem, ganttWidthRem, dayTypeRuns, todayLineLeftRem }
  }, [
    items,
    today,
    ganttDayWidthMinRem,
    ganttDayWidthMaxRem,
    holidayIsoDates,
    viewportWidthRem,
    fixedAreaWidthRem,
  ])
}
