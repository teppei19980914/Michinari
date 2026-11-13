import { Navigate, useParams } from 'react-router-dom'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import type { DailyRecordRead, QuotaItemRead } from '../api/records'
import type { ActiveReadingBook, ActiveWorkAssignment } from '../api/goals'
import { ROUTES } from '../constants/routes'
import { GoalTabBar } from '../features/record/GoalTabBar'
import { ExamReportSection } from '../features/record/ExamReportSection'
import { ReadingReportSection } from '../features/record/ReadingReportSection'
import { WorkReportSection } from '../features/record/WorkReportSection'
import { WorkMemberSection } from '../features/record/WorkMemberSection'
import { RecordConfirmationExtras } from '../features/record/RecordConfirmationExtras'
import { toCategoryReportedState } from '../features/record/categoryCompletion'
import { resolveDailyReportGuard } from '../features/record/resolveDailyReportGuard'
import {
  resolveVisibleReportTargets,
  type VisibleReportTargets,
} from '../features/record/resolveVisibleReportTargets'
import { resolveZeroRecordCategories } from '../features/record/resolveZeroRecordCategories'
import { useDailyReportData } from '../features/record/useDailyReportData'
import { useDailyReportDraft, type DailyReportDraft } from '../features/record/useDailyReportDraft'
import {
  useDailyReportActions,
  type DailyReportActions,
} from '../features/record/useDailyReportActions'
import { useGoalReportTabs } from '../features/record/useGoalReportTabs'
import { useQuickRecordSettings } from '../features/record/useQuickRecordSettings'
import { useUnsavedChangesWarning } from '../features/record/useUnsavedChangesWarning'

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
  const { lastModes, quickNoteMaxChars } = useQuickRecordSettings()
  const draft = useDailyReportDraft(`daily-report:${targetDate}`, queries, lastModes)
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
    return <p className="p-6 text-sm text-text-faint">{t('common.loading')}</p>
  }
  if (guard.kind === 'ERROR') {
    return <p className="p-6 text-sm text-danger-text">{apiErrorMessage(guard.error)}</p>
  }
  if (guard.kind === 'REDIRECT_VIEW') {
    return <Navigate to={ROUTES.dailyReportView(targetDate)} replace />
  }
  const { record, quota } = guard
  const reported = toCategoryReportedState(record)
  const zeroRecordCategories = resolveZeroRecordCategories(targets.presence, record, {
    showExamSection: targets.showExamSection,
    showReadingSection: targets.showReadingSection,
    showWorkSection: targets.showWorkSection,
  })

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-text-primary">{t('dailyReport.title', { date: targetDate })}</h1>
      <p className="text-sm text-text-faint">{t('dailyReport.estimatedDuration')}</p>

      <RecordConfirmationExtras
        targetDate={targetDate}
        zeroRecordCategories={zeroRecordCategories}
        presence={targets.presence}
        goalIdsByCategory={actions.goalIdsByCategory}
        milestoneCelebration={actions.milestoneCelebration}
      />

      {showGoalSelector && (
        <GoalTabBar
          goals={reportableGoals}
          selectedGoalId={selectedGoalId}
          onSelect={setSelectedGoalId}
        />
      )}

      <DailyReportSections
        targetDate={targetDate}
        record={record}
        quota={quota}
        targets={targets}
        draft={draft}
        slotNames={slotNames}
        actions={actions}
        reported={reported}
        quickNoteMaxChars={quickNoteMaxChars}
        readingBooks={queries.readingBooks.data ?? []}
        workAssignments={queries.workAssignments.data ?? []}
      />
    </div>
  )
}

/** カテゴリ別セクションの描画切り出し（DailyReportPage本体が100行制限に収まるよう分割。
 * ロジック自体は変えていない）。 */
function DailyReportSections({
  targetDate,
  record,
  quota,
  targets,
  draft,
  slotNames,
  actions,
  reported,
  quickNoteMaxChars,
  readingBooks,
  workAssignments,
}: {
  targetDate: string
  record: DailyRecordRead
  quota: QuotaItemRead[]
  targets: VisibleReportTargets
  draft: DailyReportDraft
  slotNames: Map<number, string>
  actions: DailyReportActions
  reported: ReturnType<typeof toCategoryReportedState>
  quickNoteMaxChars: number
  readingBooks: ActiveReadingBook[]
  workAssignments: ActiveWorkAssignment[]
}) {
  return (
    <>
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
          quickNoteMaxChars={quickNoteMaxChars}
        />
      )}

      {targets.showReadingSection && (
        <ReadingReportSection
          targetDate={targetDate}
          record={record}
          readingBooks={readingBooks}
          targets={targets}
          draft={draft}
          slotNames={slotNames}
          actions={actions.reading}
          isReported={reported.isReadingReported}
          quickNoteMaxChars={quickNoteMaxChars}
        />
      )}

      {targets.showWorkSection && (
        <WorkReportSection
          targetDate={targetDate}
          record={record}
          workAssignments={workAssignments}
          targets={targets}
          draft={draft}
          actions={actions.work}
          isReported={reported.isWorkReported}
          quickNoteMaxChars={quickNoteMaxChars}
        />
      )}

      {targets.showWorkSection && <WorkMemberSection workAssignments={workAssignments} />}
    </>
  )
}
