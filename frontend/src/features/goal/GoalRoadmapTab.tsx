import { useQuery } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { apiErrorMessage } from '../../api/client'
import { getGoalRoadmap } from '../../api/goals'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { RoadmapDiagram } from './RoadmapDiagram'
import { RoadmapLegend } from './RoadmapLegend'
import { buildRoadmapSummaryText, resolveRoadmapStatusTextClass } from './roadmapSummaryText'

type GoalRoadmapTabProps = { goalId: number }

/** 目標詳細画面「道のり」タブ（開発Todo_道のりマップ_v1.0.md §0 U1、詳細版）。
 * GET /goals/{id}/roadmap をそのまま描画する。ReplanHistoryTabと同じ
 * useQuery＋読み込み中／エラー表示の構成に揃える（CLAUDE.md DRYの原則）。 */
export function GoalRoadmapTab({ goalId }: GoalRoadmapTabProps) {
  const roadmapQuery = useQuery({
    queryKey: QUERY_KEYS.goalRoadmap(goalId),
    queryFn: () => getGoalRoadmap(goalId),
  })

  if (roadmapQuery.isLoading) {
    return <p className="text-sm text-text-faint">{t('common.loading')}</p>
  }
  if (roadmapQuery.isError || !roadmapQuery.data) {
    return <p className="text-sm text-danger-text">{apiErrorMessage(roadmapQuery.error)}</p>
  }

  const roadmap = roadmapQuery.data
  // アクセシビリティ用のaria-labelとは別に、見える文字として現状（進捗%・遅れ/先行）を
  // 示す（aria-labelだけでは晴眼の利用者には見えず分かりづらいという利用者フィードバック、
  // 2026-11-01）。
  const summaryText = buildRoadmapSummaryText({
    category: roadmap.category,
    progressRatio: roadmap.progress_ratio,
    overrunDays: roadmap.overrun_days,
    isAchieved: roadmap.is_achieved,
  })
  const statusTextClass = resolveRoadmapStatusTextClass({
    category: roadmap.category,
    overrunDays: roadmap.overrun_days,
  })

  return (
    <Card>
      <p className={`text-sm font-medium ${statusTextClass}`}>{summaryText}</p>
      <div className="mt-2 h-64 w-full">
        <RoadmapDiagram roadmap={roadmap} interactive />
      </div>
      <RoadmapLegend category={roadmap.category} />
    </Card>
  )
}
