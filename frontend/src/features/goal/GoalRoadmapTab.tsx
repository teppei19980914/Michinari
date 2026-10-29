import { useQuery } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { apiErrorMessage } from '../../api/client'
import { getGoalRoadmap } from '../../api/goals'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { RoadmapDiagram } from './RoadmapDiagram'

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

  return (
    <Card>
      <div className="h-64 w-full">
        <RoadmapDiagram roadmap={roadmapQuery.data} interactive />
      </div>
    </Card>
  )
}
