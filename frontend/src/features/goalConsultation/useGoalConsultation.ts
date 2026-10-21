/** 目標相談チャットの通信フック（S09）。キャッシュキーは`constants/queryKeys.ts`に集約する。 */
import { useMutation, useQuery } from '@tanstack/react-query'
import { askGoalConsultationQuestion, getGoalConsultationLimits } from '../../api/goalConsultation'
import { QUERY_KEYS } from '../../constants/queryKeys'

/** 質問の上限文字数などの取得（タブを開いたときに一度だけ読む）。 */
export function useGoalConsultationLimits(goalId: number) {
  return useQuery({
    queryKey: QUERY_KEYS.goalConsultationLimits(goalId),
    queryFn: () => getGoalConsultationLimits(goalId),
    staleTime: Infinity,
  })
}

/** 質問を送る。回答は画面の履歴に積むため、キャッシュには残さない（1問1答）。 */
export function useAskGoalConsultationQuestion(goalId: number) {
  return useMutation({
    mutationFn: (question: string) => askGoalConsultationQuestion(goalId, question),
  })
}
