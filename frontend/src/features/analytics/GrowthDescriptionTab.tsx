import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { apiErrorMessage } from '../../api/client'
import {
  assignGrowthDescriptionGoal,
  getGrowthDescriptions,
  type GrowthDescriptionEntryRead,
} from '../../api/analytics'
import type { GoalRead } from '../../api/goals'
import { QUERY_KEYS } from '../../constants/queryKeys'

type GrowthDescriptionTabProps = {
  /** 選択中の目標(GoalTabBar)。この目標宛て + 同カテゴリの未割り当てレガシー分を表示する。 */
  goalId: number
  /** 未割り当てレガシー分の割り当て先候補を絞り込むため、全目標を受け取る。 */
  goals: GoalRead[]
}

function UnassignedEntryAssignForm({
  entry,
  candidateGoals,
  onAssigned,
}: {
  entry: GrowthDescriptionEntryRead
  candidateGoals: GoalRead[]
  onAssigned: () => void
}) {
  const { showApiError } = useToast()
  const [targetGoalId, setTargetGoalId] = useState('')

  const mutation = useMutation({
    mutationFn: (goalId: number) =>
      assignGrowthDescriptionGoal(entry.message_id, { goal_id: goalId }),
    onSuccess: onAssigned,
    onError: showApiError,
  })

  return (
    <div className="mt-2 flex items-center gap-2 border-t border-gray-100 pt-2">
      <span className="text-xs text-amber-700">{t('analytics.growthDescription.unassignedLabel')}</span>
      <select
        className="rounded border border-gray-300 px-2 py-1 text-sm"
        value={targetGoalId}
        onChange={(event) => setTargetGoalId(event.target.value)}
      >
        <option value="">{t('analytics.growthDescription.assignPlaceholder')}</option>
        {candidateGoals.map((goal) => (
          <option key={goal.id} value={goal.id}>
            {goal.name}
          </option>
        ))}
      </select>
      <Button
        variant="secondary"
        disabled={!targetGoalId || mutation.isPending}
        onClick={() => mutation.mutate(Number(targetGoalId))}
      >
        {t('analytics.growthDescription.assignButton')}
      </Button>
    </div>
  )
}

/** 分析画面「成長記述」タブ(仕様書6.8、ANL-07)。選択中の目標宛てのAI日次報告フィードバック
 * 応答履歴を新しい日付順に表示する(Phase26で目標単位に分離、それ以前はgoal_id=NULLで
 * 目標横断していた)。目標単位分離より前のレガシーメッセージ(goal_id=NULL)は「未割り当て」
 * として表示し、利用者が記憶を頼りにプルダウンから目標を手動で割り当てられる
 * (analytics_service.assign_growth_description_goalのdocstring参照、同一カテゴリの
 * 目標にのみ割り当て可能)。 */
export function GrowthDescriptionTab({ goalId, goals }: GrowthDescriptionTabProps) {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: QUERY_KEYS.analyticsGrowthDescriptions(goalId),
    queryFn: () => getGrowthDescriptions(goalId),
  })

  if (query.isLoading) {
    return <p className="text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (query.isError || !query.data) {
    return <p className="text-sm text-red-600">{apiErrorMessage(query.error)}</p>
  }
  if (query.data.length === 0) {
    return <p className="text-sm text-gray-500">{t('analytics.growthDescription.empty')}</p>
  }

  const category = goals.find((goal) => goal.id === goalId)?.category
  const candidateGoals = goals.filter((goal) => goal.category === category)
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.analyticsGrowthDescriptions(goalId) })

  return (
    <div className="flex flex-col gap-3">
      {query.data.map((entry) => (
        <Card key={entry.message_id}>
          <p className="mb-1 text-xs text-gray-400">{entry.record_date}</p>
          <p className="whitespace-pre-wrap text-sm text-gray-900">{entry.content}</p>
          {entry.goal_id === null && (
            <UnassignedEntryAssignForm
              entry={entry}
              candidateGoals={candidateGoals}
              onAssigned={invalidate}
            />
          )}
        </Card>
      ))}
    </div>
  )
}
