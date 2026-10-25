import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type GoalConsultationAnswerStatus = components['schemas']['GoalConsultationAnswerStatus']
export type GoalConsultationAnswer = components['schemas']['GoalConsultationAnswerRead']
export type GoalConsultationLimits = components['schemas']['GoalConsultationLimitsRead']
export type GoalConsultationHistoryItem = components['schemas']['GoalConsultationHistoryItemRead']
export type GoalConsultationConversation = components['schemas']['GoalConsultationConversationRead']

/** 質問に、目標の記録に基づいて答える（S09、要件定義書R-104。S10で読書・仕事へ展開、S11で
 * 会話継続に対応し`conversationId`を必須化、開発Todo v1.2 W7）。 */
export function askGoalConsultationQuestion(
  goalId: number,
  conversationId: number,
  question: string,
): Promise<GoalConsultationAnswer> {
  return apiClient.post<GoalConsultationAnswer>(`/goals/${goalId}/consultation/questions`, {
    conversation_id: conversationId,
    question,
  })
}

/** 新しい会話を開始する（S11、開発Todo v1.2 W7、確認事項③）。 */
export function createGoalConsultationConversation(
  goalId: number,
  title: string,
): Promise<GoalConsultationConversation> {
  return apiClient.post<GoalConsultationConversation>(
    `/goals/${goalId}/consultation/conversations`,
    { title },
  )
}

/** 会話一覧を取得する（S11、開発Todo v1.2 W7）。 */
export function getGoalConsultationConversations(
  goalId: number,
): Promise<GoalConsultationConversation[]> {
  return apiClient.get<GoalConsultationConversation[]>(
    `/goals/${goalId}/consultation/conversations`,
  )
}

/** 会話を削除する（所属する相談履歴も連鎖削除される、S11、開発Todo v1.2 W7）。 */
export function deleteGoalConsultationConversation(
  goalId: number,
  conversationId: number,
): Promise<void> {
  return apiClient.delete<void>(`/goals/${goalId}/consultation/conversations/${conversationId}`)
}

/** 質問の上限文字数などの、画面が使う上限を取得する。 */
export function getGoalConsultationLimits(goalId: number): Promise<GoalConsultationLimits> {
  return apiClient.get<GoalConsultationLimits>(`/goals/${goalId}/consultation/limits`)
}

/** 相談履歴の一覧を取得する（S10、開発Todo v1.1 V7）。 */
export function getGoalConsultationHistory(
  goalId: number,
): Promise<GoalConsultationHistoryItem[]> {
  return apiClient.get<GoalConsultationHistoryItem[]>(`/goals/${goalId}/consultation/history`)
}

/** 相談履歴を1件削除する（S10、開発Todo v1.1 V7）。 */
export function deleteGoalConsultationHistoryItem(goalId: number, logId: number): Promise<void> {
  return apiClient.delete<void>(`/goals/${goalId}/consultation/history/${logId}`)
}
