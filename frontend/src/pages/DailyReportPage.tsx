import { useEffect, useRef, useState } from 'react'
import { Navigate, useBlocker, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { useToast } from '../components/Toast'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { Modal } from '../components/Modal'
import { ROUTES } from '../constants/routes'
import {
  type DailyRecordRead,
  finalizeReadingRecord,
  finalizeRecord,
  finalizeWorkRecord,
  getQuota,
  getRecord,
  sendChat,
  sendReadingChat,
  sendWorkChat,
} from '../api/records'
import { listActiveReadingBooks, listActiveWorkAssignments, listGoals } from '../api/goals'
import { StudyLogFields } from '../features/record/StudyLogFields'
import { listSlots } from '../api/resources'
import { StudyLogSummaryList, type MaterialLabel } from '../features/record/StudyLogSummaryList'
import { ReadingLogFields } from '../features/record/ReadingLogFields'
import { ReadingLogSummaryList, type BookLabel } from '../features/record/ReadingLogSummaryList'
import { WorkLogFields } from '../features/record/WorkLogFields'
import {
  WorkLogSummaryList,
  type WorkAssignmentLabel,
} from '../features/record/WorkLogSummaryList'
import { DiaryFields } from '../features/record/DiaryFields'
import { DiaryEntrySummaryList } from '../features/record/DiaryEntrySummaryList'
import { ChatPanel } from '../features/record/ChatPanel'
import { isAllCategoriesReported } from '../features/record/categoryCompletion'
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
  hasAnyDiaryInput,
  initDiaryFormValues,
  type DiaryFormValue,
} from '../features/record/diaryForm'
import type { components } from '../types/api.d.ts'

type ChatMessageRead = components['schemas']['ChatMessageRead']

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
/** 「他の時間枠を追加」の候補となる全時間枠（slot_id → 名称）。
 * 配分していない枠でも実績は記録できる（仕様書6.5「未配分スロットの追加」）。 */
function useSlotNames(): Map<number, string> {
  const query = useQuery({ queryKey: ['resource-slots'], queryFn: listSlots })
  return new Map((query.data ?? []).map((slot) => [slot.id, slot.name]))
}

export function DailyReportPage() {
  const { date } = useParams<{ date: string }>()
  const targetDate = date as string
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const slotNames = useSlotNames()
  const { showApiError } = useToast()

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

  const [studyLogValues, setStudyLogValues] = useState<Record<number, StudyLogFormValue>>({})
  const [readingLogValues, setReadingLogValues] = useState<Record<number, ReadingLogFormValue>>(
    {},
  )
  const [workLogValues, setWorkLogValues] = useState<Record<number, WorkLogFormValue>>({})
  const [diaryValues, setDiaryValues] = useState<Record<number, DiaryFormValue>>({})
  const { reportableGoals, showGoalSelector, selectedGoalId, setSelectedGoalId, selectedGoal } =
    useGoalReportTabs(goalsQuery.data ?? [])
  const [chatMessages, setChatMessages] = useState<ChatMessageRead[]>([])
  const [wasTruncated, setWasTruncated] = useState(false)
  const [readingWasTruncated, setReadingWasTruncated] = useState(false)
  const [workWasTruncated, setWorkWasTruncated] = useState(false)
  const hydratedRef = useRef(false)

  // 日記（DiaryFields）は資格試験の複数目標混同対策（未決事項L-04）が目的のため、対象は
  // ACTIVEな資格試験目標のみに限定する。読書目標は想起（ReadingLogFields）が同じ役割を
  // 果たすため、両方の入力欄が並ぶ重複を避ける。
  const activeGoals = (goalsQuery.data ?? []).filter(
    (goal) => goal.status === 'ACTIVE' && goal.category === 'EXAM',
  )

  // AI対話（送信・履歴フィルタ）の対象goal_id。日次フィードバックを目標単位の会話へ分離した
  // ため（Phase26、未決事項L-07の解消方針転換）、表示中のカテゴリセクションがどの1目標を
  // 指しているかをresolveCategoryGoalIdで解決する。useMutationのmutationFnから参照するため、
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
  // （navigateIfAllSectionsReported/isFullyReported）にそのまま使うと、選択中でない
  // カテゴリを「対象なし」と誤判定してしまう）。
  const hasExamCategory = activeGoals.length > 0
  const hasReadingCategory = activeBooks.length > 0
  const hasWorkCategory = activeWorkAssignments.length > 0

  const isExamReported = recordQuery.data?.exam_record_state === 'REPORTED'
  const isReadingReported = recordQuery.data?.reading_record_state === 'REPORTED'
  const isWorkReported = recordQuery.data?.work_record_state === 'REPORTED'
  // 下書き値は全目標分を常に保持するため、確定済みでないカテゴリの入力有無のみで判定する
  // （確定済みカテゴリの下書きが残っていても、既にサーバへ反映済みのため警告対象にしない）。
  const hasUnsavedInput =
    (!isExamReported && (hasAnyStudyLogInput(studyLogValues) || hasAnyDiaryInput(diaryValues))) ||
    (!isReadingReported && hasAnyReadingLogInput(readingLogValues)) ||
    (!isWorkReported && hasAnyWorkLogInput(workLogValues))
  // ブラウザレベルの離脱（タブを閉じる・再読み込み・アドレスバーへの直接入力）を警告する。
  useUnsavedChangesWarning(hasUnsavedInput)

  // 確定成功によるnavigate()（各finalizeMutationのonSuccess）まで誤ってブロックしないための
  // フラグ。レンダー中にrefを読むとReactのルール違反になるため、hasUnsavedInputの計算には
  // 含めず、useBlockerへ渡す判定関数の「呼び出し時」にのみ参照する（この関数は
  // ナビゲーション試行のタイミングでルータから呼ばれるため、レンダー中の読み取りにはならない。
  // finalizedRef.currentへの代入もonSuccess内でnavigate()の直前に行うため、
  // 同期的なnavigate()呼び出しに対しても値が確実に反映される）。
  const finalizedRef = useRef(false)
  // アプリ内遷移（GlobalNavのリンククリック、ブラウザの戻る/進む等）を警告する
  // （仕様書6.5「確定前に画面を離脱した場合、入力内容は保存されない旨を警告する」は
  // ブラウザ離脱に限定されないため、data router化してuseBlockerを使う。App.tsx参照）。
  const blocker = useBlocker(() => hasUnsavedInput && !finalizedRef.current)

  const chatMutation = useMutation({
    mutationFn: (message: string | null) =>
      sendChat(targetDate, {
        goal_id: examGoalId as number,
        message,
        study_logs: buildStudyLogPayload(studyLogValues),
        diary_entries: buildDiaryEntriesPayload(diaryValues),
      }),
    onSuccess: (response, message) => {
      // ユーザー発言もサーバ側では保存されるが、レスポンスにはassistant_messageしか
      // 含まれない（ChatResponseスキーマ）ため、即時表示用に正のid（サーバ採番）と
      // 衝突しない負の仮idを付けたローカル表示専用エントリを組み立てる。
      setChatMessages((current) => [
        ...current,
        ...(message
          ? [
              {
                id: -Date.now(),
                goal_id: examGoalId,
                purpose: 'DAILY_FEEDBACK' as const,
                role: 'USER' as const,
                content: message,
                sequence: current.length,
                created_at: new Date().toISOString(),
              },
            ]
          : []),
        response.assistant_message,
      ])
      setWasTruncated(response.was_truncated)
    },
    onError: showApiError,
  })

  const readingChatMutation = useMutation({
    mutationFn: (message: string | null) =>
      sendReadingChat(targetDate, {
        goal_id: readingGoalId as number,
        message,
        reading_logs: buildReadingLogPayload(readingLogValues),
      }),
    onSuccess: (response, message) => {
      setChatMessages((current) => [
        ...current,
        ...(message
          ? [
              {
                id: -Date.now(),
                goal_id: readingGoalId,
                purpose: 'DAILY_FEEDBACK_READING' as const,
                role: 'USER' as const,
                content: message,
                sequence: current.length,
                created_at: new Date().toISOString(),
              },
            ]
          : []),
        response.assistant_message,
      ])
      setReadingWasTruncated(response.was_truncated)
    },
    onError: showApiError,
  })

  const workChatMutation = useMutation({
    mutationFn: (message: string | null) =>
      sendWorkChat(targetDate, {
        goal_id: workGoalId as number,
        message,
        work_logs: buildWorkLogPayload(workLogValues),
      }),
    onSuccess: (response, message) => {
      setChatMessages((current) => [
        ...current,
        ...(message
          ? [
              {
                id: -Date.now(),
                goal_id: workGoalId,
                purpose: 'DAILY_FEEDBACK_WORK' as const,
                role: 'USER' as const,
                content: message,
                sequence: current.length,
                created_at: new Date().toISOString(),
              },
            ]
          : []),
        response.assistant_message,
      ])
      setWorkWasTruncated(response.was_truncated)
    },
    onError: showApiError,
  })

  const invalidateAfterFinalize = () => {
    queryClient.invalidateQueries({ queryKey: ['record', targetDate] })
    queryClient.invalidateQueries({ queryKey: ['today'] })
    queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    queryClient.invalidateQueries({ queryKey: ['calendar'] })
  }

  // 表示対象の全カテゴリが確定済みになった場合のみダッシュボードへ遷移する。1カテゴリのみの
  // 確定では画面に留まり、該当セクションだけが読み取り専用に切り替わる（仕様変更2026-09-05）。
  const navigateIfAllSectionsReported = (record: DailyRecordRead) => {
    const allReported = isAllCategoriesReported(
      { hasExamCategory, hasReadingCategory, hasWorkCategory },
      {
        isExamReported: record.exam_record_state === 'REPORTED',
        isReadingReported: record.reading_record_state === 'REPORTED',
        isWorkReported: record.work_record_state === 'REPORTED',
      },
    )
    if (allReported) {
      finalizedRef.current = true
      navigate(ROUTES.dashboard)
    }
  }

  const examFinalizeMutation = useMutation({
    mutationFn: () =>
      finalizeRecord(targetDate, {
        study_logs: buildStudyLogPayload(studyLogValues),
        diary_entries: buildDiaryEntriesPayload(diaryValues),
      }),
    onSuccess: (record) => {
      invalidateAfterFinalize()
      navigateIfAllSectionsReported(record)
    },
    onError: showApiError,
  })

  const readingFinalizeMutation = useMutation({
    mutationFn: () =>
      finalizeReadingRecord(targetDate, {
        reading_logs: buildReadingLogPayload(readingLogValues),
      }),
    onSuccess: (record) => {
      invalidateAfterFinalize()
      navigateIfAllSectionsReported(record)
    },
    onError: showApiError,
  })

  const workFinalizeMutation = useMutation({
    mutationFn: () =>
      finalizeWorkRecord(targetDate, {
        work_logs: buildWorkLogPayload(workLogValues),
      }),
    onSuccess: (record) => {
      invalidateAfterFinalize()
      navigateIfAllSectionsReported(record)
    },
    onError: showApiError,
  })

  if (
    recordQuery.isLoading ||
    quotaQuery.isLoading ||
    readingBooksQuery.isLoading ||
    workAssignmentsQuery.isLoading ||
    goalsQuery.isLoading
  ) {
    return <p className="p-6 text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (
    recordQuery.isError ||
    !recordQuery.data ||
    quotaQuery.isError ||
    !quotaQuery.data ||
    readingBooksQuery.isError ||
    workAssignmentsQuery.isError ||
    goalsQuery.isError ||
    !goalsQuery.data
  ) {
    return (
      <p className="p-6 text-sm text-red-600">
        {apiErrorMessage(
          recordQuery.error ??
            quotaQuery.error ??
            readingBooksQuery.error ??
            workAssignmentsQuery.error ??
            goalsQuery.error,
        )}
      </p>
    )
  }

  // showGoalSelectorがfalse（着手中の目標が0〜1件）の間は、selectedGoalIdに関わらず
  // 常に全件をそのまま表示する（従来の挙動を維持し、切替UIがある場合にのみ絞り込む）。
  const visibleQuotaItems = showGoalSelector
    ? selectedGoal && selectedGoal.category === 'EXAM'
      ? quotaQuery.data.filter((item) => item.goal_id === selectedGoal.id)
      : []
    : quotaQuery.data

  const visibleDiaryGoals = showGoalSelector
    ? selectedGoal && selectedGoal.category === 'EXAM'
      ? [selectedGoal]
      : []
    : activeGoals

  const visibleBooks = showGoalSelector
    ? selectedGoal && selectedGoal.category === 'READING'
      ? (readingBooksQuery.data ?? [])
          .filter((entry) => entry.goal.id === selectedGoal.id)
          .map((entry) => entry.book)
      : []
    : activeBooks

  const visibleWorkAssignments = showGoalSelector
    ? selectedGoal && selectedGoal.category === 'WORK'
      ? (workAssignmentsQuery.data ?? [])
          .filter((entry) => entry.goal.id === selectedGoal.id)
          .map((entry) => entry.workAssignment)
      : []
    : activeWorkAssignments

  const examMessages = chatMessages.filter(
    (m) => m.purpose === 'DAILY_FEEDBACK' && (m.goal_id === examGoalId || m.goal_id === null),
  )
  const readingMessages = chatMessages.filter(
    (m) =>
      m.purpose === 'DAILY_FEEDBACK_READING' && (m.goal_id === readingGoalId || m.goal_id === null),
  )
  const workMessages = chatMessages.filter(
    (m) => m.purpose === 'DAILY_FEEDBACK_WORK' && (m.goal_id === workGoalId || m.goal_id === null),
  )

  // カテゴリごとに独立して確定する仕様変更（2026-09-05）に伴い、対象カテゴリの目標が
  // 存在しない場合はそのセクション自体を表示しない（showReading/showWorkSectionと同じ
  // 考え方に揃える。以前はEXAMのみ非選択時に無条件表示していたため、資格試験目標を
  // 持たない利用者にも空のセクションと確定ボタンが表示され、確定操作が必要になっていた）。
  const showExamSection = showGoalSelector
    ? !!selectedGoal && selectedGoal.category === 'EXAM'
    : activeGoals.length > 0
  const showReadingSection = showGoalSelector
    ? !!selectedGoal && selectedGoal.category === 'READING' && visibleBooks.length > 0
    : activeBooks.length > 0
  const showWorkSection = showGoalSelector
    ? !!selectedGoal && selectedGoal.category === 'WORK' && visibleWorkAssignments.length > 0
    : activeWorkAssignments.length > 0

  // タブ表示中かどうかではなく、その日そのカテゴリに確定すべき目標があるか
  // （hasExamCategory等）で判定する（navigateIfAllSectionsReportedと同じ理由）。
  const isFullyReported = isAllCategoriesReported(
    { hasExamCategory, hasReadingCategory, hasWorkCategory },
    { isExamReported, isReadingReported, isWorkReported },
  )
  if (isFullyReported) {
    // 表示対象の全カテゴリが確定済みは変更不可（仕様書7.2）。閲覧画面へ誘導する。
    return <Navigate to={ROUTES.dailyReportView(targetDate)} replace />
  }

  const materialLabels = new Map<number, MaterialLabel>(
    quotaQuery.data.map((item) => [
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
  const reportedDiaryEntries = recordQuery.data.diary_entries.filter(
    (entry) => entry.diary_body || entry.diary_learned,
  )

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
        <>
          {isExamReported ? (
            <section className="flex flex-col gap-3">
              <h2 className="font-medium text-gray-900">
                {t('dailyReport.studyLog.title')}
                <span className="ml-2 text-xs font-normal text-gray-400">
                  {t('dailyReport.confirmedBadge')}
                </span>
              </h2>
              <StudyLogSummaryList
                studyLogs={recordQuery.data.study_logs}
                materialLabels={materialLabels}
              />
              <DiaryEntrySummaryList diaryEntries={reportedDiaryEntries} />
            </section>
          ) : (
            <section className="flex flex-col gap-3">
              <h2 className="font-medium text-gray-900">{t('dailyReport.studyLog.title')}</h2>
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
            </section>
          )}

          <Card className="flex flex-col gap-3">
            <h2 className="font-medium text-gray-900">{t('dailyReport.chat.title')}</h2>
            {isExamReported ? (
              <ChatPanel messages={examMessages} readOnly />
            ) : (
              <>
                {examMessages.length === 0 && (
                  <Button
                    disabled={chatMutation.isPending}
                    onClick={() => chatMutation.mutate(null)}
                  >
                    {t('dailyReport.chat.startButton')}
                  </Button>
                )}
                <ChatPanel
                  messages={examMessages}
                  wasTruncated={wasTruncated}
                  isSending={chatMutation.isPending}
                  onSend={
                    examMessages.length > 0 ? (message) => chatMutation.mutate(message) : undefined
                  }
                />
              </>
            )}
          </Card>

          {!isExamReported && (
            <div className="flex justify-end">
              <Button
                disabled={examFinalizeMutation.isPending}
                onClick={() => examFinalizeMutation.mutate()}
              >
                {t('dailyReport.studyLog.finalizeButton')}
              </Button>
            </div>
          )}
        </>
      )}

      {showReadingSection && (
        <>
          {isReadingReported ? (
            <section className="flex flex-col gap-3">
              <h2 className="font-medium text-gray-900">
                {t('dailyReport.readingLog.title')}
                <span className="ml-2 text-xs font-normal text-gray-400">
                  {t('dailyReport.confirmedBadge')}
                </span>
              </h2>
              <ReadingLogSummaryList
                readingLogs={recordQuery.data.reading_logs}
                bookLabels={bookLabels}
              />
            </section>
          ) : (
            <section className="flex flex-col gap-3">
              <h2 className="font-medium text-gray-900">{t('dailyReport.readingLog.title')}</h2>
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
            </section>
          )}

          <Card className="flex flex-col gap-3">
            <h2 className="font-medium text-gray-900">{t('dailyReport.readingChat.title')}</h2>
            {isReadingReported ? (
              <ChatPanel messages={readingMessages} readOnly />
            ) : (
              <>
                {readingMessages.length === 0 && (
                  <Button
                    disabled={readingChatMutation.isPending}
                    onClick={() => readingChatMutation.mutate(null)}
                  >
                    {t('dailyReport.readingChat.startButton')}
                  </Button>
                )}
                <ChatPanel
                  messages={readingMessages}
                  wasTruncated={readingWasTruncated}
                  isSending={readingChatMutation.isPending}
                  onSend={
                    readingMessages.length > 0
                      ? (message) => readingChatMutation.mutate(message)
                      : undefined
                  }
                />
              </>
            )}
          </Card>

          {!isReadingReported && (
            <div className="flex justify-end">
              <Button
                disabled={readingFinalizeMutation.isPending}
                onClick={() => readingFinalizeMutation.mutate()}
              >
                {t('dailyReport.readingLog.finalizeButton')}
              </Button>
            </div>
          )}
        </>
      )}

      {showWorkSection && (
        <>
          {isWorkReported ? (
            <section className="flex flex-col gap-3">
              <h2 className="font-medium text-gray-900">
                {t('dailyReport.workLog.title')}
                <span className="ml-2 text-xs font-normal text-gray-400">
                  {t('dailyReport.confirmedBadge')}
                </span>
              </h2>
              <WorkLogSummaryList
                workLogs={recordQuery.data.work_logs}
                workAssignmentLabels={workAssignmentLabels}
              />
            </section>
          ) : (
            <section className="flex flex-col gap-3">
              <h2 className="font-medium text-gray-900">{t('dailyReport.workLog.title')}</h2>
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
            </section>
          )}

          <Card className="flex flex-col gap-3">
            <h2 className="font-medium text-gray-900">{t('dailyReport.workChat.title')}</h2>
            {isWorkReported ? (
              <ChatPanel messages={workMessages} readOnly />
            ) : (
              <>
                {workMessages.length === 0 && (
                  <Button
                    disabled={workChatMutation.isPending}
                    onClick={() => workChatMutation.mutate(null)}
                  >
                    {t('dailyReport.workChat.startButton')}
                  </Button>
                )}
                <ChatPanel
                  messages={workMessages}
                  wasTruncated={workWasTruncated}
                  isSending={workChatMutation.isPending}
                  onSend={
                    workMessages.length > 0
                      ? (message) => workChatMutation.mutate(message)
                      : undefined
                  }
                />
              </>
            )}
          </Card>

          {!isWorkReported && (
            <div className="flex justify-end">
              <Button
                disabled={workFinalizeMutation.isPending}
                onClick={() => workFinalizeMutation.mutate()}
              >
                {t('dailyReport.workLog.finalizeButton')}
              </Button>
            </div>
          )}
        </>
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
