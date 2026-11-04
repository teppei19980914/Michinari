import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useToast } from '../../components/toastContext'
import { ROUTES } from '../../constants/routes'
import {
  finalizeReadingRecord,
  finalizeRecord,
  finalizeWorkRecord,
  type DailyRecordRead,
} from '../../api/records'
import type { GoalCategory } from '../../api/goals'
import { invalidateDailyRecordCaches } from './invalidateDailyRecordCaches'
import {
  isAllCategoriesReported,
  toCategoryReportedState,
  type CategoryPresence,
} from './categoryCompletion'
import type { ZeroRecordCategory } from './resolveZeroRecordCategories'

/** カテゴリ別の「空の実績で確定する」呼び出し（記録画面改善タスク2026-09-17）。
 * finalize系のAPIは0件の配列を渡しても正常に完了し、そのカテゴリの状態を直接REPORTEDに
 * できる（record_service.pyのfinalize_record等はregister_progressと異なり「1件以上」を
 * 要求しない）。これを利用し、下書きの内容に関わらず常に空配列で確定する。 */
const FINALIZE_AS_ZERO: Record<
  ZeroRecordCategory,
  (targetDate: string) => Promise<DailyRecordRead>
> = {
  EXAM: (targetDate) => finalizeRecord(targetDate, { study_logs: [], diary_entries: [] }),
  READING: (targetDate) => finalizeReadingRecord(targetDate, { reading_logs: [] }),
  WORK: (targetDate) => finalizeWorkRecord(targetDate, { work_logs: [] }),
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
}: ZeroRecordActionOptions): ZeroRecordAction {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showToast, showApiError } = useToast()

  const mutation = useMutation({
    mutationFn: async () => {
      let lastRecord: DailyRecordRead | undefined
      for (const category of categories) {
        lastRecord = await FINALIZE_AS_ZERO[category](targetDate)
      }
      return lastRecord
    },
    meta: { overlay: 'saving' },
    onSuccess: (record) => {
      invalidateDailyRecordCaches(queryClient, targetDate)
      showToast(message)
      for (const category of categories) {
        checkMilestones?.(goalIdsByCategory[category], category)
      }
      if (record && isAllCategoriesReported(presence, toCategoryReportedState(record))) {
        navigate(ROUTES.dashboard)
      }
    },
    onError: showApiError,
  })

  return { isPending: mutation.isPending, submit: () => mutation.mutate() }
}
