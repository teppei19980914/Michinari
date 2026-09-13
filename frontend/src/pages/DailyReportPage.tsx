import { useEffect, useRef, useState } from 'react'
import { Navigate, useBlocker, useNavigate, useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { useToast } from '../components/Toast'
import { Button } from '../components/Button'
import { Modal } from '../components/Modal'
import { ROUTES } from '../constants/routes'
import {
  type ChatMessageRead,
  type DailyRecordRead,
  finalizeReadingRecord,
  finalizeRecord,
  finalizeWorkRecord,
  sendChat,
  sendReadingChat,
  sendWorkChat,
} from '../api/records'
import { StudyLogFields } from '../features/record/StudyLogFields'
import { StudyLogSummaryList } from '../features/record/StudyLogSummaryList'
import { ReadingLogFields } from '../features/record/ReadingLogFields'
import { ReadingLogSummaryList } from '../features/record/ReadingLogSummaryList'
import { WorkLogFields } from '../features/record/WorkLogFields'
import { WorkLogSummaryList } from '../features/record/WorkLogSummaryList'
import { DiaryFields } from '../features/record/DiaryFields'
import { DiaryEntrySummaryList } from '../features/record/DiaryEntrySummaryList'
import {
  isAllCategoriesReported,
  toCategoryReportedState,
} from '../features/record/categoryCompletion'
import { useDailyReportData } from '../features/record/useDailyReportData'
import { resolveDailyReportGuard } from '../features/record/resolveDailyReportGuard'
import { CategoryReportSection } from '../features/record/CategoryReportSection'
import { resolveVisibleReportTargets } from '../features/record/resolveVisibleReportTargets'
import {
  buildBookLabels,
  buildMaterialLabels,
  buildWorkAssignmentLabels,
} from '../features/record/summaryLabels'
import { invalidateDailyRecordCaches } from '../features/record/invalidateDailyRecordCaches'
import { filterCategoryMessages } from '../features/record/dailyChatMessage'
import { useCategoryChat } from '../features/record/useCategoryChat'
import { useCategoryFinalize } from '../features/record/useCategoryFinalize'
import { GoalTabBar } from '../features/record/GoalTabBar'
import { useGoalReportTabs } from '../features/record/useGoalReportTabs'
import { resolveCategoryGoalId } from '../features/record/resolveCategoryGoalId'
import { useUnsavedChangesWarning } from '../features/record/useUnsavedChangesWarning'
import {
  buildStudyLogPayload,
  hasAnyStudyLogInput,
  initStudyLogFormValues,
  type StudyLogFormValue,
} from '../features/record/studyLogForm'
import {
  buildReadingLogPayload,
  hasAnyReadingLogInput,
  initReadingLogFormValues,
  type ReadingLogFormValue,
} from '../features/record/readingLogForm'
import {
  buildWorkLogPayload,
  hasAnyWorkLogInput,
  initWorkLogFormValues,
  type WorkLogFormValue,
} from '../features/record/workLogForm'
import {
  buildDiaryEntriesPayload,
  filterWrittenDiaryEntries,
  hasAnyDiaryInput,
  initDiaryFormValues,
  type DiaryFormValue,
} from '../features/record/diaryForm'
/** SC-06 日次報告（仕様書6.5）。上段=実績入力+日記、下段=AI対話の2段構成。
 * 実績・日記は確定（finalize）まで一切サーバへ保存しない下書き値であり、AI対話
 * （POST /records/{date}/chat）はこの下書きをプロンプトへ渡すのみで永続化しない
 * （16.7「AI呼び出しが失敗しても実績入力が失われない」）ため、ローカルstateを常に正とする。
 *
 * 読書目標の想起入力・AI対話（DAILY_FEEDBACK_READING）も同じ画面に統合するが、資格試験の
 * /chatとは別エンドポイント（/reading-chat）・別の対話履歴として扱う（データ構造編6.2）。
 * chat_messages配列はpurposeで両者が混在するため、表示時にフィルタする。
 *
 * 確定（finalize）はカテゴリ（資格勉強/読書/仕事）ごとに独立しており、あるカテゴリを確定
 * しても他カテゴリは引き続き入力・確定できる（仕様変更2026-09-05）。確定済みのカテゴリは
 * そのセクションのみ読み取り専用表示に切り替わり、確定ボタンも非表示になる。
 *
 * 着手中の目標が2件以上ある場合、目標タブで表示対象を切り替える（useGoalReportTabs）。
 * 切り替えは表示のみに作用し、下書き値（studyLogValues等）は全目標分を常に保持したまま
 * カテゴリ単位で確定するため、非表示のタブに入力済みの内容が確定時に失われることはない。 */
export function DailyReportPage() {
  const { date } = useParams<{ date: string }>()
  const targetDate = date as string
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showApiError } = useToast()

  const { queries, slotNames } = useDailyReportData(targetDate)
  const {
    record: recordQuery,
    quota: quotaQuery,
    readingBooks: readingBooksQuery,
    workAssignments: workAssignmentsQuery,
    goals: goalsQuery,
  } = queries

  const [studyLogValues, setStudyLogValues] = useState<Record<number, StudyLogFormValue>>({})
  const [readingLogValues, setReadingLogValues] = useState<Record<number, ReadingLogFormValue>>(
    {},
  )
  const [workLogValues, setWorkLogValues] = useState<Record<number, WorkLogFormValue>>({})
  const [diaryValues, setDiaryValues] = useState<Record<number, DiaryFormValue>>({})
  const { reportableGoals, showGoalSelector, selectedGoalId, setSelectedGoalId, selectedGoal } =
    useGoalReportTabs(goalsQuery.data ?? [])
  const [chatMessages, setChatMessages] = useState<ChatMessageRead[]>([])
  const hydratedRef = useRef(false)

  // 日記（DiaryFields）は資格試験の複数目標混同対策（未決事項L-04）が目的のため、対象は
  // ACTIVEな資格試験目標のみに限定する。読書目標は想起（ReadingLogFields）が同じ役割を
  // 果たすため、両方の入力欄が並ぶ重複を避ける。
  const activeGoals = (goalsQuery.data ?? []).filter(
    (goal) => goal.status === 'ACTIVE' && goal.category === 'EXAM',
  )

  // AI対話（送信・履歴フィルタ）の対象goal_id。日次フィードバックを目標単位の会話へ分離した
  // ため（Phase26、未決事項L-07の解消方針転換）、表示中のカテゴリセクションがどの1目標を
  // 指しているかをresolveCategoryGoalIdで解決する。送信処理から参照するため、
  // フックより前（早期returnより前）で計算する。
  const goalTabs = { showGoalSelector, selectedGoal }
  const examGoalId = resolveCategoryGoalId(goalTabs, 'EXAM', activeGoals[0]?.id ?? null)
  const readingGoalId = resolveCategoryGoalId(
    goalTabs,
    'READING',
    readingBooksQuery.data?.[0]?.goal.id ?? null,
  )
  const workGoalId = resolveCategoryGoalId(
    goalTabs,
    'WORK',
    workAssignmentsQuery.data?.[0]?.goal.id ?? null,
  )

  useEffect(() => {
    if (
      hydratedRef.current ||
      !recordQuery.data ||
      !quotaQuery.data ||
      !readingBooksQuery.data ||
      !workAssignmentsQuery.data ||
      !goalsQuery.data
    ) {
      return
    }
    hydratedRef.current = true
    setStudyLogValues(initStudyLogFormValues(quotaQuery.data, recordQuery.data.study_logs))
    setReadingLogValues(
      initReadingLogFormValues(
        readingBooksQuery.data.map((entry) => entry.book),
        recordQuery.data.reading_logs,
      ),
    )
    setWorkLogValues(
      initWorkLogFormValues(
        workAssignmentsQuery.data.map((entry) => entry.workAssignment),
        recordQuery.data.work_logs,
      ),
    )
    setDiaryValues(
      initDiaryFormValues(
        goalsQuery.data.filter((goal) => goal.status === 'ACTIVE' && goal.category === 'EXAM'),
        recordQuery.data.diary_entries,
      ),
    )
    setChatMessages(recordQuery.data.chat_messages)
    const firstActiveGoal = goalsQuery.data.find((goal) => goal.status === 'ACTIVE')
    if (firstActiveGoal) {
      setSelectedGoalId(firstActiveGoal.id)
    }
  }, [
    recordQuery.data,
    quotaQuery.data,
    readingBooksQuery.data,
    workAssignmentsQuery.data,
    goalsQuery.data,
    setSelectedGoalId,
  ])

  const activeBooks = readingBooksQuery.data?.map((entry) => entry.book) ?? []
  const activeWorkAssignments = workAssignmentsQuery.data?.map((entry) => entry.workAssignment) ?? []
  // 「その日そのカテゴリに確定すべき目標があるか」は選択中タブに関係なく判定する必要がある
  // （showExamSection等はタブ切替で表示中のセクションを示すだけなので、確定完了判定
  // （handleFinalized/resolveDailyReportGuard）にそのまま使うと、選択中でない
  // カテゴリを「対象なし」と誤判定してしまう）。
  const hasExamCategory = activeGoals.length > 0
  const hasReadingCategory = activeBooks.length > 0
  const hasWorkCategory = activeWorkAssignments.length > 0

  const { isExamReported, isReadingReported, isWorkReported } = toCategoryReportedState(
    recordQuery.data,
  )
  // 下書き値は全目標分を常に保持するため、確定済みでないカテゴリの入力有無のみで判定する
  // （確定済みカテゴリの下書きが残っていても、既にサーバへ反映済みのため警告対象にしない）。
  const hasUnsavedInput =
    (!isExamReported && (hasAnyStudyLogInput(studyLogValues) || hasAnyDiaryInput(diaryValues))) ||
    (!isReadingReported && hasAnyReadingLogInput(readingLogValues)) ||
    (!isWorkReported && hasAnyWorkLogInput(workLogValues))
  // ブラウザレベルの離脱（タブを閉じる・再読み込み・アドレスバーへの直接入力）を警告する。
  useUnsavedChangesWarning(hasUnsavedInput)

  // 確定成功によるnavigate()（handleFinalized）まで誤ってブロックしないための
  // フラグ。レンダー中にrefを読むとReactのルール違反になるため、hasUnsavedInputの計算には
  // 含めず、useBlockerへ渡す判定関数の「呼び出し時」にのみ参照する（この関数は
  // ナビゲーション試行のタイミングでルータから呼ばれるため、レンダー中の読み取りにはならない。
  // finalizedRef.currentへの代入もhandleFinalized内でnavigate()の直前に行うため、
  // 同期的なnavigate()呼び出しに対しても値が確実に反映される）。
  const finalizedRef = useRef(false)
  // アプリ内遷移（GlobalNavのリンククリック、ブラウザの戻る/進む等）を警告する
  // （仕様書6.5「確定前に画面を離脱した場合、入力内容は保存されない旨を警告する」は
  // ブラウザ離脱に限定されないため、data router化してuseBlockerを使う。App.tsx参照）。
  const blocker = useBlocker(() => hasUnsavedInput && !finalizedRef.current)

  const examChat = useCategoryChat({
    goalId: examGoalId,
    purpose: 'DAILY_FEEDBACK',
    sendRequest: (message) =>
      sendChat(targetDate, {
        goal_id: examGoalId as number,
        message,
        study_logs: buildStudyLogPayload(studyLogValues),
        diary_entries: buildDiaryEntriesPayload(diaryValues),
      }),
    setMessages: setChatMessages,
    onError: showApiError,
  })

  const readingChat = useCategoryChat({
    goalId: readingGoalId,
    purpose: 'DAILY_FEEDBACK_READING',
    sendRequest: (message) =>
      sendReadingChat(targetDate, {
        goal_id: readingGoalId as number,
        message,
        reading_logs: buildReadingLogPayload(readingLogValues),
      }),
    setMessages: setChatMessages,
    onError: showApiError,
  })

  const workChat = useCategoryChat({
    goalId: workGoalId,
    purpose: 'DAILY_FEEDBACK_WORK',
    sendRequest: (message) =>
      sendWorkChat(targetDate, {
        goal_id: workGoalId as number,
        message,
        work_logs: buildWorkLogPayload(workLogValues),
      }),
    setMessages: setChatMessages,
    onError: showApiError,
  })

  /** 確定後の共通処理。関連キャッシュを無効化し、表示対象の全カテゴリが確定済みになった場合のみ
   * ダッシュボードへ遷移する。1カテゴリのみの確定では画面に留まり、該当セクションだけが
   * 読み取り専用に切り替わる（仕様変更2026-09-05）。 */
  const handleFinalized = (record: DailyRecordRead) => {
    invalidateDailyRecordCaches(queryClient, targetDate)

    const allReported = isAllCategoriesReported(
      { hasExamCategory, hasReadingCategory, hasWorkCategory },
      toCategoryReportedState(record),
    )
    if (allReported) {
      finalizedRef.current = true
      navigate(ROUTES.dashboard)
    }
  }

  const examFinalize = useCategoryFinalize({
    finalizeRequest: () =>
      finalizeRecord(targetDate, {
        study_logs: buildStudyLogPayload(studyLogValues),
        diary_entries: buildDiaryEntriesPayload(diaryValues),
      }),
    onFinalized: handleFinalized,
    onError: showApiError,
  })

  const readingFinalize = useCategoryFinalize({
    finalizeRequest: () =>
      finalizeReadingRecord(targetDate, {
        reading_logs: buildReadingLogPayload(readingLogValues),
      }),
    onFinalized: handleFinalized,
    onError: showApiError,
  })

  const workFinalize = useCategoryFinalize({
    finalizeRequest: () =>
      finalizeWorkRecord(targetDate, {
        work_logs: buildWorkLogPayload(workLogValues),
      }),
    onFinalized: handleFinalized,
    onError: showApiError,
  })

  // 表示状態（ローディング/エラー/閲覧画面への転送/入力可）の判定はresolveDailyReportGuardへ
  // 集約している。全フックの呼び出しが済んだ後で評価する必要があるため、ここで呼ぶ。
  const guard = resolveDailyReportGuard(
    queries,
    { hasExamCategory, hasReadingCategory, hasWorkCategory },
    targetDate,
  )
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

  const {
    quotaItems: visibleQuotaItems,
    diaryGoals: visibleDiaryGoals,
    books: visibleBooks,
    workAssignments: visibleWorkAssignments,
    showExamSection,
    showReadingSection,
    showWorkSection,
  } = resolveVisibleReportTargets({
    showGoalSelector,
    selectedGoal,
    activeGoals,
    quotaItems: quota,
    readingBooks: readingBooksQuery.data ?? [],
    workAssignments: workAssignmentsQuery.data ?? [],
  })

  const examMessages = filterCategoryMessages(chatMessages, 'DAILY_FEEDBACK', examGoalId)
  const readingMessages = filterCategoryMessages(
    chatMessages,
    'DAILY_FEEDBACK_READING',
    readingGoalId,
  )
  const workMessages = filterCategoryMessages(chatMessages, 'DAILY_FEEDBACK_WORK', workGoalId)

  const materialLabels = buildMaterialLabels(quota)
  const bookLabels = buildBookLabels(readingBooksQuery.data ?? [])
  const workAssignmentLabels = buildWorkAssignmentLabels(workAssignmentsQuery.data ?? [])
  const reportedDiaryEntries = filterWrittenDiaryEntries(record.diary_entries)

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

      {showExamSection && (
        <CategoryReportSection
          labels={{
            title: t('dailyReport.studyLog.title'),
            chatTitle: t('dailyReport.chat.title'),
            chatStartLabel: t('dailyReport.chat.startButton'),
            finalizeLabel: t('dailyReport.studyLog.finalizeButton'),
          }}
          isReported={isExamReported}
          summary={
            <>
              <StudyLogSummaryList studyLogs={record.study_logs} materialLabels={materialLabels} />
              <DiaryEntrySummaryList diaryEntries={reportedDiaryEntries} />
            </>
          }
          editor={
            <>
              <StudyLogFields
                quotaItems={visibleQuotaItems}
                values={studyLogValues}
                slotNames={slotNames}
                onChangeField={(materialId, field, value) =>
                  setStudyLogValues((current) => ({
                    ...current,
                    [materialId]: { ...current[materialId], [field]: value },
                  }))
                }
                onChangeSlotMinutes={(materialId, slotMinutes) =>
                  setStudyLogValues((current) => ({
                    ...current,
                    [materialId]: { ...current[materialId], slotMinutes },
                  }))
                }
              />
              <DiaryFields
                activeGoals={visibleDiaryGoals}
                values={diaryValues}
                onChangeField={(goalId, field, value) =>
                  setDiaryValues((current) => ({
                    ...current,
                    [goalId]: { ...current[goalId], [field]: value },
                  }))
                }
              />
            </>
          }
          messages={examMessages}
          chat={examChat}
          finalize={examFinalize}
        />
      )}

      {showReadingSection && (
        <CategoryReportSection
          labels={{
            title: t('dailyReport.readingLog.title'),
            chatTitle: t('dailyReport.readingChat.title'),
            chatStartLabel: t('dailyReport.readingChat.startButton'),
            finalizeLabel: t('dailyReport.readingLog.finalizeButton'),
          }}
          isReported={isReadingReported}
          summary={
            <ReadingLogSummaryList readingLogs={record.reading_logs} bookLabels={bookLabels} />
          }
          editor={
            <ReadingLogFields
              books={visibleBooks}
              values={readingLogValues}
              slotNames={slotNames}
              onChangeField={(bookId, field, value) =>
                setReadingLogValues((current) => ({
                  ...current,
                  [bookId]: { ...current[bookId], [field]: value },
                }))
              }
              onChangeSlotMinutes={(bookId, slotMinutes) =>
                setReadingLogValues((current) => ({
                  ...current,
                  [bookId]: { ...current[bookId], slotMinutes },
                }))
              }
            />
          }
          messages={readingMessages}
          chat={readingChat}
          finalize={readingFinalize}
        />
      )}

      {showWorkSection && (
        <CategoryReportSection
          labels={{
            title: t('dailyReport.workLog.title'),
            chatTitle: t('dailyReport.workChat.title'),
            chatStartLabel: t('dailyReport.workChat.startButton'),
            finalizeLabel: t('dailyReport.workLog.finalizeButton'),
          }}
          isReported={isWorkReported}
          summary={
            <WorkLogSummaryList
              workLogs={record.work_logs}
              workAssignmentLabels={workAssignmentLabels}
            />
          }
          editor={
            <WorkLogFields
              workAssignments={visibleWorkAssignments}
              values={workLogValues}
              onChangeField={(workAssignmentId, field, value) =>
                setWorkLogValues((current) => ({
                  ...current,
                  [workAssignmentId]: { ...current[workAssignmentId], [field]: value },
                }))
              }
            />
          }
          messages={workMessages}
          chat={workChat}
          finalize={workFinalize}
        />
      )}

      <Modal
        open={blocker.state === 'blocked'}
        onClose={() => blocker.state === 'blocked' && blocker.reset()}
        title={t('dailyReport.leaveConfirm.title')}
      >
        <p className="text-sm text-gray-700">{t('dailyReport.leaveConfirm.body')}</p>
        <div className="mt-4 flex justify-end gap-2">
          <Button
            variant="secondary"
            onClick={() => blocker.state === 'blocked' && blocker.reset()}
          >
            {t('dailyReport.leaveConfirm.stay')}
          </Button>
          <Button onClick={() => blocker.state === 'blocked' && blocker.proceed()}>
            {t('dailyReport.leaveConfirm.leave')}
          </Button>
        </div>
      </Modal>
    </div>
  )
}
