import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../locales/t'
import { ROUTES } from '../constants/routes'
import { Button } from '../components/Button'
import { Modal } from '../components/Modal'
import { useToast } from '../components/Toast'
import { ApiError } from '../api/client'
import { activateGoal, closeGoal, getGoal, pauseGoal, resumeGoal } from '../api/goals'
import { BasicInfoTab } from '../features/goal/BasicInfoTab'
import { SubjectsTab } from '../features/goal/SubjectsTab'
import { MaterialsTab } from '../features/goal/MaterialsTab'
import { ResourceAllocationTab } from '../features/goal/ResourceAllocationTab'
import { LoadProfileTab } from '../features/goal/LoadProfileTab'
import { isClosedGoalStatus } from '../features/goal/goalStatus'

const TABS = [
  { key: 'basicInfo', labelKey: 'goals.detail.tabs.basicInfo' },
  { key: 'subjects', labelKey: 'goals.detail.tabs.subjects' },
  { key: 'materials', labelKey: 'goals.detail.tabs.materials' },
  { key: 'resourceAllocation', labelKey: 'goals.detail.tabs.resourceAllocation' },
  { key: 'loadProfile', labelKey: 'goals.detail.tabs.loadProfile' },
] as const

type TabKey = (typeof TABS)[number]['key']

function CloseGoalModal({
  goalId,
  open,
  onClose,
}: {
  goalId: number
  open: boolean
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [needsConfirmWithoutResult, setNeedsConfirmWithoutResult] = useState(false)

  const mutation = useMutation({
    mutationFn: (confirmWithoutResult: boolean) =>
      closeGoal(goalId, { confirm_without_result: confirmWithoutResult }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goal', goalId] })
      setNeedsConfirmWithoutResult(false)
      onClose()
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === 'INVALID_STATE_TRANSITION') {
        setNeedsConfirmWithoutResult(true)
        return
      }
      showToast(error instanceof ApiError ? error.localizedMessage : t('errors.default'), 'error')
    },
  })

  return (
    <Modal
      open={open}
      onClose={() => {
        setNeedsConfirmWithoutResult(false)
        onClose()
      }}
      title={t('goals.detail.closeConfirm.title')}
    >
      <p className="text-sm text-gray-700">
        {needsConfirmWithoutResult
          ? t('goals.detail.closeConfirm.withoutResultBody')
          : t('goals.detail.closeConfirm.body')}
      </p>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          {t('common.action.cancel')}
        </Button>
        <Button
          disabled={mutation.isPending}
          onClick={() => mutation.mutate(needsConfirmWithoutResult)}
        >
          {t('common.action.confirm')}
        </Button>
      </div>
    </Modal>
  )
}

function GoalStatusActions({
  goalId,
  status,
}: {
  goalId: number
  status: string
}) {
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [closeModalOpen, setCloseModalOpen] = useState(false)
  const [resumeErrorModalOpen, setResumeErrorModalOpen] = useState(false)

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['goal', goalId] })
  const handleError = (error: unknown) => {
    showToast(error instanceof ApiError ? error.localizedMessage : t('errors.default'), 'error')
  }

  const activateMutation = useMutation({
    mutationFn: () => activateGoal(goalId),
    onSuccess: invalidate,
    onError: handleError,
  })
  const pauseMutation = useMutation({
    mutationFn: () => pauseGoal(goalId),
    onSuccess: invalidate,
    onError: handleError,
  })
  const resumeMutation = useMutation({
    mutationFn: () => resumeGoal(goalId),
    onSuccess: invalidate,
    onError: (error) => {
      if (error instanceof ApiError && error.code === 'RESOURCE_EXCEEDED') {
        setResumeErrorModalOpen(true)
        return
      }
      handleError(error)
    },
  })

  if (status === 'DRAFT') {
    return (
      <Button disabled={activateMutation.isPending} onClick={() => activateMutation.mutate()}>
        {t('goals.detail.action.activate')}
      </Button>
    )
  }
  if (status === 'ACTIVE') {
    return (
      <div className="flex gap-2">
        <Button
          variant="secondary"
          disabled={pauseMutation.isPending}
          onClick={() => pauseMutation.mutate()}
        >
          {t('goals.detail.action.pause')}
        </Button>
        <Button variant="secondary" onClick={() => setCloseModalOpen(true)}>
          {t('goals.detail.action.close')}
        </Button>
        <CloseGoalModal
          goalId={goalId}
          open={closeModalOpen}
          onClose={() => setCloseModalOpen(false)}
        />
      </div>
    )
  }
  if (status === 'PAUSED') {
    return (
      <>
        <Button disabled={resumeMutation.isPending} onClick={() => resumeMutation.mutate()}>
          {t('goals.detail.action.resume')}
        </Button>
        <Modal
          open={resumeErrorModalOpen}
          onClose={() => setResumeErrorModalOpen(false)}
          title={t('goals.detail.action.resume')}
        >
          <p className="text-sm text-gray-700">{t('goals.detail.resumeError')}</p>
          <div className="mt-4 flex justify-end">
            <Button variant="secondary" onClick={() => setResumeErrorModalOpen(false)}>
              {t('common.action.close')}
            </Button>
          </div>
        </Modal>
      </>
    )
  }
  return null
}

/** SC-03 目標詳細・編集（仕様書6.2、5タブ構成）。 */
export function GoalDetailPage() {
  const { goalId: goalIdParam } = useParams<{ goalId: string }>()
  const goalId = Number(goalIdParam)
  const [tab, setTab] = useState<TabKey>('basicInfo')

  const goalQuery = useQuery({ queryKey: ['goal', goalId], queryFn: () => getGoal(goalId) })

  if (goalQuery.isLoading) {
    return <p className="p-6 text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (goalQuery.isError || !goalQuery.data) {
    const error = goalQuery.error
    const message = error instanceof ApiError ? error.localizedMessage : t('errors.default')
    return <p className="p-6 text-sm text-red-600">{message}</p>
  }

  const goal = goalQuery.data
  const isReadOnly = isClosedGoalStatus(goal.status)

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <Link to={ROUTES.goals} className="text-sm text-blue-600 hover:underline">
        {t('goals.detail.backToList')}
      </Link>

      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">{goal.name}</h1>
        {!isReadOnly && <GoalStatusActions goalId={goal.id} status={goal.status} />}
      </div>

      {isReadOnly && (
        <p className="rounded-md bg-gray-100 px-3 py-2 text-sm text-gray-600">
          {t('goals.detail.readOnlyNotice')}
        </p>
      )}

      <div className="flex gap-1 border-b border-gray-200">
        {TABS.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => setTab(item.key)}
            className={`px-3 py-2 text-sm font-medium ${
              tab === item.key
                ? 'border-b-2 border-blue-600 text-blue-700'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {t(item.labelKey)}
          </button>
        ))}
      </div>

      {tab === 'basicInfo' && <BasicInfoTab goal={goal} readOnly={isReadOnly} />}
      {tab === 'subjects' && <SubjectsTab goal={goal} readOnly={isReadOnly} />}
      {tab === 'materials' && <MaterialsTab goal={goal} readOnly={isReadOnly} />}
      {tab === 'resourceAllocation' && <ResourceAllocationTab goal={goal} readOnly={isReadOnly} />}
      {tab === 'loadProfile' && <LoadProfileTab goal={goal} readOnly={isReadOnly} />}
    </div>
  )
}
