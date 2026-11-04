import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type MilestoneAchievement = components['schemas']['MilestoneAchievementRead']
export type MilestoneType = components['schemas']['MilestoneType']

/** 目標の節目履歴（お祝い済み・未済問わず、到達の新しい順）。分析画面の一覧表示用。 */
export function listMilestones(goalId: number): Promise<MilestoneAchievement[]> {
  return apiClient.get<MilestoneAchievement[]>(`/goals/${goalId}/milestones`)
}

/** 未お祝いの節目（到達順）。記録確定の直後にお祝いモーダルのキューへ積むために呼ぶ。 */
export function listPendingCelebrations(goalId: number): Promise<MilestoneAchievement[]> {
  return apiClient.get<MilestoneAchievement[]>(`/goals/${goalId}/milestones/pending-celebrations`)
}

/** お祝いモーダルを閉じたときに呼び、お祝い済みとして記録する。 */
export function celebrateMilestone(
  goalId: number,
  milestoneId: number,
): Promise<MilestoneAchievement> {
  return apiClient.post<MilestoneAchievement>(
    `/goals/${goalId}/milestones/${milestoneId}/celebrate`,
  )
}
