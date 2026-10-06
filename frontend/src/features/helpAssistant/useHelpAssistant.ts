/** ヘルプAIアシスタントの通信フック（Phase43）。キャッシュキーは `constants/queryKeys.ts` に集約する。 */
import { useMutation, useQuery } from '@tanstack/react-query'
import { askHelpQuestion, getHelpAssistantLimits } from '../../api/helpAssistant'
import { QUERY_KEYS } from '../../constants/queryKeys'

/** 質問の上限文字数などの取得（ドロワーを開いたときに一度だけ読む）。 */
export function useHelpAssistantLimits() {
  return useQuery({
    queryKey: QUERY_KEYS.helpAssistantLimits(),
    queryFn: getHelpAssistantLimits,
    staleTime: Infinity,
  })
}

/** 質問を送る。回答は画面の履歴に積むため、キャッシュには残さない（1問1答）。 */
export function useAskHelpQuestion() {
  return useMutation({
    mutationFn: (question: string) => askHelpQuestion(question),
  })
}
