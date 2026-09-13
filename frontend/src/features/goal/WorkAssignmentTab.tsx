import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Textarea } from '../../components/Textarea'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import {
  createWorkAssignment,
  updateWorkAssignment,
  type GoalDetailRead,
  type WorkAssignmentRead,
} from '../../api/goals'
import { QUERY_KEYS } from '../../constants/queryKeys'

function WorkAssignmentForm({
  goalId,
  workAssignment,
  onDone,
}: {
  goalId: number
  workAssignment?: WorkAssignmentRead
  onDone: () => void
}) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [clientName, setClientName] = useState(workAssignment?.client_name ?? '')
  const [expectedContent, setExpectedContent] = useState(workAssignment?.expected_content ?? '')
  const [startDate, setStartDate] = useState(workAssignment?.start_date ?? '')

  const payload = {
    client_name: clientName === '' ? null : clientName,
    expected_content: expectedContent,
    start_date: startDate,
  }

  const mutation = useMutation({
    mutationFn: () =>
      workAssignment
        ? updateWorkAssignment(goalId, payload)
        : createWorkAssignment(goalId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.goal(goalId) })
      onDone()
    },
    onError: showApiError,
  })

  return (
    <Card>
      <form
        className="flex flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          mutation.mutate()
        }}
      >
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('goals.workAssignment.clientNameLabel')}
          <Input value={clientName} onChange={(e) => setClientName(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('goals.workAssignment.expectedContentLabel')}
          <Textarea
            value={expectedContent}
            onChange={(e) => setExpectedContent(e.target.value)}
            rows={4}
            required
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('goals.workAssignment.startDateLabel')}
          <Input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            required
          />
        </label>
        <div className="flex justify-end gap-2">
          {workAssignment && (
            <Button type="button" variant="secondary" onClick={onDone}>
              {t('common.action.cancel')}
            </Button>
          )}
          <Button type="submit" disabled={mutation.isPending}>
            {t('common.action.save')}
          </Button>
        </div>
      </form>
    </Card>
  )
}

function WorkAssignmentProgress({ workAssignment }: { workAssignment: WorkAssignmentRead }) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-gray-600">
      <dt className="text-gray-400">{t('goals.workAssignment.elapsedDaysLabel')}</dt>
      <dd>{t('goals.workAssignment.elapsedDaysValue', { days: workAssignment.elapsed_days })}</dd>
      <dt className="text-gray-400">{t('goals.workAssignment.lastWorkDateLabel')}</dt>
      <dd>{workAssignment.last_work_date ?? t('goals.workAssignment.lastWorkDateUnavailable')}</dd>
      <dt className="text-gray-400">{t('goals.workAssignment.currentStreakLabel')}</dt>
      <dd>
        {t('goals.workAssignment.currentStreakValue', { days: workAssignment.current_streak })}
      </dd>
      <dt className="text-gray-400">{t('goals.workAssignment.hasRecentMonthlyReportLabel')}</dt>
      <dd>
        {workAssignment.has_recent_monthly_report
          ? t('common.yes')
          : t('goals.workAssignment.hasRecentMonthlyReportNone')}
      </dd>
    </dl>
  )
}

/** 案件情報タブ（仕事目標。仕様書6.2「仕事目標（category=WORKの場合）」）。
 * 資格試験の試験科目・教材タブ、読書の書籍タブに相当する仕事版で、1目標1案件のため
 * 単一のカードで登録・編集・進捗表示を行う。読了操作に相当する専用の完了ボタンは持たず、
 * 案件の終了は基本情報タブと共通のクローズ操作（結果あり／結果なしの選択）で行う。 */
export function WorkAssignmentTab({
  goal,
  readOnly,
}: {
  goal: GoalDetailRead
  readOnly: boolean
}) {
  const [editing, setEditing] = useState(false)

  if (!goal.work_assignment) {
    if (readOnly) {
      return <p className="text-sm text-gray-500">{t('goals.workAssignment.empty')}</p>
    }
    return <WorkAssignmentForm goalId={goal.id} onDone={() => undefined} />
  }

  const workAssignment = goal.work_assignment

  if (editing) {
    return (
      <WorkAssignmentForm
        goalId={goal.id}
        workAssignment={workAssignment}
        onDone={() => setEditing(false)}
      />
    )
  }

  return (
    <Card className="flex flex-col gap-3">
      <div>
        {workAssignment.client_name && (
          <p className="text-sm text-gray-500">{workAssignment.client_name}</p>
        )}
        <p className="whitespace-pre-wrap text-sm text-gray-900">
          {workAssignment.expected_content}
        </p>
      </div>
      <WorkAssignmentProgress workAssignment={workAssignment} />
      {!readOnly && (
        <div className="flex justify-end">
          <Button variant="secondary" onClick={() => setEditing(true)}>
            {t('common.action.edit')}
          </Button>
        </div>
      )}
    </Card>
  )
}
