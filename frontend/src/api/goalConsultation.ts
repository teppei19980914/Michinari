import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type GoalConsultationAnswerStatus = components['schemas']['GoalConsultationAnswerStatus']
export type GoalConsultationAnswer = components['schemas']['GoalConsultationAnswerRead']
export type GoalConsultationLimits = components['schemas']['GoalConsultationLimitsRead']

/** 質問に、目標の記録に基づいて答える（S09、要件定義書R-104）。 */
export function askGoalConsultationQuestion(
  goalId: number,
  question: string,
): Promise<GoalConsultationAnswer> {
  return apiClient.post<GoalConsultationAnswer>(`/goals/${goalId}/consultation/questions`, {
    question,
  })
}

/** 質問の上限文字数などの、画面が使う上限を取得する。 */
export function getGoalConsultationLimits(goalId: number): Promise<GoalConsultationLimits> {
  return apiClient.get<GoalConsultationLimits>(`/goals/${goalId}/consultation/limits`)
}
