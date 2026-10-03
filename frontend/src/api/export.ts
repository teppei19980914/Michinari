import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type KnowledgeExportRequest = components['schemas']['KnowledgeExportRequest']
export type KnowledgeExportContentRead = components['schemas']['KnowledgeExportContentRead']
export type KnowledgeExportResultRead = components['schemas']['KnowledgeExportResultRead']
export type KnowledgeExportProgressRead = components['schemas']['KnowledgeExportProgressRead']
export type ExportSelection = Omit<KnowledgeExportRequest, 'anonymize'>

export function previewKnowledgeExport(
  goalId: number,
  selection: ExportSelection,
  anonymized: boolean,
): Promise<KnowledgeExportContentRead> {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(selection)) {
    params.set(key, String(value))
  }
  params.set('anonymized', String(anonymized))
  return apiClient.get<KnowledgeExportContentRead>(
    `/goals/${goalId}/knowledge-export/preview?${params.toString()}`,
  )
}

export function executeKnowledgeExport(
  goalId: number,
  payload: KnowledgeExportRequest,
): Promise<KnowledgeExportResultRead> {
  return apiClient.post<KnowledgeExportResultRead>(`/goals/${goalId}/knowledge-export`, payload)
}

/** 匿名化エクスポート実行中の進捗をポーリング取得する（実装フェーズ分割計画書Phase10
 * 注意点「進捗を表示すること」）。 */
export function getKnowledgeExportProgress(goalId: number): Promise<KnowledgeExportProgressRead> {
  return apiClient.get<KnowledgeExportProgressRead>(`/goals/${goalId}/knowledge-export/progress`)
}
