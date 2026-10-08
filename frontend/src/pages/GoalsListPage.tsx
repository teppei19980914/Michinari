import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../locales/t'
import { ROUTES } from '../constants/routes'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { Modal } from '../components/Modal'
import { useToast } from '../components/toastContext'
import { archiveGoal, listGoals, unarchiveGoal, type GoalRead } from '../api/goals'
import {
  goalStatusLabelKey,
  hasOperation,
  isClosedGoalStatus,
  isDefaultListedGoal,
  resolveGoalListTarget,
} from '../features/goal/goalStatus'
import { resolveGoalCategoryBadgeClass, resolveGoalCategoryIcon } from '../features/goal/goalCategoryBadge'
import { CHARACTER_ICONS } from '../constants/characterIcons'
import { DeleteGoalModal } from '../features/goal/DeleteGoalModal'
import { QuickCreateGoalModal } from '../features/goal/QuickCreateGoalModal'
import { QUERY_KEYS } from '../constants/queryKeys'

/** 新規目標作成の入口（仕様書「初学者導線」）。種別を選ぶと、資格はウィザードへ遷移し、
 * 読書・仕事はその場で簡易作成フォーム（QuickCreateGoalModal）を開く。目標一覧からの
 * 入口とウェルカム画面（WelcomePage）の入口を統一する設計（2026-09-18）。 */
function NewGoalEntryModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const [quickCreateCategory, setQuickCreateCategory] = useState<'READING' | 'WORK' | null>(null)

  return (
    <>
      <Modal open={open && quickCreateCategory === null} onClose={onClose} title={t('goals.list.newGoal')}>
        <div className="flex flex-col gap-2">
          <Button onClick={() => setQuickCreateCategory('READING')}>
            {t('goals.new.category.READING')}
          </Button>
          <Button onClick={() => setQuickCreateCategory('WORK')}>{t('goals.new.category.WORK')}</Button>
          <Button
            onClick={() => {
              onClose()
              navigate(ROUTES.goalNewExam)
            }}
          >
            {t('goals.new.category.EXAM')}
          </Button>
        </div>
      </Modal>
      <QuickCreateGoalModal
        // WelcomePageと同じ理由：キャンセル後の再オープンや種別切り替え時に前回の
        // 入力が残らないよう、開閉のたびに別インスタンスとして作り直す。
        key={quickCreateCategory ?? 'closed'}
        open={quickCreateCategory !== null}
        category={quickCreateCategory ?? 'READING'}
        onClose={() => {
          setQuickCreateCategory(null)
          onClose()
        }}
        onCreated={() => {
          setQuickCreateCategory(null)
          onClose()
          navigate(ROUTES.dashboard)
        }}
      />
    </>
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
      <Link to={resolveGoalListTarget(goal.id, goal.status)} className="flex flex-1 flex-col gap-1">
        <span className="flex items-center gap-1 font-medium text-gray-900">
          {goal.name}
          {goal.is_achieved && (
            <span className="flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
              <img src={CHARACTER_ICONS.achieved} alt="" className="h-4 w-4" />
              {t('goals.list.achievedBadge')}
            </span>
          )}
        </span>
        <span className="flex items-center gap-2 text-xs text-gray-500">
          <span
            className={`flex items-center gap-1 rounded-full px-2 py-0.5 font-medium ${resolveGoalCategoryBadgeClass(goal.category)}`}
          >
            <img src={resolveGoalCategoryIcon(goal.category)} alt="" className="h-4 w-4 rounded-full" />
            {t(`goals.new.category.${goal.category}`)}
          </span>
          <span className="rounded-full bg-gray-100 px-2 py-0.5 font-medium text-gray-700">
            {t(goalStatusLabelKey(goal.category, goal.status))}
          </span>
          {isArchived && (
            <span className="rounded-full bg-gray-200 px-2 py-0.5 font-medium text-gray-600">
              {t('goals.list.archivedBadge')}
            </span>
          )}
        </span>
      </Link>
      {isClosed && !isArchived && (
        <Link to={ROUTES.goalExport(goal.id)} className="text-sm text-blue-600 hover:underline">
          {t('goals.list.exportLink')}
        </Link>
      )}
      {isClosed && !isArchived && (
        <Link to={ROUTES.goalDetail(goal.id)} className="text-sm text-blue-600 hover:underline">
          {t('goals.list.detailLink')}
        </Link>
      )}
      {goal.status === 'ACTIVE' && goal.category === 'EXAM' && (
        <Link to={ROUTES.goalResult(goal.id)} className="text-sm text-blue-600 hover:underline">
          {t('goals.list.resultLink')}
        </Link>
      )}
      {hasOperation(goal, 'ARCHIVE') && (
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
      {hasOperation(goal, 'UNARCHIVE') && (
        <Button type="button" variant="secondary" onClick={() => onUnarchive(goal.id)}>
          {t('goals.list.restoreButton')}
        </Button>
      )}
      {hasOperation(goal, 'DELETE') && (
        <Button type="button" variant="secondary" onClick={() => onRequestDelete(goal)}>
          {t('goals.list.deleteButton')}
        </Button>
      )}
    </Card>
  )
}

/**
 * SC-02 目標一覧（仕様書4章・5.2「新規作成/目標選択/クローズ済目標選択」、6.15）。
 * 既定は下書き・実行中・一時停止。「すべて表示」で完了・中断・アーカイブ済みを含むすべてを出す
 * （開発Todo 1-9）。
 */
export function GoalsListPage() {
  const [newGoalModalOpen, setNewGoalModalOpen] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<GoalRead | null>(null)
  const queryClient = useQueryClient()
  const { showApiErrorWithTitle } = useToast()
  const goalsQuery = useQuery({ queryKey: QUERY_KEYS.goals(), queryFn: listGoals })

  // 状態変更の失敗は操作名を見出しにして表示する（利用者方針2026-10-04：状態変更から広げる）
  const archiveMutation = useMutation({
    mutationFn: archiveGoal,
    meta: { overlay: 'deleting' },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.goals() }),
    onError: (error) => showApiErrorWithTitle(t('goals.list.archiveButton'), error),
  })
  const unarchiveMutation = useMutation({
    mutationFn: unarchiveGoal,
    meta: { overlay: 'saving' },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.goals() }),
    onError: (error) => showApiErrorWithTitle(t('goals.list.restoreButton'), error),
  })

  const allGoals = goalsQuery.data ?? []
  const visibleGoals = showAll ? allGoals : allGoals.filter(isDefaultListedGoal)

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">{t('goals.list.title')}</h1>
        <Button onClick={() => setNewGoalModalOpen(true)}>{t('goals.list.newGoal')}</Button>
      </div>

      {goalsQuery.isLoading && <p className="text-sm text-gray-500">{t('common.loading')}</p>}

      {goalsQuery.data && allGoals.length === 0 && (
        <p className="text-sm text-gray-500">{t('goals.list.empty')}</p>
      )}

      {allGoals.length > 0 && (
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
          {t('goals.list.showAllToggle')}
        </label>
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

      <NewGoalEntryModal open={newGoalModalOpen} onClose={() => setNewGoalModalOpen(false)} />
      <DeleteGoalModal goal={deleteTarget} onClose={() => setDeleteTarget(null)} />
    </div>
  )
}
