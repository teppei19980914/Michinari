import { useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { Card } from '../components/Card'
import { getQuota, getRecord } from '../api/records'
import { listActiveReadingBooks, listActiveWorkAssignments, listGoals } from '../api/goals'
import { StudyLogSummaryList, type MaterialLabel } from '../features/record/StudyLogSummaryList'
import { ReadingLogSummaryList, type BookLabel } from '../features/record/ReadingLogSummaryList'
import {
  WorkLogSummaryList,
  type WorkAssignmentLabel,
} from '../features/record/WorkLogSummaryList'
import { DiaryEntrySummaryList } from '../features/record/DiaryEntrySummaryList'
import { ChatPanel } from '../features/record/ChatPanel'
import { CommentSection } from '../features/record/CommentSection'
import { GoalTabBar } from '../features/record/GoalTabBar'
import { useGoalReportTabs } from '../features/record/useGoalReportTabs'

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

  const recordQuery = useQuery({
    queryKey: ['record', targetDate],
    queryFn: () => getRecord(targetDate),
  })
  const quotaQuery = useQuery({
    queryKey: ['quota', targetDate],
    queryFn: () => getQuota(targetDate),
  })
  const readingBooksQuery = useQuery({
    queryKey: ['activeReadingBooks'],
    queryFn: listActiveReadingBooks,
  })
  const workAssignmentsQuery = useQuery({
    queryKey: ['activeWorkAssignments'],
    queryFn: listActiveWorkAssignments,
  })
  const goalsQuery = useQuery({
    queryKey: ['goals'],
    queryFn: () => listGoals(),
  })
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
  const diaryEntries = record.diary_entries.filter(
    (entry) => entry.diary_body || entry.diary_learned,
  )
  const materialLabels = new Map<number, MaterialLabel>(
    (quotaQuery.data ?? []).map((item) => [
      item.material_id,
      {
        name: item.material_name,
        unitLabel: item.unit_label,
        qualityMetricType: item.quality_metric_type,
      },
    ]),
  )
  const bookLabels = new Map<number, BookLabel>(
    (readingBooksQuery.data ?? []).map((entry) => [entry.book.id, { title: entry.book.title }]),
  )
  const workAssignmentLabels = new Map<number, WorkAssignmentLabel>(
    (workAssignmentsQuery.data ?? []).map((entry) => [
      entry.workAssignment.id,
      { clientName: entry.workAssignment.client_name },
    ]),
  )
  const examMessages = record.chat_messages.filter((m) => m.purpose === 'DAILY_FEEDBACK')
  const readingMessages = record.chat_messages.filter(
    (m) => m.purpose === 'DAILY_FEEDBACK_READING',
  )
  const workMessages = record.chat_messages.filter((m) => m.purpose === 'DAILY_FEEDBACK_WORK')

  // showGoalSelectorがfalse（着手中の目標が0〜1件）の間は、選択タブに関わらず従来通り
  // データの有無のみで各セクションの表示を判定する（DailyReportPageのshow*Sectionと
  // 同じ考え方）。
  const showExamSection = showGoalSelector ? selectedGoal?.category === 'EXAM' : true
  const showReadingSection = showGoalSelector
    ? selectedGoal?.category === 'READING' && record.reading_logs.length > 0
    : record.reading_logs.length > 0
  const showWorkSection = showGoalSelector
    ? selectedGoal?.category === 'WORK' && record.work_logs.length > 0
    : record.work_logs.length > 0
  const showDiarySection = showGoalSelector
    ? selectedGoal?.category === 'EXAM' && diaryEntries.length > 0
    : diaryEntries.length > 0
  const showExamChatHistory = showGoalSelector
    ? selectedGoal?.category === 'EXAM' && examMessages.length > 0
    : examMessages.length > 0
  const showReadingChatHistory = showGoalSelector
    ? selectedGoal?.category === 'READING' && readingMessages.length > 0
    : readingMessages.length > 0
  const showWorkChatHistory = showGoalSelector
    ? selectedGoal?.category === 'WORK' && workMessages.length > 0
    : workMessages.length > 0

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

      {showExamSection && (
        <section className="flex flex-col gap-2">
          <h2 className="font-medium text-gray-900">{t('dailyReportView.studyLog.title')}</h2>
          <StudyLogSummaryList studyLogs={record.study_logs} materialLabels={materialLabels} />
        </section>
      )}

      {showReadingSection && (
        <section className="flex flex-col gap-2">
          <h2 className="font-medium text-gray-900">{t('dailyReportView.readingLog.title')}</h2>
          <ReadingLogSummaryList readingLogs={record.reading_logs} bookLabels={bookLabels} />
        </section>
      )}

      {showWorkSection && (
        <section className="flex flex-col gap-2">
          <h2 className="font-medium text-gray-900">{t('dailyReportView.workLog.title')}</h2>
          <WorkLogSummaryList
            workLogs={record.work_logs}
            workAssignmentLabels={workAssignmentLabels}
          />
        </section>
      )}

      {showDiarySection && <DiaryEntrySummaryList diaryEntries={diaryEntries} />}

      {showExamChatHistory && (
        <Card className="flex flex-col gap-2">
          <h2 className="font-medium text-gray-900">{t('dailyReportView.chatHistory.title')}</h2>
          <ChatPanel messages={examMessages} readOnly />
        </Card>
      )}

      {showReadingChatHistory && (
        <Card className="flex flex-col gap-2">
          <h2 className="font-medium text-gray-900">
            {t('dailyReportView.readingChatHistory.title')}
          </h2>
          <ChatPanel messages={readingMessages} readOnly />
        </Card>
      )}

      {showWorkChatHistory && (
        <Card className="flex flex-col gap-2">
          <h2 className="font-medium text-gray-900">
            {t('dailyReportView.workChatHistory.title')}
          </h2>
          <ChatPanel messages={workMessages} readOnly />
        </Card>
      )}

      <CommentSection targetDate={targetDate} comments={record.comments} />
    </div>
  )
}
