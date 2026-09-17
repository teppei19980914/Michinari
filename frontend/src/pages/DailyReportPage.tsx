import { Navigate, useParams } from 'react-router-dom'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { ROUTES } from '../constants/routes'
import { GoalTabBar } from '../features/record/GoalTabBar'
import { ExamReportSection } from '../features/record/ExamReportSection'
import { ReadingReportSection } from '../features/record/ReadingReportSection'
import { WorkReportSection } from '../features/record/WorkReportSection'
import { toCategoryReportedState } from '../features/record/categoryCompletion'
import { resolveDailyReportGuard } from '../features/record/resolveDailyReportGuard'
import { resolveVisibleReportTargets } from '../features/record/resolveVisibleReportTargets'
import { resolveZeroRecordCategories } from '../features/record/resolveZeroRecordCategories'
import { useDailyReportData } from '../features/record/useDailyReportData'
import { useDailyReportDraft } from '../features/record/useDailyReportDraft'
import { useDailyReportActions } from '../features/record/useDailyReportActions'
import { useGoalReportTabs } from '../features/record/useGoalReportTabs'
import { useUnsavedChangesWarning } from '../features/record/useUnsavedChangesWarning'
import { ZeroRecordButton } from '../features/record/ZeroRecordButton'

/** SC-06 日次報告（仕様書6.5）。上段=実績入力+日記、下段=AI対話の2段構成。
 *
 * この画面は「取得 → 表示状態の判定 → カテゴリ別セクションの配置」に徹し、下書きの保持
 * （useDailyReportDraft）・送信と確定（useDailyReportActions）・
 * 表示対象の絞り込み（resolveVisibleReportTargets）はそれぞれのモジュールへ委ねる。
 *
 * 確定（finalize）はカテゴリ（資格試験/読書/仕事）ごとに独立しており、あるカテゴリを確定
 * しても他カテゴリは引き続き入力・確定できる（仕様変更2026-09-05）。確定済みのカテゴリは
 * そのセクションのみ読み取り専用表示に切り替わる。
 *
 * 着手中の目標が2件以上ある場合、目標タブで表示対象を切り替える（useGoalReportTabs）。
 * 切り替えは表示のみに作用し、下書き値は全目標分を常に保持する。
 *
 * アプリ内遷移（別画面への移動）は警告しない（記録画面改善タスク2026-09-17）。下書きは
 * ページの外（DailyReportDraftProvider、App.tsx）が保持するため、別画面へ移動して戻っても
 * 入力内容は失われないため。ブラウザを閉じる・再読み込みは下書きが本当に失われるため、
 * その場合のみ`useUnsavedChangesWarning`（beforeunload）で警告する。 */
export function DailyReportPage() {
  const { date } = useParams<{ date: string }>()
  const targetDate = date as string

  const { queries, slotNames } = useDailyReportData(targetDate)
  const { reportableGoals, showGoalSelector, selectedGoalId, setSelectedGoalId, selectedGoal } =
    useGoalReportTabs(queries.goals.data ?? [])
  const draft = useDailyReportDraft(`daily-report:${targetDate}`, queries)
  useUnsavedChangesWarning(draft.hasUnsavedInput)

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
  const zeroRecordCategories = resolveZeroRecordCategories(targets.presence, record)

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-gray-900">
        {t('dailyReport.title', { date: targetDate })}
      </h1>
      <p className="text-sm text-gray-500">{t('dailyReport.estimatedDuration')}</p>

      <ZeroRecordButton
        targetDate={targetDate}
        categories={zeroRecordCategories}
        presence={targets.presence}
      />

      {showGoalSelector && (
        <GoalTabBar
          goals={reportableGoals}
          selectedGoalId={selectedGoalId}
          onSelect={setSelectedGoalId}
        />
      )}

      {targets.showExamSection && (
        <ExamReportSection
          targetDate={targetDate}
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
          targetDate={targetDate}
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
          targetDate={targetDate}
          record={record}
          workAssignments={queries.workAssignments.data ?? []}
          targets={targets}
          draft={draft}
          actions={actions.work}
          isReported={reported.isWorkReported}
        />
      )}
    </div>
  )
}
