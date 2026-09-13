import { useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { StudyLogSummaryList } from '../features/record/StudyLogSummaryList'
import { ReadingLogSummaryList } from '../features/record/ReadingLogSummaryList'
import { WorkLogSummaryList } from '../features/record/WorkLogSummaryList'
import { DiaryEntrySummaryList } from '../features/record/DiaryEntrySummaryList'
import { CommentSection } from '../features/record/CommentSection'
import { GoalTabBar } from '../features/record/GoalTabBar'
import { useGoalReportTabs } from '../features/record/useGoalReportTabs'
import { useDailyRecordQueries } from '../features/record/useDailyRecordQueries'
import {
  buildBookLabels,
  buildMaterialLabels,
  buildWorkAssignmentLabels,
} from '../features/record/summaryLabels'
import { filterWrittenDiaryEntries } from '../features/record/diaryForm'
import { resolveDailyReportViewSections } from '../features/record/dailyReportViewSections'
import { DailyRecordChatHistories } from '../features/record/DailyRecordChatHistories'

/** SC-08 日次報告閲覧（仕様書6.7）。実績・日記は読み取り専用、コメントのみ追加・修正・削除
 * が可能。カレンダーから「進捗のみ登録済かつ2日以上前」を選んだ場合もこの画面を再利用する
 * （日記・対話はデータが無ければ自然に非表示になるため、報告済/進捗のみのどちらにも対応する）。
 * コメント機能（CommentSection）は進捗のみ登録済の記録にも表示する。仕様書6.7はコメントを
 * 報告済（SC-08）の文脈で説明しているが、record_stateによらずコメント可否を区別する記載は
 * なく、バックエンドのadd_comment（record_service.py）もrecord_stateを問わず許可している
 * ため、この画面を開けるあらゆる記録に対して一貫して提供する。
 *
 * 着手中の目標が2件以上ある場合、日次報告画面（DailyReportPage）と同じ目標タブで表示対象を
 * 切り替えられる（仕様変更2026-09-05）。コメントは日次記録単位（カテゴリを問わない）のため
 * タブ切り替えの影響を受けず常に表示する。 */
export function DailyReportViewPage() {
  const { date } = useParams<{ date: string }>()
  const targetDate = date as string

  const {
    record: recordQuery,
    quota: quotaQuery,
    readingBooks: readingBooksQuery,
    workAssignments: workAssignmentsQuery,
    goals: goalsQuery,
  } = useDailyRecordQueries(targetDate)
  const { reportableGoals, showGoalSelector, selectedGoalId, setSelectedGoalId, selectedGoal } =
    useGoalReportTabs(goalsQuery.data ?? [])

  const hydratedTabRef = useRef(false)
  useEffect(() => {
    if (hydratedTabRef.current || !goalsQuery.data) {
      return
    }
    hydratedTabRef.current = true
    const firstActiveGoal = goalsQuery.data.find((goal) => goal.status === 'ACTIVE')
    if (firstActiveGoal) {
      setSelectedGoalId(firstActiveGoal.id)
    }
  }, [goalsQuery.data, setSelectedGoalId])

  if (
    recordQuery.isLoading ||
    quotaQuery.isLoading ||
    readingBooksQuery.isLoading ||
    workAssignmentsQuery.isLoading ||
    goalsQuery.isLoading
  ) {
    return <p className="p-6 text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (recordQuery.isError || !recordQuery.data) {
    return <p className="p-6 text-sm text-red-600">{apiErrorMessage(recordQuery.error)}</p>
  }

  const record = recordQuery.data
  const diaryEntries = filterWrittenDiaryEntries(record.diary_entries)
  const materialLabels = buildMaterialLabels(quotaQuery.data ?? [])
  const bookLabels = buildBookLabels(readingBooksQuery.data ?? [])
  const workAssignmentLabels = buildWorkAssignmentLabels(workAssignmentsQuery.data ?? [])
  const sections = resolveDailyReportViewSections({
    record,
    diaryEntries,
    goalTabs: { showGoalSelector, selectedGoal },
  })

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-gray-900">
        {t('dailyReportView.title', { date: targetDate })}
      </h1>

      {showGoalSelector && (
        <GoalTabBar
          goals={reportableGoals}
          selectedGoalId={selectedGoalId}
          onSelect={setSelectedGoalId}
        />
      )}

      {sections.showExamSection && (
        <section className="flex flex-col gap-2">
          <h2 className="font-medium text-gray-900">{t('dailyReportView.studyLog.title')}</h2>
          <StudyLogSummaryList studyLogs={record.study_logs} materialLabels={materialLabels} />
        </section>
      )}

      {sections.showReadingSection && (
        <section className="flex flex-col gap-2">
          <h2 className="font-medium text-gray-900">{t('dailyReportView.readingLog.title')}</h2>
          <ReadingLogSummaryList readingLogs={record.reading_logs} bookLabels={bookLabels} />
        </section>
      )}

      {sections.showWorkSection && (
        <section className="flex flex-col gap-2">
          <h2 className="font-medium text-gray-900">{t('dailyReportView.workLog.title')}</h2>
          <WorkLogSummaryList
            workLogs={record.work_logs}
            workAssignmentLabels={workAssignmentLabels}
          />
        </section>
      )}

      {sections.showDiarySection && <DiaryEntrySummaryList diaryEntries={diaryEntries} />}

      <DailyRecordChatHistories histories={sections.chatHistories} />

      <CommentSection targetDate={targetDate} comments={record.comments} />
    </div>
  )
}
