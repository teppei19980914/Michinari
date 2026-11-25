import { ScheduleItemsField } from './ScheduleItemsField'
import type { GoalCategory } from '../../api/goals'
import type { GoalScheduleItemsForReportRead } from '../../api/records'
import type { DailyReportDraft } from './useDailyReportDraft'
import type { VisibleReportTargets } from './resolveVisibleReportTargets'

const SELECT_GOALS_BY_CATEGORY: Record<
  GoalCategory,
  (targets: VisibleReportTargets) => GoalScheduleItemsForReportRead[]
> = {
  EXAM: (targets) => targets.examScheduleItemGoals,
  READING: (targets) => targets.readingScheduleItemGoals,
  WORK: (targets) => targets.workScheduleItemGoals,
}

/**
 * カテゴリ別ReportSection（ExamReportSection・ReadingReportSection・WorkReportSection）の
 * summary/editorから呼ぶ「今日の作業項目」欄の束ね（開発Todo_スケジュール・ガントチャート
 * _v1.1 第4章・D-38、単位4）。
 *
 * `<ScheduleItemsField>`の呼び出し（`targetDate`・`values`・`onChange`は常に同じ、差分は
 * `goals`〈カテゴリ別フィールド〉と`readOnly`だけ）が3ファイル×summary/editorの計6箇所で
 * 複製されていたため、ここへ集約した（CODING_RULES.md「①DRYの原則」。`CategoryReportSection
 * .tsx`が同種の3重複を共通化した前例に倣う）。
 */
export function CategoryScheduleItemsField({
  category,
  targets,
  targetDate,
  readOnly,
  draft,
}: {
  category: GoalCategory
  targets: VisibleReportTargets
  targetDate: string
  readOnly: boolean
  draft: DailyReportDraft
}) {
  return (
    <ScheduleItemsField
      goals={SELECT_GOALS_BY_CATEGORY[category](targets)}
      targetDate={targetDate}
      readOnly={readOnly}
      values={draft.scheduleItemValues}
      onChange={draft.setScheduleItemValues}
    />
  )
}
