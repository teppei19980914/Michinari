import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type RecapThemeSummary = components['schemas']['RecapThemeSummaryRead']
export type RecapThemeDetail = components['schemas']['RecapThemeDetailRead']

/** 目標の振り返りテーマ一覧（本文の更新日時の新しい順）。 */
export function listRecapThemes(goalId: number): Promise<RecapThemeSummary[]> {
  return apiClient.get<RecapThemeSummary[]>(`/goals/${goalId}/recap-themes`)
}

export function getRecapTheme(themeId: number): Promise<RecapThemeDetail> {
  return apiClient.get<RecapThemeDetail>(`/recap-themes/${themeId}`)
}

export function renameRecapTheme(themeId: number, name: string): Promise<RecapThemeDetail> {
  return apiClient.patch<RecapThemeDetail>(`/recap-themes/${themeId}`, { name })
}

/** sourceのテーマをtargetへ統合する（sourceは削除される）。 */
export function mergeRecapTheme(themeId: number, targetThemeId: number): Promise<RecapThemeDetail> {
  return apiClient.post<RecapThemeDetail>(`/recap-themes/${themeId}/merge`, {
    target_theme_id: targetThemeId,
  })
}

/** 紐付く報告の原文から本文を作り直す（AIを呼び出すため時間がかかる）。 */
export function rebuildRecapTheme(themeId: number): Promise<RecapThemeDetail> {
  return apiClient.post<RecapThemeDetail>(`/recap-themes/${themeId}/rebuild`)
}
