import type { AppSettingsUpdate } from '../../api/settings'

/** カンマ区切りの正の整数列（空白は許容）。バックエンドの`settings_service._parse_threshold_list`
 * が受け付ける形式と一致させる（開発Todo_節目のお祝い_v1.0 M3）。 */
const THRESHOLD_LIST_PATTERN = /^\s*\d+\s*(,\s*\d+\s*)*$/

export function isValidThresholdList(value: string): boolean {
  return THRESHOLD_LIST_PATTERN.test(value)
}

export type MilestoneThresholdFields = {
  consecutiveDaysThresholds: string
  totalRecordDaysThresholds: string
  readingTotalPagesThresholds: string
  readingCompletedBooksThresholds: string
  examOverallProgressThresholds: string
  workRecordCountThresholds: string
}

export type MilestoneThresholdGuard = {
  canSubmit: boolean
  errorKey: string | null
}

/** 6欄のいずれかが不正な形式なら保存を止める（CODING_RULES.md「フロントの分岐は.tsへ
 * 切り出す」）。 */
export function resolveMilestoneThresholdGuard(
  fields: MilestoneThresholdFields,
): MilestoneThresholdGuard {
  const allValid = Object.values(fields).every(isValidThresholdList)
  return {
    canSubmit: allValid,
    errorKey: allValid ? null : 'settings.milestoneThreshold.invalid',
  }
}

export function buildMilestoneThresholdSettingsPayload(
  fields: MilestoneThresholdFields,
): NonNullable<AppSettingsUpdate['milestone_threshold']> {
  return {
    consecutive_days_thresholds: fields.consecutiveDaysThresholds,
    total_record_days_thresholds: fields.totalRecordDaysThresholds,
    reading_total_pages_thresholds: fields.readingTotalPagesThresholds,
    reading_completed_books_thresholds: fields.readingCompletedBooksThresholds,
    exam_overall_progress_thresholds: fields.examOverallProgressThresholds,
    work_record_count_thresholds: fields.workRecordCountThresholds,
  }
}
