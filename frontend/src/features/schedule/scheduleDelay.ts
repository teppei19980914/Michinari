import type { components } from '../../types/api.d.ts'
import { daysBetween } from '../../utils/dateRange'

type ScheduleItemStatus = components['schemas']['ScheduleItemStatus']

export type ScheduleDelayInput = {
  status: ScheduleItemStatus
  planned_end_date: string
  actual_end_date: string | null
  //: 開始の遅れ（単位5・13.2・14章補足4）の判定に使う。既存の呼び出し元（終了の遅れのみを
  //: 扱っていた単位3時点のテスト）との後方互換のため任意とし、省略時は開始の遅れを判定しない
  //: （既存の挙動を変えない）。
  planned_start_date?: string
}

export type ScheduleDelayKind = 'END_DELAY' | 'START_DELAY'

export type ScheduleDelayInfo = {
  kind: ScheduleDelayKind
  days: number
}

/**
 * ガントの遅れの印（開発Todo_スケジュール・ガントチャート_v1.1 D-18・13.2）に使う遅れの
 * 種類と日数を算出する。バックエンドの`schedule_service.compute_delay_kind`と同じ判定順序
 * （終了の遅れを先に判定、未着手かつ終了の遅れが無い場合のみ開始の遅れを判定、単位3引き継ぎ
 * 事項・単位5開発Todo2章補足9）。完了していて実績終了日が予定終了日を過ぎている場合は
 * 終了の遅れとして「実績終了日－予定終了日」を返す（3.4）。中止の行は遅れの対象外。
 * 該当なしの場合はnullを返す。
 */
export function computeDelayInfo(
  item: ScheduleDelayInput,
  today: string,
): ScheduleDelayInfo | null {
  if (item.status === 'CANCELLED') {
    return null
  }

  if (item.status === 'DONE') {
    if (!item.actual_end_date) {
      return null
    }
    const delay = daysBetween(item.planned_end_date, item.actual_end_date)
    return delay > 0 ? { kind: 'END_DELAY', days: delay } : null
  }

  // NOT_STARTED・IN_PROGRESS（未完了）。
  const endDelay = daysBetween(item.planned_end_date, today)
  if (endDelay > 0) {
    return { kind: 'END_DELAY', days: endDelay }
  }
  if (item.status === 'NOT_STARTED' && item.planned_start_date != null) {
    const startDelay = daysBetween(item.planned_start_date, today)
    if (startDelay > 0) {
      return { kind: 'START_DELAY', days: startDelay }
    }
  }
  return null
}

/** `computeDelayInfo`の日数部分のみを返す薄いラッパー（既存の呼び出し元向け、0以下＝
 * 遅れていない場合はnullを返す、という既存の戻り値の意味を保つ）。 */
export function computeDelayDays(item: ScheduleDelayInput, today: string): number | null {
  return computeDelayInfo(item, today)?.days ?? null
}

export function isDelayed(item: ScheduleDelayInput, today: string): boolean {
  return computeDelayDays(item, today) !== null
}
