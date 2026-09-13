import { useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { Card } from '../components/Card'
import type { ChatMessageRead } from '../api/records'
import { StudyLogSummaryList } from '../features/record/StudyLogSummaryList'
import { ReadingLogSummaryList } from '../features/record/ReadingLogSummaryList'
import { WorkLogSummaryList } from '../features/record/WorkLogSummaryList'
import { DiaryEntrySummaryList } from '../features/record/DiaryEntrySummaryList'
import { ChatPanel } from '../features/record/ChatPanel'
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
import { isSectionVisible } from '../features/record/sectionVisibility'

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
  // 日次フィードバックを目標単位の会話へ分離したため（Phase26、未決事項L-07の解消方針
  // 転換）、目標タブ表示中（showGoalSelector=true、着手中の目標が2件以上）は選択中の目標
  // 宛て（＋goal_id=nullの移行前レガシー）のみに絞り込む。タブが無い場合は従来どおり
  // カテゴリ（purpose）のみでの絞り込みとする（1目標のみ、または閲覧時点で全目標が
  // クローズ済みでも、その日の記録を漏れなく表示するため）。
  const matchesSelectedGoal = (m: ChatMessageRead) =>
    !showGoalSelector || m.goal_id === selectedGoal?.id || m.goal_id === null
  const examMessages = record.chat_messages.filter(
    (m) => m.purpose === 'DAILY_FEEDBACK' && matchesSelectedGoal(m),
  )
  const readingMessages = record.chat_messages.filter(
    (m) => m.purpose === 'DAILY_FEEDBACK_READING' && matchesSelectedGoal(m),
  )
  const workMessages = record.chat_messages.filter(
    (m) => m.purpose === 'DAILY_FEEDBACK_WORK' && matchesSelectedGoal(m),
  )

  // セクションの表示可否は日次報告画面（SC-06）と同じ規則へ寄せる（sectionVisibility.ts）。
  // タブが無い間は中身の有無だけで判定し、タブがある場合は選択中のカテゴリのみ表示する。
  const goalTabs = { showGoalSelector, selectedGoal }
  // 資格試験のみ中身の有無を問わない。実績も日記も無い日でも、その日を「報告済みだが
  // 記録なし」として開けるようにするための従来の挙動。
  const showExamSection = isSectionVisible(goalTabs, 'EXAM', true)
  const showReadingSection = isSectionVisible(goalTabs, 'READING', record.reading_logs.length > 0)
  const showWorkSection = isSectionVisible(goalTabs, 'WORK', record.work_logs.length > 0)
  const showDiarySection = isSectionVisible(goalTabs, 'EXAM', diaryEntries.length > 0)
  const showExamChatHistory = isSectionVisible(goalTabs, 'EXAM', examMessages.length > 0)
  const showReadingChatHistory = isSectionVisible(
    goalTabs,
    'READING',
    readingMessages.length > 0,
  )
  const showWorkChatHistory = isSectionVisible(goalTabs, 'WORK', workMessages.length > 0)

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
