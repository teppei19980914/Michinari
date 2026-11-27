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

/** 確定済みの種別（`readOnly`）向け（軽微な修正3、開発Todo_スケジュール・ガントチャート_
 * 検証修正_v1.0.md）。その日に更新した行（完了・中止を含む）のみを返す。 */
const SELECT_HISTORY_GOALS_BY_CATEGORY: Record<
  GoalCategory,
  (targets: VisibleReportTargets) => GoalScheduleItemsForReportRead[]
> = {
  EXAM: (targets) => targets.examScheduleItemHistoryGoals,
  READING: (targets) => targets.readingScheduleItemHistoryGoals,
  WORK: (targets) => targets.workScheduleItemHistoryGoals,
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
  // 確定済み（readOnly）では、その日に更新した内容（schedule_item_history基準、完了・
  // 中止を含む）を表示する。入力中はライブの現在値（D-33の絞り込み）を表示する
  // （軽微な修正3、開発Todo_スケジュール・ガントチャート_検証修正_v1.0.md）。
  const goals = readOnly
    ? SELECT_HISTORY_GOALS_BY_CATEGORY[category](targets)
    : SELECT_GOALS_BY_CATEGORY[category](targets)
  return (
    <ScheduleItemsField
      goals={goals}
      targetDate={targetDate}
      readOnly={readOnly}
      values={draft.scheduleItemValues}
      onChange={draft.setScheduleItemValues}
    />
  )
}
