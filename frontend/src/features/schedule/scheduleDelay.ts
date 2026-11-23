import type { components } from '../../types/api.d.ts'
import { daysBetween } from '../../utils/dateRange'

type ScheduleItemStatus = components['schemas']['ScheduleItemStatus']

export type ScheduleDelayInput = {
  status: ScheduleItemStatus
  planned_end_date: string
  actual_end_date: string | null
}

/**
 * ガントの遅れの印（開発Todo_スケジュール・ガントチャート_v1.1 D-18）に使う遅れ日数を
 * 算出する。未完了（未着手・進行中）で本日が予定終了日を過ぎている場合は「本日－予定終了日」、
 * 完了していて実績終了日が予定終了日を過ぎている場合は「実績終了日－予定終了日」とする（3.4）。
 * 中止の行は遅れの対象外。0以下（遅れていない）の場合はnullを返す。
 */
export function computeDelayDays(item: ScheduleDelayInput, today: string): number | null {
  if (item.status === 'CANCELLED') {
    return null
  }

  if (item.status === 'DONE') {
    if (!item.actual_end_date) {
      return null
    }
    const delay = daysBetween(item.planned_end_date, item.actual_end_date)
    return delay > 0 ? delay : null
  }

  // NOT_STARTED・IN_PROGRESS（未完了）。
  const delay = daysBetween(item.planned_end_date, today)
  return delay > 0 ? delay : null
}

export function isDelayed(item: ScheduleDelayInput, today: string): boolean {
  return computeDelayDays(item, today) !== null
}
