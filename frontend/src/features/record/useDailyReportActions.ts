import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ROUTES } from '../../constants/routes'
import { useToast } from '../../components/toastContext'
import { useAiConfigured } from '../../hooks/useAiConfigured'
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
import { generateVocabTermSuggestions, getVocabDecks } from '../../api/vocab'
import { selectDiaryEntriesEligibleForVocabSuggestions } from '../vocab/vocabSuggestionEligibility'
import { updateSettings } from '../../api/settings'
import { QUERY_KEYS } from '../../constants/queryKeys'
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
import { buildScheduleItemUpdatesPayload, selectScheduleItemIdsForGoals } from './scheduleItemsDraft'
import type { RecordInputMode } from './recordInputMode'
import {
  useDailyReportScheduleRevisionBanner,
  type DailyReportScheduleRevisionBannerStatus,
} from './useDailyReportScheduleRevisionBanner'

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
  /** カテゴリ別の作業項目id（開発Todo_スケジュール・ガントチャート_v1.1 D-35、単位4）。
   * ZeroRecordButton（「今日は何もしていない」）も、下書きで変更された作業項目があれば
   * そのカテゴリの確定APIへ含めて送るために使う（2026-11-24、利用者の判断）。 */
  scheduleItemIdsByCategory: Record<GoalCategory, ReadonlySet<number>>
  milestoneCelebration: MilestoneCelebrationForPage
  /** 確定後に自動生成した修正案の状態（開発Todo_スケジュール・ガントチャート_v1.1
   * 13.1・13.8、単位5）。目標IDごとに持つ（カテゴリ内に複数の目標がありうるため）。 */
  scheduleRevisionStatusByGoalId: Record<number, DailyReportScheduleRevisionBannerStatus>
  /** ZeroRecordButton（「今日は何もしていない」）等、本フック以外の経路で確定した場合に
   * 同じ生成依頼を行うための窓口（単位5、14章補足2「ひとこと記録モードの確定も対象」）。 */
  generateScheduleRevisionForGoals: (goalIds: number[], recordDate: string) => void
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
  /** このカテゴリに属する作業項目id（開発Todo_スケジュール・ガントチャート_v1.1 D-35、
   * 単位4）。確定APIはその種別の目標に属する行だけを受け付けるため、下書き全体
   * （全カテゴリ分）からここで渡された範囲だけを送信対象に絞り込む。 */
  scheduleItemIds: ReadonlySet<number>
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

/** 資格試験の確定成功後、日記（学んだこと）が書かれた目標ごとに単語帳への用語提案を
 * 作る（開発Todo_単語帳_v1.0 要件D D-U4）。AI未設定・その目標に単語帳が1つも無い場合は
 * 呼ばない。失敗しても確定処理自体の成功表示を妨げない「静かな失敗」とする（D-D18、
 * `persistExamLastMode`と同じベストエフォートの副作用パターン）。`examGoalIds`は呼び出し側が
 * 持つACTIVEなEXAM目標ID集合（単語帳はEXAM専用のため、対象外の目標への無駄な問い合わせを
 * 避ける、dry-reviewer・performance-reviewerレビューで検出、2026-11-21）。 */
export function triggerVocabTermSuggestions(
  record: DailyRecordRead,
  targetDate: string,
  aiConfigured: boolean,
  queryClient: QueryClient,
  examGoalIds: ReadonlySet<number>,
): void {
  if (!aiConfigured) return
  for (const entry of selectDiaryEntriesEligibleForVocabSuggestions(
    record.diary_entries,
    examGoalIds,
  )) {
    const goalId = entry.goal_id
    getVocabDecks(goalId)
      .then((decks) => {
        if (decks.length === 0) return undefined
        return generateVocabTermSuggestions(goalId, targetDate).then(() => {
          queryClient.invalidateQueries({
            queryKey: QUERY_KEYS.vocabTermSuggestions(goalId, targetDate),
          })
        })
      })
      .catch(() => undefined)
  }
}

function useExamActions({
  targetDate,
  draft,
  goalId,
  scheduleItemIds,
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
        schedule_item_updates: buildScheduleItemUpdatesPayload(
          draft.scheduleItemValues,
          scheduleItemIds,
        ),
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
  scheduleItemIds,
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
        schedule_item_updates: buildScheduleItemUpdatesPayload(
          draft.scheduleItemValues,
          scheduleItemIds,
        ),
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
  scheduleItemIds,
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
        schedule_item_updates: buildScheduleItemUpdatesPayload(
          draft.scheduleItemValues,
          scheduleItemIds,
        ),
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
  const aiConfigured = useAiConfigured()
  const scheduleRevisionBanner = useDailyReportScheduleRevisionBanner()

  // 対話・確定の対象goal_id。日次フィードバックを目標単位の会話へ分離したため（Phase26、
  // 未決事項L-07の解消方針転換）、表示中のカテゴリセクションがどの1目標を指しているかを解決する。
  const activeExamGoals = (queries.goals.data ?? []).filter(
    (goal) => goal.status === 'ACTIVE' && goal.category === 'EXAM',
  )
  const activeExamGoalIds = new Set(activeExamGoals.map((goal) => goal.id))
  const examGoalId = resolveCategoryGoalId(goalTabs, 'EXAM', activeExamGoals[0]?.id ?? null)
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

  // 「今日の作業項目」欄の送信対象（開発Todo_スケジュール・ガントチャート_v1.1 D-35、
  // 単位4）。確定APIはその種別の目標に属する行だけを受け付けるため、下書き全体から
  // カテゴリごとに対象idを絞り込む（studyLogValues等と同様、タブ選択に関わらず
  // 全ACTIVE目標分を送る、仕様変更2026-09-05と同じ方針）。
  const activeReadingGoalIds = new Set(
    (queries.readingBooks.data ?? []).map((entry) => entry.goal.id),
  )
  const activeWorkGoalIds = new Set(
    (queries.workAssignments.data ?? []).map((entry) => entry.goal.id),
  )
  const scheduleItemsData = queries.scheduleItems.data ?? []
  const examScheduleItemIds = selectScheduleItemIdsForGoals(scheduleItemsData, activeExamGoalIds)
  const readingScheduleItemIds = selectScheduleItemIdsForGoals(
    scheduleItemsData,
    activeReadingGoalIds,
  )
  const workScheduleItemIds = selectScheduleItemIdsForGoals(scheduleItemsData, activeWorkGoalIds)

  /** 確定後の共通処理。関連キャッシュを無効化し、表示対象の全カテゴリが確定済みになった場合のみ
   * ダッシュボードへ遷移する。1カテゴリのみの確定では画面に留まり、該当セクションだけが
   * 読み取り専用に切り替わる（仕様変更2026-09-05）。 */
  const onFinalized = (record: DailyRecordRead) => {
    invalidateDailyRecordCaches(queryClient, targetDate)
    // 確定した種別のうち遅れのある目標ごとに、画面から修正案の生成を依頼する
    // （新しい常駐処理を増やさない、13.1）。
    scheduleRevisionBanner.generateForGoals(record.schedule_revision_candidates ?? [], targetDate)
    if (isAllCategoriesReported(presence, toCategoryReportedState(record))) {
      navigate(ROUTES.dashboard)
    }
  }
  const shared = { targetDate, draft, onError: showApiError }

  return {
    exam: useExamActions({
      ...shared,
      goalId: examGoalId,
      scheduleItemIds: examScheduleItemIds,
      onFinalized: (record) => {
        onFinalized(record)
        milestoneQueue.checkGoal(examGoalId, 'EXAM')
        triggerVocabTermSuggestions(
          record,
          targetDate,
          aiConfigured,
          queryClient,
          activeExamGoalIds,
        )
      },
    }),
    reading: useReadingActions({
      ...shared,
      goalId: readingGoalId,
      scheduleItemIds: readingScheduleItemIds,
      onFinalized: (record) => {
        onFinalized(record)
        milestoneQueue.checkGoal(readingGoalId, 'READING')
      },
    }),
    work: useWorkActions({
      ...shared,
      goalId: workGoalId,
      scheduleItemIds: workScheduleItemIds,
      onFinalized: (record) => {
        onFinalized(record)
        milestoneQueue.checkGoal(workGoalId, 'WORK')
      },
    }),
    goalIdsByCategory: { EXAM: examGoalId, READING: readingGoalId, WORK: workGoalId },
    scheduleItemIdsByCategory: {
      EXAM: examScheduleItemIds,
      READING: readingScheduleItemIds,
      WORK: workScheduleItemIds,
    },
    milestoneCelebration: {
      current: milestoneQueue.current,
      checkGoal: milestoneQueue.checkGoal,
      onDismiss: () => milestoneQueue.dismissCurrent(showApiError),
    },
    scheduleRevisionStatusByGoalId: scheduleRevisionBanner.statusByGoalId,
    generateScheduleRevisionForGoals: scheduleRevisionBanner.generateForGoals,
  }
}
