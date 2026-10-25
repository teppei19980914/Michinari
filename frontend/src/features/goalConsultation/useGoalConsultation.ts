/** 目標相談チャットの通信フック（S09で導入、S10で相談履歴のフックを追加、S11で会話の
 * フックを追加）。キャッシュキーは`constants/queryKeys.ts`に集約する。 */
import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { GoalConsultationConversation } from '../../api/goalConsultation'
import {
  askGoalConsultationQuestion,
  createGoalConsultationConversation,
  deleteGoalConsultationConversation,
  deleteGoalConsultationHistoryItem,
  getGoalConsultationConversations,
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

/** 質問を送る（会話継続、S11、開発Todo v1.2 W7）。回答は画面の履歴に積むため、キャッシュ
 * には残さない（1問1答として送るが、文脈はサーバ側で会話に積む）。送信成功時は
 * 相談履歴（永続化、S10）のキャッシュを無効化し、一覧に反映させる。 */
export function useAskGoalConsultationQuestion(goalId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ conversationId, question }: { conversationId: number; question: string }) =>
      askGoalConsultationQuestion(goalId, conversationId, question),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.goalConsultationHistory(goalId) })
    },
  })
}

/** 会話一覧（S11、開発Todo v1.2 W7）。 */
export function useGoalConsultationConversations(goalId: number) {
  return useQuery({
    queryKey: QUERY_KEYS.goalConsultationConversations(goalId),
    queryFn: () => getGoalConsultationConversations(goalId),
  })
}

/** 新しい会話の開始（S11、開発Todo v1.2 W7）。 */
export function useCreateGoalConsultationConversation(goalId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (title: string) => createGoalConsultationConversation(goalId, title),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.goalConsultationConversations(goalId),
      })
    },
  })
}

/** 会話の削除（S11、開発Todo v1.2 W7）。所属する相談履歴も連鎖削除されるため、
 * 相談履歴のキャッシュも無効化する。 */
export function useDeleteGoalConsultationConversation(goalId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (conversationId: number) =>
      deleteGoalConsultationConversation(goalId, conversationId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.goalConsultationConversations(goalId),
      })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.goalConsultationHistory(goalId) })
    },
  })
}

/** 会話の選択・新規開始・削除・自動作成をまとめたフック（S11、開発Todo v1.2 W7）。
 * 画面（`GoalConsultationTab`）はこのフックが返す`effectiveConversationId`だけを
 * 使えば、会話が1件も無い場合の自動作成・最新会話の既定選択を気にしなくてよい。
 *
 * 「最新会話を既定で選ぶ」はuseEffect内で同期的にsetStateせず、描画時に導出する
 * （React公式の「エフェクトを使わずレンダー中に導出する」指針、oxlint
 * react(set-state-in-effect)。`features/systemInfo/LogExportSection.tsx`と同じ方針）。
 * 「会話が1件も無ければ自動作成する」は外部システム（サーバ）への書き込みのため、
 * 効果として残す（setStateはmutateの非同期コールバック内でのみ行う）。 */
export function useActiveGoalConsultationConversation(goalId: number) {
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const autoCreateRequested = useRef(false)
  const conversations = useGoalConsultationConversations(goalId)
  const createConversation = useCreateGoalConsultationConversation(goalId)
  const deleteConversation = useDeleteGoalConsultationConversation(goalId)

  const list: GoalConsultationConversation[] = conversations.data ?? []
  const effectiveConversationId =
    selectedId ?? (list.length > 0 ? list[list.length - 1].id : null)

  useEffect(() => {
    if (selectedId !== null || conversations.data === undefined) return
    if (conversations.data.length > 0) return
    if (autoCreateRequested.current || createConversation.isPending) return
    autoCreateRequested.current = true
    createConversation.mutate('', { onSuccess: (conversation) => setSelectedId(conversation.id) })
  }, [selectedId, conversations.data, createConversation])

  function select(id: number) {
    setSelectedId(id)
  }

  function createNew() {
    createConversation.mutate('', { onSuccess: (conversation) => setSelectedId(conversation.id) })
  }

  function deleteActive() {
    if (effectiveConversationId === null) return
    deleteConversation.mutate(effectiveConversationId, {
      onSuccess: () => {
        setSelectedId(null)
        autoCreateRequested.current = false
      },
    })
  }

  return {
    conversations: list,
    effectiveConversationId,
    select,
    createNew,
    deleteActive,
    isBusy: conversations.isLoading || createConversation.isPending || deleteConversation.isPending,
  }
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
