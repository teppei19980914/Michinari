import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../locales/t'
import { ROUTES } from '../constants/routes'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { Input } from '../components/Input'
import { Modal } from '../components/Modal'
import { useToast } from '../components/Toast'
import { ApiError } from '../api/client'
import { createGoal, listGoals } from '../api/goals'
import { isClosedGoalStatus, resolveGoalListTarget } from '../features/goal/goalStatus'

function NewGoalModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [name, setName] = useState('')
  const [startDate, setStartDate] = useState('')

  const mutation = useMutation({
    mutationFn: () => createGoal({ name, start_date: startDate }),
    onSuccess: (goal) => {
      queryClient.invalidateQueries({ queryKey: ['goals'] })
      onClose()
      navigate(ROUTES.goalDetail(goal.id))
    },
    onError: (error) => {
      showToast(error instanceof ApiError ? error.localizedMessage : t('errors.default'), 'error')
    },
  })

  return (
    <Modal open={open} onClose={onClose} title={t('goals.new.title')}>
      <form
        className="flex flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          mutation.mutate()
        }}
      >
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('goals.new.nameLabel')}
          <Input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('goals.new.startDateLabel')}
          <Input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            required
          />
        </label>
        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('common.action.cancel')}
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {t('common.action.save')}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

/** SC-02 目標一覧（仕様書4章・5.2「新規作成/目標選択/クローズ済目標選択」）。 */
export function GoalsListPage() {
  const [modalOpen, setModalOpen] = useState(false)
  const goalsQuery = useQuery({ queryKey: ['goals'], queryFn: listGoals })

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">{t('goals.list.title')}</h1>
        <Button onClick={() => setModalOpen(true)}>{t('goals.list.newGoal')}</Button>
      </div>

      {goalsQuery.isLoading && <p className="text-sm text-gray-500">{t('common.loading')}</p>}

      {goalsQuery.data && goalsQuery.data.length === 0 && (
        <p className="text-sm text-gray-500">{t('goals.list.empty')}</p>
      )}

      {goalsQuery.data && goalsQuery.data.length > 0 && (
        <ul className="flex flex-col gap-2">
          {goalsQuery.data.map((goal) => {
            const isClosed = isClosedGoalStatus(goal.status)
            return (
              <li key={goal.id}>
                <Card className="flex items-center justify-between hover:border-blue-300">
                  <Link
                    to={resolveGoalListTarget(goal.id, goal.status)}
                    className="flex flex-1 flex-col"
                  >
                    <span className="font-medium text-gray-900">{goal.name}</span>
                    <span className="text-xs text-gray-500">
                      {t(`goals.list.status.${goal.status}`)}
                    </span>
                  </Link>
                  {isClosed && (
                    <Link
                      to={ROUTES.goalExport(goal.id)}
                      className="text-sm text-blue-600 hover:underline"
                    >
                      {t('goals.list.exportLink')}
                    </Link>
                  )}
                  {goal.status === 'ACTIVE' && (
                    <Link
                      to={ROUTES.goalResult(goal.id)}
                      className="text-sm text-blue-600 hover:underline"
                    >
                      {t('goals.list.resultLink')}
                    </Link>
                  )}
                </Card>
              </li>
            )
          })}
        </ul>
      )}

      <NewGoalModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  )
}
