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
import {
  archiveGoal,
  createGoal,
  deleteArchivedGoal,
  listGoals,
  unarchiveGoal,
  type GoalCategory,
  type GoalRead,
} from '../api/goals'
import { canArchiveGoal, isClosedGoalStatus, resolveGoalListTarget } from '../features/goal/goalStatus'

const GOAL_CATEGORIES: GoalCategory[] = ['EXAM', 'READING', 'WORK']

function NewGoalModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [category, setCategory] = useState<GoalCategory>('EXAM')
  const [name, setName] = useState('')
  const [startDate, setStartDate] = useState('')

  const mutation = useMutation({
    mutationFn: () => createGoal({ category, name, start_date: startDate }),
    onSuccess: (goal) => {
      queryClient.invalidateQueries({ queryKey: ['goals'] })
      onClose()
      navigate(ROUTES.goalDetail(goal.id))
    },
    onError: showApiError,
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
          {t('goals.new.categoryLabel')}
          <select
            className="rounded-md border border-gray-300 px-3 py-2 text-sm"
            value={category}
            onChange={(e) => setCategory(e.target.value as GoalCategory)}
          >
            {GOAL_CATEGORIES.map((value) => (
              <option key={value} value={value}>
                {t(`goals.new.category.${value}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {category === 'READING'
            ? t('goals.new.nameLabelReading')
            : category === 'WORK'
              ? t('goals.new.nameLabelWork')
              : t('goals.new.nameLabel')}
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

/** MD-08 完全削除確認（仕様書5.3・6.15）。学習実績も含めるかのチェックボックスを持つ。 */
function DeleteArchivedGoalModal({
  goal,
  onClose,
}: {
  goal: GoalRead | null
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [cascadeStudyLogs, setCascadeStudyLogs] = useState(true)

  const mutation = useMutation({
    mutationFn: (goalId: number) =>
      deleteArchivedGoal(goalId, { cascade_study_logs: cascadeStudyLogs }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goals'] })
      onClose()
    },
    onError: showApiError,
  })

  return (
    <Modal open={goal !== null} onClose={onClose} title={t('goals.list.deleteModal.title')}>
      <div className="flex flex-col gap-3 text-sm text-gray-700">
        <p>{t('goals.list.deleteModal.warning')}</p>
        <label className="flex items-start gap-2">
          <input
            type="checkbox"
            className="mt-1"
            checked={cascadeStudyLogs}
            onChange={(e) => setCascadeStudyLogs(e.target.checked)}
          />
          <span>
            {t('goals.list.deleteModal.cascadeCheckbox')}
            <span className="mt-0.5 block text-xs text-gray-500">
              {t('goals.list.deleteModal.cascadeHint')}
            </span>
          </span>
        </label>
        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('common.action.cancel')}
          </Button>
          <Button
            type="button"
            disabled={mutation.isPending}
            onClick={() => goal && mutation.mutate(goal.id)}
          >
            {t('goals.list.deleteModal.confirmButton')}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

function GoalCard({
  goal,
  onArchive,
  onUnarchive,
  onRequestDelete,
}: {
  goal: GoalRead
  onArchive: (goalId: number) => void
  onUnarchive: (goalId: number) => void
  onRequestDelete: (goal: GoalRead) => void
}) {
  const isClosed = isClosedGoalStatus(goal.status)
  const isArchived = goal.archived_at !== null

  return (
    <Card className="flex items-center justify-between gap-3 hover:border-blue-300">
      <Link to={resolveGoalListTarget(goal.id, goal.status)} className="flex flex-1 flex-col">
        <span className="font-medium text-gray-900">{goal.name}</span>
        <span className="text-xs text-gray-500">
          {t(`goals.new.category.${goal.category}`)}
          {' ・ '}
          {t(`goals.list.status.${goal.status}`)}
        </span>
      </Link>
      {isClosed && !isArchived && (
        <Link to={ROUTES.goalExport(goal.id)} className="text-sm text-blue-600 hover:underline">
          {t('goals.list.exportLink')}
        </Link>
      )}
      {goal.status === 'ACTIVE' && goal.category === 'EXAM' && (
        <Link to={ROUTES.goalResult(goal.id)} className="text-sm text-blue-600 hover:underline">
          {t('goals.list.resultLink')}
        </Link>
      )}
      {canArchiveGoal(goal.status, goal.archived_at) && (
        <Button
          type="button"
          variant="secondary"
          onClick={() => {
            if (window.confirm(t('goals.list.archiveConfirm'))) {
              onArchive(goal.id)
            }
          }}
        >
          {t('goals.list.archiveButton')}
        </Button>
      )}
      {isArchived && (
        <>
          <Button type="button" variant="secondary" onClick={() => onUnarchive(goal.id)}>
            {t('goals.list.restoreButton')}
          </Button>
          <Button type="button" variant="secondary" onClick={() => onRequestDelete(goal)}>
            {t('goals.list.deleteCompletelyButton')}
          </Button>
        </>
      )}
    </Card>
  )
}

/** SC-02 目標一覧（仕様書4章・5.2「新規作成/目標選択/クローズ済目標選択」、6.15）。 */
export function GoalsListPage() {
  const [newGoalModalOpen, setNewGoalModalOpen] = useState(false)
  const [showArchived, setShowArchived] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<GoalRead | null>(null)
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const goalsQuery = useQuery({ queryKey: ['goals'], queryFn: listGoals })

  const archiveMutation = useMutation({
    mutationFn: archiveGoal,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['goals'] }),
    onError: showApiError,
  })
  const unarchiveMutation = useMutation({
    mutationFn: unarchiveGoal,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['goals'] }),
    onError: showApiError,
  })

  const visibleGoals = goalsQuery.data?.filter((goal) => goal.archived_at === null) ?? []
  const archivedGoals = goalsQuery.data?.filter((goal) => goal.archived_at !== null) ?? []

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">{t('goals.list.title')}</h1>
        <Button onClick={() => setNewGoalModalOpen(true)}>{t('goals.list.newGoal')}</Button>
      </div>

      {goalsQuery.isLoading && <p className="text-sm text-gray-500">{t('common.loading')}</p>}

      {goalsQuery.data && goalsQuery.data.length === 0 && (
        <p className="text-sm text-gray-500">{t('goals.list.empty')}</p>
      )}

      {visibleGoals.length > 0 && (
        <ul className="flex flex-col gap-2">
          {visibleGoals.map((goal) => (
            <li key={goal.id}>
              <GoalCard
                goal={goal}
                onArchive={archiveMutation.mutate}
                onUnarchive={unarchiveMutation.mutate}
                onRequestDelete={setDeleteTarget}
              />
            </li>
          ))}
        </ul>
      )}

      {archivedGoals.length > 0 && (
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={showArchived}
            onChange={(e) => setShowArchived(e.target.checked)}
          />
          {t('goals.list.showArchivedToggle')}
        </label>
      )}

      {showArchived && archivedGoals.length > 0 && (
        <div className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold text-gray-700">
            {t('goals.list.archivedSectionTitle')}
          </h2>
          <ul className="flex flex-col gap-2">
            {archivedGoals.map((goal) => (
              <li key={goal.id}>
                <GoalCard
                  goal={goal}
                  onArchive={archiveMutation.mutate}
                  onUnarchive={unarchiveMutation.mutate}
                  onRequestDelete={setDeleteTarget}
                />
              </li>
            ))}
          </ul>
        </div>
      )}

      <NewGoalModal open={newGoalModalOpen} onClose={() => setNewGoalModalOpen(false)} />
      <DeleteArchivedGoalModal goal={deleteTarget} onClose={() => setDeleteTarget(null)} />
    </div>
  )
}
