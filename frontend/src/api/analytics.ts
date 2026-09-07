import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type Granularity = components['schemas']['Granularity']
export type QualityAnalyticsRead = components['schemas']['QualityAnalyticsRead']
export type ProgressAnalyticsRead = components['schemas']['ProgressAnalyticsRead']
export type ForecastAnalyticsRead = components['schemas']['ForecastAnalyticsRead']
export type SpeedAnalyticsRead = components['schemas']['SpeedAnalyticsRead']
export type GanttAnalyticsRead = components['schemas']['GanttAnalyticsRead']
export type GrowthDescriptionEntryRead = components['schemas']['GrowthDescriptionEntryRead']
export type GrowthDescriptionAssignRequest = components['schemas']['GrowthDescriptionAssignRequest']
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

/** 成長記述タブ（仕様書6.8、ANL-07）。Phase26で目標単位に分離した。goal_idで指定した
 * 目標宛てのメッセージに加え、同カテゴリの未割り当て（goal_id=NULLの移行前レガシー）も
 * 併せて返す（analytics_service.list_growth_descriptionsのdocstring参照）。 */
export function getGrowthDescriptions(goalId: number): Promise<GrowthDescriptionEntryRead[]> {
  return apiClient.get<GrowthDescriptionEntryRead[]>(`/analytics/growth-descriptions?goal_id=${goalId}`)
}

/** 未割り当ての成長記述（goal_id=NULL）に目標を手動で割り当てる（Phase26）。 */
export function assignGrowthDescriptionGoal(
  messageId: number,
  payload: GrowthDescriptionAssignRequest,
): Promise<GrowthDescriptionEntryRead> {
  return apiClient.patch<GrowthDescriptionEntryRead>(
    `/analytics/growth-descriptions/${messageId}`,
    payload,
  )
}

export function getReadingLogAnalytics(goalId: number): Promise<ReadingLogEntryRead[]> {
  return apiClient.get<ReadingLogEntryRead[]>(`/analytics/reading-logs?goal_id=${goalId}`)
}

export function getWorkLogAnalytics(goalId: number): Promise<WorkLogEntryRead[]> {
  return apiClient.get<WorkLogEntryRead[]>(`/analytics/work-logs?goal_id=${goalId}`)
}
