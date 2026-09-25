import type { DailyRecordRead } from '../../api/records'
import type { CategoryPresence } from './categoryCompletion'

export type ZeroRecordCategory = 'EXAM' | 'READING' | 'WORK'

/** カテゴリ別セクションが現在の目標タブ選択状態で画面に表示されているか
 * （resolveVisibleReportTargetsのshowExamSection等と同じ形。構造的に一致していれば
 * 個別にimportしなくても渡せる）。 */
export type VisibleCategorySections = {
  showExamSection: boolean
  showReadingSection: boolean
  showWorkSection: boolean
}

/**
 * 「今日は何もしていない」ボタンの対象カテゴリを決める（記録画面改善タスク2026-09-17、
 * 目標タブ絞り込みバグ修正2026-09-26）。
 *
 * 対象は、その日ACTIVEな目標があり(presence)、かつ一度も操作していない（未入力、NULL）
 * カテゴリのみ。既に進捗のみ登録済み（PROGRESS_ONLY）のカテゴリは対象から除外する
 * （実データが入っているのにゼロ記録で上書きしないため）。報告済み（REPORTED）のカテゴリも
 * 当然対象外（変更不可、仕様書7.2）。
 *
 * さらに、現在画面に表示中のカテゴリセクション（visibleSections）に限定する。presenceは
 * 選択中タブに関わらずその日ACTIVEな全カテゴリを表すため（categoryCompletion.ts
 * isAllCategoriesReported参照）、これだけで絞り込むと目標タブで選択していないカテゴリまで
 * ゼロ確定してしまう（例: 読書タブ表示中に資格試験・仕事も確定済みになる不具合、2026-09-26
 * 報告）。表示中かどうかはisSectionVisibleと同じ規則のshow*Sectionで判定する。
 *
 * 対象外のカテゴリ（PROGRESS_ONLY・非表示タブ等）が残る場合、ボタンはその他のカテゴリだけを
 * ゼロ確定する（1クリックで「今表示していて、今日触れていない分」だけを片付け、既に入力済み
 * または他タブの分はそのまま残す）。
 */
export function resolveZeroRecordCategories(
  presence: CategoryPresence,
  record: Pick<DailyRecordRead, 'exam_record_state' | 'reading_record_state' | 'work_record_state'>,
  visibleSections: VisibleCategorySections,
): ZeroRecordCategory[] {
  const categories: ZeroRecordCategory[] = []
  if (presence.hasExamCategory && record.exam_record_state === null && visibleSections.showExamSection) {
    categories.push('EXAM')
  }
  if (
    presence.hasReadingCategory &&
    record.reading_record_state === null &&
    visibleSections.showReadingSection
  ) {
    categories.push('READING')
  }
  if (presence.hasWorkCategory && record.work_record_state === null && visibleSections.showWorkSection) {
    categories.push('WORK')
  }
  return categories
}
