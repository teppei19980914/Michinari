import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  decideScheduleRevisionProposal,
  generateScheduleRevisionProposal,
  type ScheduleRevisionDecisionInput,
} from '../../api/schedule'
import { QUERY_KEYS } from '../../constants/queryKeys'

/**
 * スケジュールタブの「AIに修正案を依頼」ボタンと、承認・却下・確認済みパネルが使う
 * ミューテーション（開発Todo_スケジュール・ガントチャート_v1.1 13.7・13.8、単位5）。
 *
 * いずれも成功時はスケジュールの取得クエリを無効化し、`GET /goals/{goal_id}/schedule`が
 * 埋め込む最新の修正案・revisionを再取得させる（承認でrevisionが変わるため）。
 */
export function useScheduleRevision(goalId: number) {
  const queryClient = useQueryClient()

  function invalidateSchedule() {
    return queryClient.invalidateQueries({ queryKey: QUERY_KEYS.schedule(goalId) })
  }

  const requestMutation = useMutation({
    mutationFn: () => generateScheduleRevisionProposal(goalId, { trigger: 'MANUAL' }),
    onSuccess: invalidateSchedule,
  })

  const decideMutation = useMutation({
    mutationFn: (variables: { proposalId: number; decisions: ScheduleRevisionDecisionInput[] }) =>
      decideScheduleRevisionProposal(goalId, variables.proposalId, {
        decisions: variables.decisions,
      }),
    onSuccess: invalidateSchedule,
  })

  return {
    requestRevision: () => requestMutation.mutate(),
    isRequesting: requestMutation.isPending,
    requestError: requestMutation.error,
    decide: (proposalId: number, decisions: ScheduleRevisionDecisionInput[]) =>
      decideMutation.mutate({ proposalId, decisions }),
    isDeciding: decideMutation.isPending,
    decideError: decideMutation.error,
  }
}
