import type { DailyRecordRead } from '../../api/records'
import type { CategoryPresence } from './categoryCompletion'

export type ZeroRecordCategory = 'EXAM' | 'READING' | 'WORK'

/**
 * 「今日は何もしていない」ボタンの対象カテゴリを決める（記録画面改善タスク2026-09-17）。
 *
 * 対象は、その日ACTIVEな目標があり(presence)、かつ一度も操作していない（未入力、NULL）
 * カテゴリのみ。既に進捗のみ登録済み（PROGRESS_ONLY）のカテゴリは対象から除外する
 * （実データが入っているのにゼロ記録で上書きしないため）。報告済み（REPORTED）のカテゴリも
 * 当然対象外（変更不可、仕様書7.2）。
 *
 * 対象外のカテゴリ（PROGRESS_ONLY等）が残る場合、ボタンはその他のカテゴリだけをゼロ確定
 * する（1クリックで「今日触れていない分」だけを片付け、既に入力済みの分はそのまま残す）。
 */
export function resolveZeroRecordCategories(
  presence: CategoryPresence,
  record: Pick<DailyRecordRead, 'exam_record_state' | 'reading_record_state' | 'work_record_state'>,
): ZeroRecordCategory[] {
  const categories: ZeroRecordCategory[] = []
  if (presence.hasExamCategory && record.exam_record_state === null) {
    categories.push('EXAM')
  }
  if (presence.hasReadingCategory && record.reading_record_state === null) {
    categories.push('READING')
  }
  if (presence.hasWorkCategory && record.work_record_state === null) {
    categories.push('WORK')
  }
  return categories
}
