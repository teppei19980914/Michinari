import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../locales/t'
import { ROUTES } from '../constants/routes'
import { Button } from '../components/Button'
import { Modal } from '../components/Modal'
import { Tooltip } from '../components/Tooltip'
import { useToast } from '../components/Toast'
import { ApiError, apiErrorMessage } from '../api/client'
import { activateGoal, getGoal, pauseGoal, resumeGoal } from '../api/goals'
import { BasicInfoTab } from '../features/goal/BasicInfoTab'
import { SubjectsTab } from '../features/goal/SubjectsTab'
import { MaterialsTab } from '../features/goal/MaterialsTab'
import { ResourceAllocationTab } from '../features/goal/ResourceAllocationTab'
import { LoadProfileTab } from '../features/goal/LoadProfileTab'
import { CloseGoalModal } from '../features/goal/CloseGoalModal'
import { isClosedGoalStatus } from '../features/goal/goalStatus'

const TABS = [
  {
    key: 'basicInfo',
    labelKey: 'goals.detail.tabs.basicInfo',
    tooltipKey: 'goals.detail.tabTooltips.basicInfo',
  },
  {
    key: 'subjects',
    labelKey: 'goals.detail.tabs.subjects',
    tooltipKey: 'goals.detail.tabTooltips.subjects',
  },
  {
    key: 'materials',
    labelKey: 'goals.detail.tabs.materials',
    tooltipKey: 'goals.detail.tabTooltips.materials',
  },
  {
    key: 'resourceAllocation',
    labelKey: 'goals.detail.tabs.resourceAllocation',
    tooltipKey: 'goals.detail.tabTooltips.resourceAllocation',
  },
  {
    key: 'loadProfile',
    labelKey: 'goals.detail.tabs.loadProfile',
    tooltipKey: 'goals.detail.tabTooltips.loadProfile',
  },
] as const

type TabKey = (typeof TABS)[number]['key']

function GoalStatusActions({
  goalId,
  status,
}: {
  goalId: number
  status: string
}) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [closeModalOpen, setCloseModalOpen] = useState(false)
  const [resumeErrorModalOpen, setResumeErrorModalOpen] = useState(false)

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['goal', goalId] })

  const activateMutation = useMutation({
    mutationFn: () => activateGoal(goalId),
    onSuccess: invalidate,
    onError: showApiError,
  })
  const pauseMutation = useMutation({
    mutationFn: () => pauseGoal(goalId),
    onSuccess: invalidate,
    onError: showApiError,
  })
  const resumeMutation = useMutation({
    mutationFn: () => resumeGoal(goalId),
    onSuccess: invalidate,
    onError: (error) => {
      if (error instanceof ApiError && error.code === 'RESOURCE_EXCEEDED') {
        setResumeErrorModalOpen(true)
        return
      }
      showApiError(error)
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
          onClosed={() => {
            invalidate()
            setCloseModalOpen(false)
          }}
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
    return <p className="p-6 text-sm text-red-600">{apiErrorMessage(goalQuery.error)}</p>
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
          <Tooltip key={item.key} label={t(item.tooltipKey)}>
            <button
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
          </Tooltip>
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
