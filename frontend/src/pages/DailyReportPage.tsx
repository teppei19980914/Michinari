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
import { finalizeRecord, getQuota, getRecord, sendChat, sendReadingChat } from '../api/records'
import { listActiveReadingBooks } from '../api/goals'
import { StudyLogFields } from '../features/record/StudyLogFields'
import { ReadingLogFields } from '../features/record/ReadingLogFields'
import { DiaryFields } from '../features/record/DiaryFields'
import { ChatPanel } from '../features/record/ChatPanel'
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
import type { components } from '../types/api.d.ts'

type ChatMessageRead = components['schemas']['ChatMessageRead']

/** SC-06 日次報告（仕様書6.5）。上段=実績入力+日記、下段=AI対話の2段構成。
 * 実績・日記は確定（finalize）まで一切サーバへ保存しない下書き値であり、AI対話
 * （POST /records/{date}/chat）はこの下書きをプロンプトへ渡すのみで永続化しない
 * （16.7「AI呼び出しが失敗しても実績入力が失われない」）ため、ローカルstateを常に正とする。
 *
 * 読書目標の想起入力・AI対話（DAILY_FEEDBACK_READING）も同じ画面に統合するが、資格試験の
 * /chatとは別エンドポイント（/reading-chat）・別の対話履歴として扱う（データ構造編6.2）。
 * chat_messages配列はpurposeで両者が混在するため、表示時にフィルタする。 */
export function DailyReportPage() {
  const { date } = useParams<{ date: string }>()
  const targetDate = date as string
  const navigate = useNavigate()
  const queryClient = useQueryClient()
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

  const [studyLogValues, setStudyLogValues] = useState<Record<number, StudyLogFormValue>>({})
  const [readingLogValues, setReadingLogValues] = useState<Record<number, ReadingLogFormValue>>(
    {},
  )
  const [diaryBody, setDiaryBody] = useState('')
  const [diaryLearned, setDiaryLearned] = useState('')
  const [chatMessages, setChatMessages] = useState<ChatMessageRead[]>([])
  const [wasTruncated, setWasTruncated] = useState(false)
  const [readingWasTruncated, setReadingWasTruncated] = useState(false)
  const hydratedRef = useRef(false)

  useEffect(() => {
    if (
      hydratedRef.current ||
      !recordQuery.data ||
      !quotaQuery.data ||
      !readingBooksQuery.data
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
    setDiaryBody(recordQuery.data.diary_body ?? '')
    setDiaryLearned(recordQuery.data.diary_learned ?? '')
    setChatMessages(recordQuery.data.chat_messages)
  }, [recordQuery.data, quotaQuery.data, readingBooksQuery.data])

  const examMessages = chatMessages.filter((m) => m.purpose === 'DAILY_FEEDBACK')
  const readingMessages = chatMessages.filter((m) => m.purpose === 'DAILY_FEEDBACK_READING')
  const activeBooks = readingBooksQuery.data?.map((entry) => entry.book) ?? []

  const isReported = recordQuery.data?.record_state === 'REPORTED'
  const hasUnsavedInput =
    !isReported &&
    (hasAnyStudyLogInput(studyLogValues) ||
      hasAnyReadingLogInput(readingLogValues) ||
      diaryBody.trim() !== '' ||
      diaryLearned.trim() !== '')
  // ブラウザレベルの離脱（タブを閉じる・再読み込み・アドレスバーへの直接入力）を警告する。
  useUnsavedChangesWarning(hasUnsavedInput)

  // 確定成功によるnavigate()（finalizeMutation.onSuccess）まで誤ってブロックしないための
  // フラグ。レンダー中にrefを読むとReactのルール違反になるため、hasUnsavedInputの計算には
  // 含めず、useBlockerへ渡す判定関数の「呼び出し時」にのみ参照する（この関数は
  // ナビゲーション試行のタイミングでルータから呼ばれるため、レンダー中の読み取りにはならない。
  // finalizedRef.currentへの代入もfinalizeMutation.onSuccess内でnavigate()の直前に行うため、
  // 同期的なnavigate()呼び出しに対しても値が確実に反映される）。
  const finalizedRef = useRef(false)
  // アプリ内遷移（GlobalNavのリンククリック、ブラウザの戻る/進む等）を警告する
  // （仕様書6.5「確定前に画面を離脱した場合、入力内容は保存されない旨を警告する」は
  // ブラウザ離脱に限定されないため、data router化してuseBlockerを使う。App.tsx参照）。
  const blocker = useBlocker(() => hasUnsavedInput && !finalizedRef.current)

  const chatMutation = useMutation({
    mutationFn: (message: string | null) =>
      sendChat(targetDate, {
        message,
        study_logs: buildStudyLogPayload(studyLogValues),
        diary_body: diaryBody,
        diary_learned: diaryLearned,
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

  const finalizeMutation = useMutation({
    mutationFn: () =>
      finalizeRecord(targetDate, {
        study_logs: buildStudyLogPayload(studyLogValues),
        reading_logs: buildReadingLogPayload(readingLogValues),
        diary_body: diaryBody,
        diary_learned: diaryLearned,
      }),
    onSuccess: () => {
      finalizedRef.current = true
      queryClient.invalidateQueries({ queryKey: ['record', targetDate] })
      queryClient.invalidateQueries({ queryKey: ['today'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['calendar'] })
      navigate(ROUTES.dashboard)
    },
    onError: showApiError,
  })

  if (recordQuery.isLoading || quotaQuery.isLoading || readingBooksQuery.isLoading) {
    return <p className="p-6 text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (
    recordQuery.isError ||
    !recordQuery.data ||
    quotaQuery.isError ||
    !quotaQuery.data ||
    readingBooksQuery.isError
  ) {
    return (
      <p className="p-6 text-sm text-red-600">
        {apiErrorMessage(recordQuery.error ?? quotaQuery.error ?? readingBooksQuery.error)}
      </p>
    )
  }
  if (isReported) {
    // 報告済は変更不可（仕様書7.2）。閲覧画面へ誘導する。
    return <Navigate to={ROUTES.dailyReportView(targetDate)} replace />
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-gray-900">
        {t('dailyReport.title', { date: targetDate })}
      </h1>

      <section className="flex flex-col gap-3">
        <h2 className="font-medium text-gray-900">{t('dailyReport.studyLog.title')}</h2>
        <StudyLogFields
          quotaItems={quotaQuery.data}
          values={studyLogValues}
          onChangeField={(materialId, field, value) =>
            setStudyLogValues((current) => ({
              ...current,
              [materialId]: { ...current[materialId], [field]: value },
            }))
          }
        />
        <DiaryFields
          diaryBody={diaryBody}
          diaryLearned={diaryLearned}
          onChangeDiaryBody={setDiaryBody}
          onChangeDiaryLearned={setDiaryLearned}
        />
      </section>

      <Card className="flex flex-col gap-3">
        <h2 className="font-medium text-gray-900">{t('dailyReport.chat.title')}</h2>
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
          onSend={examMessages.length > 0 ? (message) => chatMutation.mutate(message) : undefined}
        />
      </Card>

      {activeBooks.length > 0 && (
        <>
          <section className="flex flex-col gap-3">
            <h2 className="font-medium text-gray-900">{t('dailyReport.readingLog.title')}</h2>
            <ReadingLogFields
              books={activeBooks}
              values={readingLogValues}
              onChangeField={(bookId, field, value) =>
                setReadingLogValues((current) => ({
                  ...current,
                  [bookId]: { ...current[bookId], [field]: value },
                }))
              }
            />
          </section>

          <Card className="flex flex-col gap-3">
            <h2 className="font-medium text-gray-900">{t('dailyReport.readingChat.title')}</h2>
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
          </Card>
        </>
      )}

      <div className="flex justify-end">
        <Button disabled={finalizeMutation.isPending} onClick={() => finalizeMutation.mutate()}>
          {t('dailyReport.finalizeButton')}
        </Button>
      </div>

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
