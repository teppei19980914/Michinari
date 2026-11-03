import { t } from '../../locales/t'
import type { CharacterIconKey } from '../../constants/characterIcons'
import { resolveByGoalCategory } from '../goal/goalCategoryVariant'
import type { GoalCategory } from '../../api/goals'
import type { MilestoneAchievement } from '../../api/milestones'

/** 節目の種別に対応するキャラクターアイコン（目標種別から1つ選ぶ、既存のアイコンを再利用。
 * 開発Todo_節目のお祝い_v1.0 M7：新規イラストは追加しない）。 */
export function resolveMilestoneIcon(category: GoalCategory): CharacterIconKey {
  return resolveByGoalCategory(category, {
    EXAM: 'exam',
    READING: 'reading',
    WORK: 'work',
  })
}

/** `EXAM_MATERIAL_CYCLE_COMPLETED`の`milestone_key`（"{material_id}:{cycle_number}"）から
 * 周回番号を取り出す。 */
function parseCycleNumber(milestoneKey: string): number {
  const [, cycleNumber] = milestoneKey.split(':')
  return Number(cycleNumber)
}

/** 節目の種別・値から、お祝い文言を解決する（「続いていること」を褒める表現のみ。
 * 途切れたことを責める表現は使わない、依頼文の受け入れ基準）。 */
export function resolveMilestoneMessage(achievement: MilestoneAchievement): string {
  const count = Number(achievement.milestone_key)
  switch (achievement.milestone_type) {
    case 'CONSECUTIVE_DAYS':
      return t('milestone.message.consecutiveDays', { count })
    case 'TOTAL_RECORD_DAYS':
      return t('milestone.message.totalRecordDays', { count })
    case 'READING_TOTAL_PAGES':
      return t('milestone.message.readingTotalPages', { count })
    case 'READING_COMPLETED_BOOKS':
      return t('milestone.message.readingCompletedBooks', { count })
    case 'EXAM_MATERIAL_CYCLE_COMPLETED':
      return t('milestone.message.examMaterialCycleCompleted', {
        count: parseCycleNumber(achievement.milestone_key),
      })
    case 'EXAM_OVERALL_PROGRESS':
      return t('milestone.message.examOverallProgress', { count })
    case 'WORK_RECORD_COUNT':
      return t('milestone.message.workRecordCount', { count })
    case 'WORK_EVALUATION_PERIOD_COMPLETED':
      return t('milestone.message.workEvaluationPeriodCompleted')
  }
}
