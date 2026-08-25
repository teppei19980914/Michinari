import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type ExamResultRead = components['schemas']['ExamResultRead']
export type ExamResultCreate = components['schemas']['ExamResultCreate']
export type ExamResultUpdate = components['schemas']['ExamResultUpdate']
export type RetrospectiveRead = components['schemas']['RetrospectiveRead']

export function registerExamResult(
  subjectId: number,
  payload: ExamResultCreate,
): Promise<ExamResultRead> {
  return apiClient.post<ExamResultRead>(`/subjects/${subjectId}/result`, payload)
}

export function updateExamResult(
  resultId: number,
  payload: ExamResultUpdate,
): Promise<ExamResultRead> {
  return apiClient.patch<ExamResultRead>(`/results/${resultId}`, payload)
}

export function getRetrospective(
  goalId: number,
  anonymized = false,
): Promise<RetrospectiveRead | null> {
  return apiClient.get<RetrospectiveRead | null>(
    `/goals/${goalId}/retrospective?anonymized=${anonymized}`,
  )
}

export function generateRetrospective(
  goalId: number,
  anonymize: boolean,
): Promise<RetrospectiveRead> {
  return apiClient.post<RetrospectiveRead>(`/goals/${goalId}/retrospective`, { anonymize })
}
