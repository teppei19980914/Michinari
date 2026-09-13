import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ROUTES } from '../../constants/routes'
import { useToast } from '../../components/Toast'
import {
  finalizeReadingRecord,
  finalizeRecord,
  finalizeWorkRecord,
  sendChat,
  sendReadingChat,
  sendWorkChat,
  type ChatMessageRead,
  type DailyRecordRead,
} from '../../api/records'
import type { GoalRead } from '../../api/goals'
import {
  isAllCategoriesReported,
  toCategoryReportedState,
  type CategoryPresence,
} from './categoryCompletion'
import { invalidateDailyRecordCaches } from './invalidateDailyRecordCaches'
import { resolveCategoryGoalId } from './resolveCategoryGoalId'
import { filterCategoryMessages } from './dailyChatMessage'
import { useCategoryChat, type CategoryChat } from './useCategoryChat'
import { useCategoryFinalize, type CategoryFinalize } from './useCategoryFinalize'
import type { DailyReportDraft } from './useDailyReportDraft'
import type { DailyRecordQueries } from './useDailyRecordQueries'
import { buildStudyLogPayload } from './studyLogForm'
import { buildReadingLogPayload } from './readingLogForm'
import { buildWorkLogPayload } from './workLogForm'
import { buildDiaryEntriesPayload } from './diaryForm'

/** 1カテゴリ分の操作（AI対話・確定）と、そのカテゴリに属する対話履歴。 */
export type CategoryActions = {
  chat: CategoryChat
  finalize: CategoryFinalize
  messages: ChatMessageRead[]
}

export type DailyReportActions = {
  exam: CategoryActions
  reading: CategoryActions
  work: CategoryActions
}

export type DailyReportActionsOptions = {
  targetDate: string
  queries: DailyRecordQueries
  draft: DailyReportDraft
  /** 目標タブの状態。対話・確定の対象となる1目標の解決に使う。 */
  goalTabs: { showGoalSelector: boolean; selectedGoal: GoalRead | undefined }
  /** その日そのカテゴリに確定すべき目標があるか（resolveVisibleReportTargets）。 */
  presence: CategoryPresence
  /** 確定完了でダッシュボードへ遷移する直前に呼ぶ（離脱警告を通すため）。 */
  onBeforeLeave: () => void
}

/** 各カテゴリ共通の引数。異なるのは送信先と積む下書きだけなので、それ以外をここにまとめる。 */
type CategoryOptions = {
  targetDate: string
  draft: DailyReportDraft
  goalId: number | null
  onFinalized: (record: DailyRecordRead) => void
  onError: (error: unknown) => void
}

function useExamActions({
  targetDate,
  draft,
  goalId,
  onFinalized,
  onError,
}: CategoryOptions): CategoryActions {
  const chat = useCategoryChat({
    goalId,
    purpose: 'DAILY_FEEDBACK',
    sendRequest: (message) =>
      sendChat(targetDate, {
        goal_id: goalId as number,
        message,
        study_logs: buildStudyLogPayload(draft.studyLogValues),
        diary_entries: buildDiaryEntriesPayload(draft.diaryValues),
      }),
    setMessages: draft.setChatMessages,
    onError,
  })
  const finalize = useCategoryFinalize({
    finalizeRequest: () =>
      finalizeRecord(targetDate, {
        study_logs: buildStudyLogPayload(draft.studyLogValues),
        diary_entries: buildDiaryEntriesPayload(draft.diaryValues),
      }),
    onFinalized,
    onError,
  })

  return {
    chat,
    finalize,
    messages: filterCategoryMessages(draft.chatMessages, 'DAILY_FEEDBACK', goalId),
  }
}

function useReadingActions({
  targetDate,
  draft,
  goalId,
  onFinalized,
  onError,
}: CategoryOptions): CategoryActions {
  const chat = useCategoryChat({
    goalId,
    purpose: 'DAILY_FEEDBACK_READING',
    sendRequest: (message) =>
      sendReadingChat(targetDate, {
        goal_id: goalId as number,
        message,
        reading_logs: buildReadingLogPayload(draft.readingLogValues),
      }),
    setMessages: draft.setChatMessages,
    onError,
  })
  const finalize = useCategoryFinalize({
    finalizeRequest: () =>
      finalizeReadingRecord(targetDate, {
        reading_logs: buildReadingLogPayload(draft.readingLogValues),
      }),
    onFinalized,
    onError,
  })

  return {
    chat,
    finalize,
    messages: filterCategoryMessages(draft.chatMessages, 'DAILY_FEEDBACK_READING', goalId),
  }
}

function useWorkActions({
  targetDate,
  draft,
  goalId,
  onFinalized,
  onError,
}: CategoryOptions): CategoryActions {
  const chat = useCategoryChat({
    goalId,
    purpose: 'DAILY_FEEDBACK_WORK',
    sendRequest: (message) =>
      sendWorkChat(targetDate, {
        goal_id: goalId as number,
        message,
        work_logs: buildWorkLogPayload(draft.workLogValues),
      }),
    setMessages: draft.setChatMessages,
    onError,
  })
  const finalize = useCategoryFinalize({
    finalizeRequest: () =>
      finalizeWorkRecord(targetDate, {
        work_logs: buildWorkLogPayload(draft.workLogValues),
      }),
    onFinalized,
    onError,
  })

  return {
    chat,
    finalize,
    messages: filterCategoryMessages(draft.chatMessages, 'DAILY_FEEDBACK_WORK', goalId),
  }
}

/**
 * SC-06 日次報告のカテゴリ別操作（AI対話の送信・報告の確定）をまとめる。
 *
 * 3カテゴリで異なるのは送信先と積む下書きだけで、応答の扱いも確定後の処理も同一である。
 * 画面側はカテゴリごとの`{ chat, finalize, messages }`を受け取るだけでよい。
 *
 * これらのフックは画面側（カテゴリセクションの外）で呼ぶ必要がある。セクションはタブ切り替えで
 * 出し入れされるため、セクション内でフックを持つと切り替えのたびに送信中状態やプロンプト省略
 * 通知（wasTruncated）が失われる。
 */
export function useDailyReportActions({
  targetDate,
  queries,
  draft,
  goalTabs,
  presence,
  onBeforeLeave,
}: DailyReportActionsOptions): DailyReportActions {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showApiError } = useToast()

  // 対話・確定の対象goal_id。日次フィードバックを目標単位の会話へ分離したため（Phase26、
  // 未決事項L-07の解消方針転換）、表示中のカテゴリセクションがどの1目標を指しているかを解決する。
  const activeExamGoal = (queries.goals.data ?? []).find(
    (goal) => goal.status === 'ACTIVE' && goal.category === 'EXAM',
  )

  /** 確定後の共通処理。関連キャッシュを無効化し、表示対象の全カテゴリが確定済みになった場合のみ
   * ダッシュボードへ遷移する。1カテゴリのみの確定では画面に留まり、該当セクションだけが
   * 読み取り専用に切り替わる（仕様変更2026-09-05）。 */
  const onFinalized = (record: DailyRecordRead) => {
    invalidateDailyRecordCaches(queryClient, targetDate)
    if (isAllCategoriesReported(presence, toCategoryReportedState(record))) {
      onBeforeLeave()
      navigate(ROUTES.dashboard)
    }
  }
  const shared = { targetDate, draft, onFinalized, onError: showApiError }

  return {
    exam: useExamActions({
      ...shared,
      goalId: resolveCategoryGoalId(goalTabs, 'EXAM', activeExamGoal?.id ?? null),
    }),
    reading: useReadingActions({
      ...shared,
      goalId: resolveCategoryGoalId(
        goalTabs,
        'READING',
        queries.readingBooks.data?.[0]?.goal.id ?? null,
      ),
    }),
    work: useWorkActions({
      ...shared,
      goalId: resolveCategoryGoalId(
        goalTabs,
        'WORK',
        queries.workAssignments.data?.[0]?.goal.id ?? null,
      ),
    }),
  }
}
