import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { ROUTES } from '../../constants/routes'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { updateGoal, type GoalDetailRead } from '../../api/goals'

/** リソース配分タブ（仕様書6.2「本目標への配分比率の設定」。Phase7完了条件
 * 「リソース配分超過が画面上で検知される」）。 */
export function ResourceAllocationTab({
  goal,
  readOnly,
}: {
  goal: GoalDetailRead
  readOnly: boolean
}) {
  const queryClient = useQueryClient()
  const { showToast, showApiError } = useToast()
  const [ratioPercent, setRatioPercent] = useState(String(Math.round(goal.resource_ratio * 100)))

  const mutation = useMutation({
    mutationFn: () => updateGoal(goal.id, { resource_ratio: Number(ratioPercent) / 100 }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goal', goal.id] })
      showToast(t('common.saveSucceeded'))
    },
    onError: showApiError,
  })

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium text-gray-900">{t('goals.resourceAllocation.title')}</h2>
      <Link to={ROUTES.resources} className="text-sm text-blue-600 hover:underline">
        {t('resources.title')}
      </Link>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goals.resourceAllocation.ratioLabel')}
        <Input
          type="number"
          min={0}
          max={100}
          value={ratioPercent}
          onChange={(e) => setRatioPercent(e.target.value)}
          disabled={readOnly}
        />
      </label>
      {!readOnly && (
        <div className="flex justify-end">
          <Button disabled={mutation.isPending} onClick={() => mutation.mutate()}>
            {t('common.action.save')}
          </Button>
        </div>
      )}
    </Card>
  )
}
