import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ROUTES } from '../../constants/routes'
import { useToast } from '../../components/toastContext'
import {
  useMilestoneCelebrationQueue,
  type MilestoneCelebrationQueue,
} from '../milestone/useMilestoneCelebrationQueue'
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
import { updateSettings } from '../../api/settings'
import type { GoalCategory, GoalRead } from '../../api/goals'
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
import type { RecordInputMode } from './recordInputMode'

/** 1カテゴリ分の操作（AI対話・確定）と、そのカテゴリに属する対話履歴。 */
export type CategoryActions = {
  chat: CategoryChat
  finalize: CategoryFinalize
  messages: ChatMessageRead[]
}

/** 節目のお祝い（開発Todo_節目のお祝い_v1.0 §4）の、この画面向けの窓口。キュー自体は
 * 本フックが保持し、ZeroRecordButton（別の確定経路）からも`checkGoal`を呼べるよう公開する。 */
export type MilestoneCelebrationForPage = {
  current: MilestoneCelebrationQueue['current']
  checkGoal: MilestoneCelebrationQueue['checkGoal']
  onDismiss: () => void
}

export type DailyReportActions = {
  exam: CategoryActions
  reading: CategoryActions
  work: CategoryActions
  /** 確定対象の目標ID（カテゴリ別）。ZeroRecordButton（複数カテゴリを一括確定）が
   * 確定後の節目チェックに使う（開発Todo_節目のお祝い_v1.0 §4）。 */
  goalIdsByCategory: Record<GoalCategory, number | null>
  milestoneCelebration: MilestoneCelebrationForPage
}

export type DailyReportActionsOptions = {
  targetDate: string
  queries: DailyRecordQueries
  draft: DailyReportDraft
  /** 目標タブの状態。対話・確定の対象となる1目標の解決に使う。 */
  goalTabs: { showGoalSelector: boolean; selectedGoal: GoalRead | undefined }
  /** その日そのカテゴリに確定すべき目標があるか（resolveVisibleReportTargets）。 */
  presence: CategoryPresence
}

/** 各カテゴリ共通の引数。異なるのは送信先と積む下書きだけなので、それ以外をここにまとめる。 */
type CategoryOptions = {
  targetDate: string
  draft: DailyReportDraft
  goalId: number | null
  onFinalized: (record: DailyRecordRead) => void
  onError: (error: unknown) => void
}

/** 確定時に使った入力方式を「最後に使ったモード」（開発Todo「ひとこと記録」v1.0 決定事項Q3、
 * §4.1手順4）へ書き戻す。失敗しても確定処理自体は成功させる（表示の初期値が次回も
 * 直前のままになるだけで、記録そのものには影響しないため）。 */
function persistExamLastMode(mode: RecordInputMode): void {
  updateSettings({ quick_record: { last_mode_exam: mode } }).catch(() => undefined)
}
function persistReadingLastMode(mode: RecordInputMode): void {
  updateSettings({ quick_record: { last_mode_reading: mode } }).catch(() => undefined)
}
function persistWorkLastMode(mode: RecordInputMode): void {
  updateSettings({ quick_record: { last_mode_work: mode } }).catch(() => undefined)
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
    sendRequest: (message, attachmentIds) =>
      sendChat(targetDate, {
        goal_id: goalId as number,
        message,
        study_logs: buildStudyLogPayload(draft.studyLogValues),
        diary_entries: buildDiaryEntriesPayload(draft.diaryValues),
        attachment_ids: attachmentIds,
        quick_mode: draft.examMode === 'QUICK',
      }),
    setMessages: draft.setChatMessages,
    onError,
  })
  const finalize = useCategoryFinalize({
    finalizeRequest: async () => {
      const record = await finalizeRecord(targetDate, {
        study_logs: buildStudyLogPayload(draft.studyLogValues),
        diary_entries: buildDiaryEntriesPayload(draft.diaryValues),
        mood: draft.examMode === 'QUICK' ? draft.examMood : null,
      })
      persistExamLastMode(draft.examMode)
      return record
    },
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
    sendRequest: (message, attachmentIds) =>
      sendReadingChat(targetDate, {
        goal_id: goalId as number,
        message,
        reading_logs: buildReadingLogPayload(draft.readingLogValues),
        attachment_ids: attachmentIds,
        quick_mode: draft.readingMode === 'QUICK',
      }),
    setMessages: draft.setChatMessages,
    onError,
  })
  const finalize = useCategoryFinalize({
    finalizeRequest: async () => {
      const record = await finalizeReadingRecord(targetDate, {
        reading_logs: buildReadingLogPayload(draft.readingLogValues),
        mood: draft.readingMode === 'QUICK' ? draft.readingMood : null,
      })
      persistReadingLastMode(draft.readingMode)
      return record
    },
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
    sendRequest: (message, attachmentIds) =>
      sendWorkChat(targetDate, {
        goal_id: goalId as number,
        message,
        work_logs: buildWorkLogPayload(draft.workLogValues),
        attachment_ids: attachmentIds,
        quick_mode: draft.workMode === 'QUICK',
      }),
    setMessages: draft.setChatMessages,
    onError,
  })
  const finalize = useCategoryFinalize({
    finalizeRequest: async () => {
      const record = await finalizeWorkRecord(targetDate, {
        work_logs: buildWorkLogPayload(draft.workLogValues),
        mood: draft.workMode === 'QUICK' ? draft.workMood : null,
      })
      persistWorkLastMode(draft.workMode)
      return record
    },
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
}: DailyReportActionsOptions): DailyReportActions {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const milestoneQueue = useMilestoneCelebrationQueue()

  // 対話・確定の対象goal_id。日次フィードバックを目標単位の会話へ分離したため（Phase26、
  // 未決事項L-07の解消方針転換）、表示中のカテゴリセクションがどの1目標を指しているかを解決する。
  const activeExamGoal = (queries.goals.data ?? []).find(
    (goal) => goal.status === 'ACTIVE' && goal.category === 'EXAM',
  )
  const examGoalId = resolveCategoryGoalId(goalTabs, 'EXAM', activeExamGoal?.id ?? null)
  const readingGoalId = resolveCategoryGoalId(
    goalTabs,
    'READING',
    queries.readingBooks.data?.[0]?.goal.id ?? null,
  )
  const workGoalId = resolveCategoryGoalId(
    goalTabs,
    'WORK',
    queries.workAssignments.data?.[0]?.goal.id ?? null,
  )

  /** 確定後の共通処理。関連キャッシュを無効化し、表示対象の全カテゴリが確定済みになった場合のみ
   * ダッシュボードへ遷移する。1カテゴリのみの確定では画面に留まり、該当セクションだけが
   * 読み取り専用に切り替わる（仕様変更2026-09-05）。 */
  const onFinalized = (record: DailyRecordRead) => {
    invalidateDailyRecordCaches(queryClient, targetDate)
    if (isAllCategoriesReported(presence, toCategoryReportedState(record))) {
      navigate(ROUTES.dashboard)
    }
  }
  const shared = { targetDate, draft, onError: showApiError }

  return {
    exam: useExamActions({
      ...shared,
      goalId: examGoalId,
      onFinalized: (record) => {
        onFinalized(record)
        milestoneQueue.checkGoal(examGoalId, 'EXAM')
      },
    }),
    reading: useReadingActions({
      ...shared,
      goalId: readingGoalId,
      onFinalized: (record) => {
        onFinalized(record)
        milestoneQueue.checkGoal(readingGoalId, 'READING')
      },
    }),
    work: useWorkActions({
      ...shared,
      goalId: workGoalId,
      onFinalized: (record) => {
        onFinalized(record)
        milestoneQueue.checkGoal(workGoalId, 'WORK')
      },
    }),
    goalIdsByCategory: { EXAM: examGoalId, READING: readingGoalId, WORK: workGoalId },
    milestoneCelebration: {
      current: milestoneQueue.current,
      checkGoal: milestoneQueue.checkGoal,
      onDismiss: () => milestoneQueue.dismissCurrent(showApiError),
    },
  }
}
