import { endOfWeek, format, startOfWeek, subWeeks } from 'date-fns'

export interface RecentWeeksRange {
  dateFrom: string
  dateTo: string
}

/** 直近4週間（今週を含む）の日付範囲を返す（ダッシュボードの縮小カレンダー、S-4 4-5）。
 *
 * 週の始まりは月次カレンダー（CalendarGrid・useCalendarMonth.ts）と同じ既定（日曜始まり、
 * date-fnsの既定weekStartsOn）に揃える。週次まとめ（S-4 4-4、metrics_service.
 * resolve_last_week_range）は月曜始まりだが、あちらは業務上の「週」の定義であり、
 * こちらは月次カレンダーと同じ見た目のグリッドを作るための表示上の週区切りのため、
 * 意図的に別の基準を用いる。 */
export function resolveRecentWeeksRange(today: Date): RecentWeeksRange {
  const dateTo = endOfWeek(today)
  const dateFrom = startOfWeek(subWeeks(dateTo, 3))
  return {
    dateFrom: format(dateFrom, 'yyyy-MM-dd'),
    dateTo: format(dateTo, 'yyyy-MM-dd'),
  }
}
