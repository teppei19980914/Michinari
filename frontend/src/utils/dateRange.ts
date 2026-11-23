import { differenceInCalendarDays, parseISO } from 'date-fns'

/**
 * ISO日付文字列同士の日数差を計算する（開発Todo_スケジュール・ガントチャート_v1.1 3.4
 * 「日付の差の計算など共通にできる部分だけを切り出して共通化する」）。
 * 既存の教材ガント（`features/analytics/ganttGeometry.ts`、百分率方式）と、スケジュール
 * タブのガント（`features/schedule/scheduleGanttGeometry.ts`、rem方式）の両方から使う。
 */
export function daysBetween(fromIso: string, toIso: string): number {
  return differenceInCalendarDays(parseISO(toIso), parseISO(fromIso))
}
