import { t } from '../../locales/t'
import { combineQaAnswers, hasAnyQaInput } from './qaCombine'
import type { WorkAssignmentRead } from '../../api/goals'
import type { WorkLogInput } from '../../api/records'
import type { components } from '../../types/api.d.ts'

type WorkLogRead = components['schemas']['WorkLogRead']

/**
 * 業務記録入力欄の1案件分の入力状態（readingLogForm.tsのReadingLogFormValueと
 * 同じ方針。読書と異なりページ数等の付随入力は持たない）。
 *
 * 業務内容は質問への回答形式へ再構成した（仕様書6.5改、記録画面改善タスク2026-09-17）。
 * questionAnswersが質問ごとの回答、freeTextが「自由に書く」欄（旧・業務内容欄）に対応する。
 * 送信する業務内容（body）はこの2つをcombineWorkBodyで都度結合して求め、保存形式・APIは
 * 変更しない。
 */
export type WorkLogFormValue = {
  questionAnswers: string[]
  freeText: string
}

/** 仕事の業務記録質問（仕様書6.5改）。固定2問。 */
export function getWorkLogQuestions(): string[] {
  return [t('dailyReport.workLog.question1'), t('dailyReport.workLog.question2')]
}

const EMPTY_VALUE: WorkLogFormValue = { questionAnswers: ['', ''], freeText: '' }

/** 質問への回答と「自由に書く」欄を結合し、送信する業務内容（body）を求める。 */
export function combineWorkBody(value: WorkLogFormValue): string {
  return combineQaAnswers(getWorkLogQuestions(), value.questionAnswers, value.freeText)
}

/**
 * 業務記録入力欄の初期値を組み立てる（readingLogForm.initReadingLogFormValuesと同じ方針）。
 * 既存の業務内容は「自由に書く」欄（freeText）へそのまま引き継ぐ（質問への回答への
 * 逆変換はしない）。
 */
export function initWorkLogFormValues(
  workAssignments: WorkAssignmentRead[],
  existingLogs: WorkLogRead[],
): Record<number, WorkLogFormValue> {
  const existingByAssignment = new Map(existingLogs.map((log) => [log.work_assignment_id, log]))
  const result: Record<number, WorkLogFormValue> = {}

  for (const workAssignment of workAssignments) {
    const existing = existingByAssignment.get(workAssignment.id)
    result[workAssignment.id] = existing
      ? { questionAnswers: ['', ''], freeText: existing.body }
      : { ...EMPTY_VALUE, questionAnswers: [...EMPTY_VALUE.questionAnswers] }
  }
  return result
}

/** 業務記録欄（質問への回答・自由記述）に1件でも入力されているか（要件定義書R-75）。
 * R-75の「業務内容は必須」は、いずれかの回答欄に1件以上の入力があることを指す
 * （仕様変更2026-09-17。全ての回答欄は任意とし、1つだけ書いても確定できる）。 */
export function hasAnyWorkLogInput(values: Record<number, WorkLogFormValue>): boolean {
  return Object.values(values).some((v) => hasAnyQaInput(v.questionAnswers, v.freeText))
}

/** 送信用ペイロードを組み立てる。業務内容が未入力の案件（今日その業務に触れていない）は
 * 送信対象から除外する（WorkLogInput.bodyは必須のため）。 */
export function buildWorkLogPayload(values: Record<number, WorkLogFormValue>): WorkLogInput[] {
  return Object.entries(values)
    .map(([workAssignmentId, value]) => ({
      work_assignment_id: Number(workAssignmentId),
      body: combineWorkBody(value),
    }))
    .filter((entry) => entry.body !== '')
}
