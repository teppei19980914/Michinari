/** カレンダー（SC-05）が表示している月と、その月グリッドが覆う日付範囲を保持するフック。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）への対応で CalendarPage から
 * 切り出したものである。取得する範囲は「月初の週の日曜」から「月末の週の土曜」までで、
 * 前後の月のはみ出し分も含む（グリッドに並ぶ日をすべて色分けするため）。 */
import { useState } from 'react'
import { addMonths, endOfMonth, endOfWeek, format, startOfMonth, startOfWeek, subMonths } from 'date-fns'

export interface CalendarMonthState {
  month: Date
  /** 月グリッドの先頭日（ISO 8601）。 */
  dateFrom: string
  /** 月グリッドの末尾日（ISO 8601）。 */
  dateTo: string
  showPreviousMonth: () => void
  showNextMonth: () => void
}

export function useCalendarMonth(): CalendarMonthState {
  const [month, setMonth] = useState(() => startOfMonth(new Date()))

  return {
    month,
    dateFrom: format(startOfWeek(startOfMonth(month)), 'yyyy-MM-dd'),
    dateTo: format(endOfWeek(endOfMonth(month)), 'yyyy-MM-dd'),
    showPreviousMonth: () => setMonth((current) => subMonths(current, 1)),
    showNextMonth: () => setMonth((current) => addMonths(current, 1)),
  }
}
