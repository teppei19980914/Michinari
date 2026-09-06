import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type Granularity = components['schemas']['Granularity']
export type QualityAnalyticsRead = components['schemas']['QualityAnalyticsRead']
export type ProgressAnalyticsRead = components['schemas']['ProgressAnalyticsRead']
export type ForecastAnalyticsRead = components['schemas']['ForecastAnalyticsRead']
export type SpeedAnalyticsRead = components['schemas']['SpeedAnalyticsRead']
export type GanttAnalyticsRead = components['schemas']['GanttAnalyticsRead']
export type GrowthDescriptionEntryRead = components['schemas']['GrowthDescriptionEntryRead']
export type ReadingLogEntryRead = components['schemas']['ReadingLogEntryRead']
export type WorkLogEntryRead = components['schemas']['WorkLogEntryRead']

export function getQualityAnalytics(
  goalId: number,
  granularity?: Granularity,
): Promise<QualityAnalyticsRead> {
  const query = granularity
    ? `?goal_id=${goalId}&granularity=${granularity}`
    : `?goal_id=${goalId}`
  return apiClient.get<QualityAnalyticsRead>(`/analytics/quality${query}`)
}

export function getProgressAnalytics(goalId: number): Promise<ProgressAnalyticsRead> {
  return apiClient.get<ProgressAnalyticsRead>(`/analytics/progress?goal_id=${goalId}`)
}

export function getForecastAnalytics(goalId: number): Promise<ForecastAnalyticsRead> {
  return apiClient.get<ForecastAnalyticsRead>(`/analytics/forecast?goal_id=${goalId}`)
}

export function getSpeedAnalytics(goalId: number): Promise<SpeedAnalyticsRead> {
  return apiClient.get<SpeedAnalyticsRead>(`/analytics/speed?goal_id=${goalId}`)
}

export function getGanttAnalytics(goalId: number): Promise<GanttAnalyticsRead> {
  return apiClient.get<GanttAnalyticsRead>(`/analytics/gantt?goal_id=${goalId}`)
}

export function getGrowthDescriptions(): Promise<GrowthDescriptionEntryRead[]> {
  return apiClient.get<GrowthDescriptionEntryRead[]>('/analytics/growth-descriptions')
}

export function getReadingLogAnalytics(goalId: number): Promise<ReadingLogEntryRead[]> {
  return apiClient.get<ReadingLogEntryRead[]>(`/analytics/reading-logs?goal_id=${goalId}`)
}

export function getWorkLogAnalytics(goalId: number): Promise<WorkLogEntryRead[]> {
  return apiClient.get<WorkLogEntryRead[]>(`/analytics/work-logs?goal_id=${goalId}`)
}
