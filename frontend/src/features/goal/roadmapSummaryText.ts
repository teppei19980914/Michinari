import { t } from '../../locales/t'
import { resolveScheduleStatus } from './scheduleStatus'
import type { GoalCategory } from '../../api/goals'

/**
 * 道のりマップの要約文言（アクセシビリティ用の`aria-label`、開発Todo_道のりマップ_v1.0.md
 * §0 要件5「図に文章の要約を付ける（例：『全体の62%、予定より3日遅れ』）」）。
 *
 * 遅れ/予定どおり/先行の判定は資格試験目標にのみ行う（§0 U7、`resolveScheduleStatus`と
 * 同じ判定ロジックを再利用し、ここで複製しない）。
 */
export function buildRoadmapSummaryText(params: {
  category: GoalCategory
  progressRatio: number
  overrunDays: number | null
  isAchieved: boolean
}): string {
  const percent = Math.round(Math.min(1, Math.max(0, params.progressRatio)) * 100)

  if (params.isAchieved) {
    return t('goals.roadmap.summary.achieved', { percent })
  }
  if (params.category === 'READING') {
    return t('goals.roadmap.summary.reading.inProgress', { percent })
  }
  if (params.category === 'WORK') {
    return t('goals.roadmap.summary.work.inProgress', { percent })
  }

  const status = resolveScheduleStatus(params.overrunDays)
  const days = Math.round(Math.abs(params.overrunDays ?? 0))
  if (status === 'delayed') {
    return t('goals.roadmap.summary.exam.delayed', { percent, days })
  }
  if (status === 'ahead') {
    return t('goals.roadmap.summary.exam.ahead', { percent, days })
  }
  if (status === 'onTrack') {
    return t('goals.roadmap.summary.exam.onTrack', { percent })
  }
  return t('goals.roadmap.summary.exam.noForecast', { percent })
}
