import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { updateGoal, type GoalDetailRead } from '../../api/goals'
import { resolveByGoalCategory } from './goalCategoryVariant'

/** 基本情報タブ（仕様書6.2「試験名、開始日、状態、備考」）。 */
export function BasicInfoTab({ goal, readOnly }: { goal: GoalDetailRead; readOnly: boolean }) {
  const queryClient = useQueryClient()
  const { showToast, showApiError } = useToast()
  const [name, setName] = useState(goal.name)
  const [startDate, setStartDate] = useState(goal.start_date)
  const [memo, setMemo] = useState(goal.memo ?? '')

  const mutation = useMutation({
    mutationFn: () => updateGoal(goal.id, { name, start_date: startDate, memo }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goal', goal.id] })
      showToast(t('common.saveSucceeded'))
    },
    onError: showApiError,
  })

  const nameLabel = t(
    resolveByGoalCategory(goal.category, {
      EXAM: 'goals.basicInfo.nameLabel',
      READING: 'goals.basicInfo.nameLabelReading',
      WORK: 'goals.basicInfo.nameLabelWork',
    }),
  )

  return (
    <Card className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {nameLabel}
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={readOnly}
          required
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goals.basicInfo.startDateLabel')}
        <Input
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          disabled={readOnly}
          required
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goals.basicInfo.memoLabel')}
        <textarea
          className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          value={memo}
          onChange={(e) => setMemo(e.target.value)}
          disabled={readOnly}
          rows={3}
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
