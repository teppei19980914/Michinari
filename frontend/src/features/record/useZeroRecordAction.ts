import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useToast } from '../../components/toastContext'
import { ROUTES } from '../../constants/routes'
import {
  finalizeReadingRecord,
  finalizeRecord,
  finalizeWorkRecord,
  type DailyRecordRead,
  type ScheduleItemUpdateInput,
} from '../../api/records'
import type { GoalCategory } from '../../api/goals'
import { invalidateDailyRecordCaches } from './invalidateDailyRecordCaches'
import {
  isAllCategoriesReported,
  toCategoryReportedState,
  type CategoryPresence,
} from './categoryCompletion'
import type { ZeroRecordCategory } from './resolveZeroRecordCategories'
import { buildScheduleItemUpdatesPayload, type ScheduleItemDraftValue } from './scheduleItemsDraft'

/** カテゴリ別の「空の実績で確定する」呼び出し（記録画面改善タスク2026-09-17）。
 * finalize系のAPIは0件の配列を渡しても正常に完了し、そのカテゴリの状態を直接REPORTEDに
 * できる（record_service.pyのfinalize_record等はregister_progressと異なり「1件以上」を
 * 要求しない）。これを利用し、study_logs等は下書きの内容に関わらず常に空配列で確定する。
 *
 * 「今日の作業項目」欄（開発Todo_スケジュール・ガントチャート_v1.1 第4章、単位4）は
 * 「今日は何もしていない」とは独立した操作であるため、変更していればそのカテゴリの
 * schedule_item_updatesだけ積んで送る（利用者の判断、2026-11-24）。 */
const FINALIZE_AS_ZERO: Record<
  ZeroRecordCategory,
  (targetDate: string, scheduleItemUpdates: ScheduleItemUpdateInput[]) => Promise<DailyRecordRead>
> = {
  EXAM: (targetDate, scheduleItemUpdates) =>
    finalizeRecord(targetDate, {
      study_logs: [],
      diary_entries: [],
      schedule_item_updates: scheduleItemUpdates,
    }),
  READING: (targetDate, scheduleItemUpdates) =>
    finalizeReadingRecord(targetDate, {
      reading_logs: [],
      schedule_item_updates: scheduleItemUpdates,
    }),
  WORK: (targetDate, scheduleItemUpdates) =>
    finalizeWorkRecord(targetDate, { work_logs: [], schedule_item_updates: scheduleItemUpdates }),
}

export type ZeroRecordAction = {
  isPending: boolean
  submit: () => void
}

export type ZeroRecordActionOptions = {
  targetDate: string
  /** ゼロ確定の対象カテゴリ（resolveZeroRecordCategories）。 */
  categories: ZeroRecordCategory[]
  /** その日ACTIVEな全カテゴリの有無。全カテゴリ確定済みになったかの判定に使う。 */
  presence: CategoryPresence
  /** 確定後に表示するトースト文言（日種別で決まる。resolveZeroRecordMessage）。 */
  message: string
  /** カテゴリ別の目標ID（useDailyReportActionsのgoalIdsByCategory）。確定後の節目チェックに使う。 */
  goalIdsByCategory: Record<GoalCategory, number | null>
  /** 確定の直後に、そのカテゴリの目標に新しい節目が無いか確認する（開発Todo_節目のお祝い_v1.0
   * §4）。モーダル表示自体は呼び出し元（DailyReportPage）が持つキューが行う。 */
  checkMilestones?: (goalId: number | null, category: GoalCategory) => void
  /** 「今日の作業項目」欄の下書き（開発Todo_スケジュール・ガントチャート_v1.1 D-35、
   * 単位4）。カテゴリ別の対象行id（useDailyReportActionsのscheduleItemIdsByCategory）と
   * 合わせて、変更されていればそのカテゴリの確定APIへ含める。 */
  scheduleItemValues: Record<number, ScheduleItemDraftValue>
  scheduleItemIdsByCategory: Record<GoalCategory, ReadonlySet<number>>
  /** 確定後の修正案の生成依頼（単位5・14章補足2「ひとこと記録モードの確定も対象とする」）。
   * ゼロ記録（本フック）はひとこと記録モードと同じ確定処理を経るため対象に含める。 */
  generateScheduleRevisionForGoals: (goalIds: number[], recordDate: string) => void
}

/**
 * 「今日は何もしていない」ボタンの確定処理（記録画面改善タスク2026-09-17）。
 *
 * 対象カテゴリを順に空配列で確定し、完了後に成功トーストを出す。対象外のカテゴリ
 * （進捗のみ登録済み等）が残る場合は画面に留まり、その日ACTIVEな全カテゴリが確定済みに
 * なった場合のみダッシュボードへ遷移する（通常の確定と同じ規則、useDailyReportActionsの
 * onFinalizedと同型）。
 */
export function useZeroRecordAction({
  targetDate,
  categories,
  presence,
  message,
  goalIdsByCategory,
  checkMilestones,
  scheduleItemValues,
  scheduleItemIdsByCategory,
  generateScheduleRevisionForGoals,
}: ZeroRecordActionOptions): ZeroRecordAction {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showToast, showApiError } = useToast()

  const mutation = useMutation({
    mutationFn: async () => {
      let lastRecord: DailyRecordRead | undefined
      const scheduleRevisionCandidateIds: number[] = []
      for (const category of categories) {
        const scheduleItemUpdates = buildScheduleItemUpdatesPayload(
          scheduleItemValues,
          scheduleItemIdsByCategory[category],
        )
        lastRecord = await FINALIZE_AS_ZERO[category](targetDate, scheduleItemUpdates)
        scheduleRevisionCandidateIds.push(...lastRecord.schedule_revision_candidates)
      }
      return { lastRecord, scheduleRevisionCandidateIds }
    },
    meta: { overlay: 'saving' },
    onSuccess: ({ lastRecord: record, scheduleRevisionCandidateIds }) => {
      invalidateDailyRecordCaches(queryClient, targetDate)
      showToast(message)
      for (const category of categories) {
        checkMilestones?.(goalIdsByCategory[category], category)
      }
      generateScheduleRevisionForGoals(scheduleRevisionCandidateIds, targetDate)
      if (record && isAllCategoriesReported(presence, toCategoryReportedState(record))) {
        navigate(ROUTES.dashboard)
      }
    },
    onError: showApiError,
  })

  return { isPending: mutation.isPending, submit: () => mutation.mutate() }
}
