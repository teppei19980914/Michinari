import type { components } from '../../types/api.d.ts'

type ScheduleItemStatus = components['schemas']['ScheduleItemStatus']

export type ScheduleActualDates = {
  actualStartDate: string | null
  actualEndDate: string | null
}

/**
 * 状況を変更したときの実績日の補完（開発Todo_スケジュール・ガントチャート_v1.1 6.3、
 * 12章補足1）。基準日は、スケジュール画面では本日固定とする（日次報告・SC-07は報告対象日、
 * 単位4の対象）。補完した値は利用者が修正できる（呼び出し側がこの戻り値をそのまま編集状態へ
 * 反映し、以後は通常のセル編集として扱う）。
 */
export function applyScheduleStatusAutoFill(
  newStatus: ScheduleItemStatus,
  current: ScheduleActualDates,
  today: string,
): ScheduleActualDates {
  if (newStatus === 'IN_PROGRESS') {
    return {
      actualStartDate: current.actualStartDate ?? today,
      actualEndDate: null,
    }
  }
  if (newStatus === 'DONE') {
    return {
      actualStartDate: current.actualStartDate ?? today,
      actualEndDate: current.actualEndDate ?? today,
    }
  }
  if (newStatus === 'NOT_STARTED') {
    return { actualStartDate: null, actualEndDate: null }
  }
  // CANCELLED: 変更しない。
  return current
}
