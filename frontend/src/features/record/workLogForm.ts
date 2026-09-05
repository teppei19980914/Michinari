import type { WorkAssignmentRead } from '../../api/goals'
import type { WorkLogInput } from '../../api/records'
import type { components } from '../../types/api.d.ts'

type WorkLogRead = components['schemas']['WorkLogRead']

/** 業務記録入力欄の1案件分の入力状態（readingLogForm.tsのReadingLogFormValueと
 * 同じ方針。読書と異なりページ数等の付随入力は持たない、自由記述1本）。 */
export type WorkLogFormValue = {
  body: string
}

const EMPTY_VALUE: WorkLogFormValue = { body: '' }

/** 業務記録入力欄の初期値を組み立てる（readingLogForm.initReadingLogFormValuesと同じ方針）。 */
export function initWorkLogFormValues(
  workAssignments: WorkAssignmentRead[],
  existingLogs: WorkLogRead[],
): Record<number, WorkLogFormValue> {
  const existingByAssignment = new Map(existingLogs.map((log) => [log.work_assignment_id, log]))
  const result: Record<number, WorkLogFormValue> = {}

  for (const workAssignment of workAssignments) {
    const existing = existingByAssignment.get(workAssignment.id)
    result[workAssignment.id] = existing ? { body: existing.body } : { ...EMPTY_VALUE }
  }
  return result
}

/** 業務内容が1件でも入力されているか（要件定義書R-75の入力側チェック）。 */
export function hasAnyWorkLogInput(values: Record<number, WorkLogFormValue>): boolean {
  return Object.values(values).some((v) => v.body.trim() !== '')
}

/** 送信用ペイロードを組み立てる。本文が未入力の案件（今日その業務に触れていない）は
 * 送信対象から除外する（WorkLogInput.bodyは必須のため）。 */
export function buildWorkLogPayload(values: Record<number, WorkLogFormValue>): WorkLogInput[] {
  return Object.entries(values)
    .filter(([, value]) => value.body.trim() !== '')
    .map(([workAssignmentId, value]) => ({
      work_assignment_id: Number(workAssignmentId),
      body: value.body,
    }))
}
