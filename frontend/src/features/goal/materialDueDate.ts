import type { SubjectRead } from '../../api/goals'

type DueDateSubject = Pick<SubjectRead, 'id' | 'exam_date_type' | 'exam_date_from' | 'exam_date_fixed'>

function effectiveExamDate(subject: DueDateSubject): string | null {
  return subject.exam_date_type === 'FIXED' ? subject.exam_date_fixed : subject.exam_date_from
}

function isoDateMinusOneDay(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  date.setUTCDate(date.getUTCDate() - 1)
  return date.toISOString().slice(0, 10)
}

/**
 * 教材の締切自動導出のプレビュー用（backend/app/services/material_service.py の
 * effective_exam_date/compute_due_dateと同じ規則）。保存前にUIで開始日との矛盾を
 * その場で提示するための計算であり、"今日"を判断するものではないため
 * CLAUDE.md「クライアント側での論理日の判断」禁止には抵触しない。締切の正式な決定は
 * サーバ側（material_service.py）が引き続き唯一の実装箇所とする。
 *
 * @param subjects 目標配下の全試験科目（GoalDetailRead.exam_subjects）
 * @param subjectIds 教材フォームで選択中の科目ID
 * @returns 選択科目の最も早い受験日の前日（ISO 8601）。算出不能な場合はnull
 */
export function computeAutoDueDate(
  subjects: DueDateSubject[],
  subjectIds: number[],
): string | null {
  const examDates = subjects
    .filter((subject) => subjectIds.includes(subject.id))
    .map(effectiveExamDate)
    .filter((date): date is string => date !== null)
  if (examDates.length === 0) {
    return null
  }
  const earliest = examDates.reduce((min, current) => (current < min ? current : min))
  return isoDateMinusOneDay(earliest)
}
