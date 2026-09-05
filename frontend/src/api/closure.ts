import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type ExamResultRead = components['schemas']['ExamResultRead']
export type ExamResultCreate = components['schemas']['ExamResultCreate']
export type ExamResultUpdate = components['schemas']['ExamResultUpdate']
export type RetrospectiveRead = components['schemas']['RetrospectiveRead']
export type WorkReportRead = components['schemas']['WorkReportRead']
export type MonthlyReportUpdateRequest = components['schemas']['MonthlyReportUpdateRequest']
export type SemiannualReviewUpdateRequest = components['schemas']['SemiannualReviewUpdateRequest']

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

// --- 月次報告・半期評価（category=WORKの場合のみ、実装フェーズ分割計画書Phase22・23） ---

export function getMonthlyReport(goalId: number, period?: string): Promise<WorkReportRead | null> {
  const query = period ? `?period=${encodeURIComponent(period)}` : ''
  return apiClient.get<WorkReportRead | null>(`/goals/${goalId}/monthly-report${query}`)
}

export function generateMonthlyReport(
  goalId: number,
  period?: string,
  anonymize = false,
): Promise<WorkReportRead> {
  return apiClient.post<WorkReportRead>(`/goals/${goalId}/monthly-report`, { period, anonymize })
}

export function updateMonthlyReport(
  goalId: number,
  period: string,
  payload: MonthlyReportUpdateRequest,
): Promise<WorkReportRead> {
  return apiClient.patch<WorkReportRead>(
    `/goals/${goalId}/monthly-report?period=${encodeURIComponent(period)}`,
    payload,
  )
}

export function getSemiannualReview(
  goalId: number,
  period?: string,
): Promise<WorkReportRead | null> {
  const query = period ? `?period=${encodeURIComponent(period)}` : ''
  return apiClient.get<WorkReportRead | null>(`/goals/${goalId}/semiannual-review${query}`)
}

export function generateSemiannualReview(
  goalId: number,
  period?: string,
  anonymize = false,
): Promise<WorkReportRead> {
  return apiClient.post<WorkReportRead>(`/goals/${goalId}/semiannual-review`, { period, anonymize })
}

export function updateSemiannualReview(
  goalId: number,
  period: string,
  payload: SemiannualReviewUpdateRequest,
): Promise<WorkReportRead> {
  return apiClient.patch<WorkReportRead>(
    `/goals/${goalId}/semiannual-review?period=${encodeURIComponent(period)}`,
    payload,
  )
}
