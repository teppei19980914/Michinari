/** 目標相談チャットの通信フック（S09で導入、S10で相談履歴のフックを追加）。
 * キャッシュキーは`constants/queryKeys.ts`に集約する。 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  askGoalConsultationQuestion,
  deleteGoalConsultationHistoryItem,
  getGoalConsultationHistory,
  getGoalConsultationLimits,
} from '../../api/goalConsultation'
import { QUERY_KEYS } from '../../constants/queryKeys'

/** 質問の上限文字数などの取得（タブを開いたときに一度だけ読む）。 */
export function useGoalConsultationLimits(goalId: number) {
  return useQuery({
    queryKey: QUERY_KEYS.goalConsultationLimits(goalId),
    queryFn: () => getGoalConsultationLimits(goalId),
    staleTime: Infinity,
  })
}

/** 質問を送る。回答は画面の履歴に積むため、キャッシュには残さない（1問1答）。送信成功時は
 * 相談履歴（永続化、S10）のキャッシュを無効化し、一覧に反映させる。 */
export function useAskGoalConsultationQuestion(goalId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (question: string) => askGoalConsultationQuestion(goalId, question),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.goalConsultationHistory(goalId) })
    },
  })
}

/** 相談履歴の一覧（S10、開発Todo v1.1 V7）。 */
export function useGoalConsultationHistory(goalId: number) {
  return useQuery({
    queryKey: QUERY_KEYS.goalConsultationHistory(goalId),
    queryFn: () => getGoalConsultationHistory(goalId),
  })
}

/** 相談履歴の削除（S10、開発Todo v1.1 V7）。 */
export function useDeleteGoalConsultationHistoryItem(goalId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (logId: number) => deleteGoalConsultationHistoryItem(goalId, logId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.goalConsultationHistory(goalId) })
    },
  })
}
