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
import { activateGoal, getGoal, pauseGoal, resumeGoal, type GoalCategory } from '../api/goals'
import { BasicInfoTab } from '../features/goal/BasicInfoTab'
import { SubjectsTab } from '../features/goal/SubjectsTab'
import { MaterialsTab } from '../features/goal/MaterialsTab'
import { ResourceAllocationTab } from '../features/goal/ResourceAllocationTab'
import { LoadProfileTab } from '../features/goal/LoadProfileTab'
import { BookTab } from '../features/goal/BookTab'
import { WorkAssignmentTab } from '../features/goal/WorkAssignmentTab'
import { WorkReportTab } from '../features/goal/WorkReportTab'
import { CloseGoalModal } from '../features/goal/CloseGoalModal'
import { ERROR_CODES } from '../constants/errorCodes'
import { resolveByGoalCategory } from '../features/goal/goalCategoryVariant'
import { isClosedGoalStatus } from '../features/goal/goalStatus'
import { QUERY_KEYS } from '../constants/queryKeys'

const EXAM_TABS = [
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

/** 読書目標（category=READING）は基本情報＋書籍＋リソース配分の構成とする
 * （仕様書6.2「読書目標（category=READINGの場合）」。試験科目・教材・負荷プロファイルは
 * 表示しない。リソース配分は、読書も自由な時間に行う活動でありスロットを奪い合うため
 * 表示する（要件定義書R-64）。ただし設定は任意で、未設定でも開始できる）。 */
const READING_TABS = [
  {
    key: 'basicInfo',
    labelKey: 'goals.detail.tabs.basicInfo',
    tooltipKey: 'goals.detail.tabTooltips.basicInfoReading',
  },
  {
    key: 'book',
    labelKey: 'goals.detail.tabs.book',
    tooltipKey: 'goals.detail.tabTooltips.book',
  },
  {
    key: 'resourceAllocation',
    labelKey: 'goals.detail.tabs.resourceAllocation',
    tooltipKey: 'goals.detail.tabTooltips.resourceAllocation',
  },
] as const

/** 仕事目標（category=WORK）は基本情報＋案件情報＋月次報告＋半期評価の構成とする
 * （仕様書6.2「仕事目標（category=WORKの場合）」、試験科目・教材・リソース配分・
 * 負荷プロファイルは表示しない。読書と異なり、周期的なレポートタブを2つ持つ）。 */
const WORK_TABS = [
  {
    key: 'basicInfo',
    labelKey: 'goals.detail.tabs.basicInfo',
    tooltipKey: 'goals.detail.tabTooltips.basicInfoWork',
  },
  {
    key: 'workAssignment',
    labelKey: 'goals.detail.tabs.workAssignment',
    tooltipKey: 'goals.detail.tabTooltips.workAssignment',
  },
  {
    key: 'monthlyReport',
    labelKey: 'goals.detail.tabs.monthlyReport',
    tooltipKey: 'goals.detail.tabTooltips.monthlyReport',
  },
  {
    key: 'semiannualReview',
    labelKey: 'goals.detail.tabs.semiannualReview',
    tooltipKey: 'goals.detail.tabTooltips.semiannualReview',
  },
] as const

type TabKey =
  | (typeof EXAM_TABS)[number]['key']
  | (typeof READING_TABS)[number]['key']
  | (typeof WORK_TABS)[number]['key']

/** 種別ごとのタブ構成。要素の形が種別で異なるため union で受ける（as constはTabKeyの導出に必要）。 */
type GoalDetailTabs = typeof EXAM_TABS | typeof READING_TABS | typeof WORK_TABS

function GoalStatusActions({
  goalId,
  status,
  category,
}: {
  goalId: number
  status: string
  category: GoalCategory
}) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [closeModalOpen, setCloseModalOpen] = useState(false)
  const [resumeErrorModalOpen, setResumeErrorModalOpen] = useState(false)

  const invalidate = () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.goal(goalId) })

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
      if (error instanceof ApiError && error.code === ERROR_CODES.RESOURCE_EXCEEDED) {
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
          category={category}
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

/** SC-03 目標詳細・編集（仕様書6.2）。categoryにより資格試験（5タブ構成）・
 * 読書（基本情報＋書籍の簡略構成）でタブを出し分ける。 */
export function GoalDetailPage() {
  const { goalId: goalIdParam } = useParams<{ goalId: string }>()
  const goalId = Number(goalIdParam)
  const [tab, setTab] = useState<TabKey>('basicInfo')

  const goalQuery = useQuery({ queryKey: QUERY_KEYS.goal(goalId), queryFn: () => getGoal(goalId) })

  if (goalQuery.isLoading) {
    return <p className="p-6 text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (goalQuery.isError || !goalQuery.data) {
    return <p className="p-6 text-sm text-red-600">{apiErrorMessage(goalQuery.error)}</p>
  }

  const goal = goalQuery.data
  const isArchived = goal.archived_at !== null
  const isReadOnly = isClosedGoalStatus(goal.status)
  // 対応表から引くことで、種別を追加したときの記述漏れをtscに検知させる
  // （入れ子三項だと既定分岐で静かに資格試験のタブ構成へ落ちる）。
  const tabs = resolveByGoalCategory<GoalDetailTabs>(goal.category, {
    EXAM: EXAM_TABS,
    READING: READING_TABS,
    WORK: WORK_TABS,
  })
  // 別の目標（category違い）から遷移してきた場合、直前のタブ選択が現在のタブ構成に
  // 存在しないことがあるため、その場合のみ基本情報タブへ読み替える（stateは据え置き、
  // 同一目標内でのタブ切替の挙動には影響させない）。
  const activeTab: TabKey = tabs.some((item) => item.key === tab) ? tab : 'basicInfo'

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <Link to={ROUTES.goals} className="text-sm text-blue-600 hover:underline">
        {t('goals.detail.backToList')}
      </Link>

      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">{goal.name}</h1>
        {!isReadOnly && !isArchived && (
          <GoalStatusActions goalId={goal.id} status={goal.status} category={goal.category} />
        )}
      </div>

      {isArchived ? (
        <p className="rounded-md bg-gray-100 px-3 py-2 text-sm text-gray-600">
          {t('goals.detail.archivedNotice')}
        </p>
      ) : (
        isReadOnly && (
          <p className="rounded-md bg-gray-100 px-3 py-2 text-sm text-gray-600">
            {t('goals.detail.readOnlyNotice')}
          </p>
        )
      )}

      <div className="flex gap-1 border-b border-gray-200">
        {tabs.map((item) => (
          <Tooltip key={item.key} label={t(item.tooltipKey)}>
            <button
              type="button"
              onClick={() => setTab(item.key)}
              className={`px-3 py-2 text-sm font-medium ${
                activeTab === item.key
                  ? 'border-b-2 border-blue-600 text-blue-700'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {t(item.labelKey)}
            </button>
          </Tooltip>
        ))}
      </div>

      {activeTab === 'basicInfo' && <BasicInfoTab goal={goal} readOnly={isReadOnly} />}
      {goal.category === 'READING' && (
        <>{activeTab === 'book' && <BookTab goal={goal} readOnly={isReadOnly} />}</>
      )}
      {goal.category === 'WORK' && (
        <>
          {activeTab === 'workAssignment' && (
            <WorkAssignmentTab goal={goal} readOnly={isReadOnly} />
          )}
          {activeTab === 'monthlyReport' && <WorkReportTab goalId={goal.id} kind="monthly" />}
          {activeTab === 'semiannualReview' && (
            <WorkReportTab goalId={goal.id} kind="semiannual" />
          )}
        </>
      )}
      {goal.category === 'EXAM' && (
        <>
          {activeTab === 'subjects' && <SubjectsTab goal={goal} readOnly={isReadOnly} />}
          {activeTab === 'materials' && <MaterialsTab goal={goal} readOnly={isReadOnly} />}
          {activeTab === 'resourceAllocation' && (
            <ResourceAllocationTab goal={goal} readOnly={isReadOnly} />
          )}
          {activeTab === 'loadProfile' && <LoadProfileTab goal={goal} readOnly={isReadOnly} />}
        </>
      )}
    </div>
  )
}
