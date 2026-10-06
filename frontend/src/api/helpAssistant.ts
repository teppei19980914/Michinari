import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type HelpAnswerStatus = components['schemas']['HelpAnswerStatus']
export type HelpAssistantAnswer = components['schemas']['HelpAssistantAnswerRead']
export type HelpAssistantLimits = components['schemas']['HelpAssistantLimitsRead']

/** 質問に、ヘルプ本文に基づいて答える（Phase43、仕様書6.18）。 */
export function askHelpQuestion(question: string): Promise<HelpAssistantAnswer> {
  return apiClient.post<HelpAssistantAnswer>('/help-assistant/questions', { question })
}

/** 質問の上限文字数などの、画面が使う上限を取得する。 */
export function getHelpAssistantLimits(): Promise<HelpAssistantLimits> {
  return apiClient.get<HelpAssistantLimits>('/help-assistant/limits')
}
