import { Navigate, useParams } from 'react-router-dom'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { ROUTES } from '../constants/routes'
import { GoalTabBar } from '../features/record/GoalTabBar'
import { LeaveConfirmModal } from '../features/record/LeaveConfirmModal'
import { ExamReportSection } from '../features/record/ExamReportSection'
import { ReadingReportSection } from '../features/record/ReadingReportSection'
import { WorkReportSection } from '../features/record/WorkReportSection'
import { toCategoryReportedState } from '../features/record/categoryCompletion'
import { resolveDailyReportGuard } from '../features/record/resolveDailyReportGuard'
import { resolveVisibleReportTargets } from '../features/record/resolveVisibleReportTargets'
import { useDailyReportData } from '../features/record/useDailyReportData'
import { useDailyReportDraft } from '../features/record/useDailyReportDraft'
import { useDailyReportActions } from '../features/record/useDailyReportActions'
import { useGoalReportTabs } from '../features/record/useGoalReportTabs'
import { useLeaveConfirm } from '../features/record/useLeaveConfirm'

/** SC-06 日次報告（仕様書6.5）。上段=実績入力+日記、下段=AI対話の2段構成。
 *
 * この画面は「取得 → 表示状態の判定 → カテゴリ別セクションの配置」に徹し、下書きの保持
 * （useDailyReportDraft）・送信と確定（useDailyReportActions）・離脱警告（useLeaveConfirm）・
 * 表示対象の絞り込み（resolveVisibleReportTargets）はそれぞれのモジュールへ委ねる。
 *
 * 確定（finalize）はカテゴリ（資格試験/読書/仕事）ごとに独立しており、あるカテゴリを確定
 * しても他カテゴリは引き続き入力・確定できる（仕様変更2026-09-05）。確定済みのカテゴリは
 * そのセクションのみ読み取り専用表示に切り替わる。
 *
 * 着手中の目標が2件以上ある場合、目標タブで表示対象を切り替える（useGoalReportTabs）。
 * 切り替えは表示のみに作用し、下書き値は全目標分を常に保持する。 */
export function DailyReportPage() {
  const { date } = useParams<{ date: string }>()
  const targetDate = date as string

  const { queries, slotNames } = useDailyReportData(targetDate)
  const { reportableGoals, showGoalSelector, selectedGoalId, setSelectedGoalId, selectedGoal } =
    useGoalReportTabs(queries.goals.data ?? [])
  const draft = useDailyReportDraft(queries, setSelectedGoalId)
  const leaveConfirm = useLeaveConfirm(draft.hasUnsavedInput)

  const targets = resolveVisibleReportTargets({
    showGoalSelector,
    selectedGoal,
    goals: queries.goals.data ?? [],
    quotaItems: queries.quota.data ?? [],
    readingBooks: queries.readingBooks.data ?? [],
    workAssignments: queries.workAssignments.data ?? [],
  })
  const actions = useDailyReportActions({
    targetDate,
    queries,
    draft,
    goalTabs: { showGoalSelector, selectedGoal },
    presence: targets.presence,
    onBeforeLeave: leaveConfirm.allowNextNavigation,
  })

  // 表示状態（ローディング/エラー/閲覧画面への転送/入力可）の判定はresolveDailyReportGuardへ
  // 集約している。全フックの呼び出しが済んだ後で評価する必要があるため、ここで呼ぶ。
  const guard = resolveDailyReportGuard(queries, targets.presence, targetDate)
  if (guard.kind === 'LOADING') {
    return <p className="p-6 text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (guard.kind === 'ERROR') {
    return <p className="p-6 text-sm text-red-600">{apiErrorMessage(guard.error)}</p>
  }
  if (guard.kind === 'REDIRECT_VIEW') {
    return <Navigate to={ROUTES.dailyReportView(targetDate)} replace />
  }
  const { record, quota } = guard
  const reported = toCategoryReportedState(record)

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-gray-900">
        {t('dailyReport.title', { date: targetDate })}
      </h1>

      {showGoalSelector && (
        <GoalTabBar
          goals={reportableGoals}
          selectedGoalId={selectedGoalId}
          onSelect={setSelectedGoalId}
        />
      )}

      {targets.showExamSection && (
        <ExamReportSection
          record={record}
          quotaItems={quota}
          targets={targets}
          draft={draft}
          slotNames={slotNames}
          actions={actions.exam}
          isReported={reported.isExamReported}
        />
      )}

      {targets.showReadingSection && (
        <ReadingReportSection
          record={record}
          readingBooks={queries.readingBooks.data ?? []}
          targets={targets}
          draft={draft}
          slotNames={slotNames}
          actions={actions.reading}
          isReported={reported.isReadingReported}
        />
      )}

      {targets.showWorkSection && (
        <WorkReportSection
          record={record}
          workAssignments={queries.workAssignments.data ?? []}
          targets={targets}
          draft={draft}
          actions={actions.work}
          isReported={reported.isWorkReported}
        />
      )}

      <LeaveConfirmModal blocker={leaveConfirm.blocker} />
    </div>
  )
}
