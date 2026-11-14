import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type SummaryCardRead = components['schemas']['SummaryCardRead']
export type SummaryCardMilestoneRead = components['schemas']['SummaryCardMilestoneRead']
export type SummaryCardSentenceRead = components['schemas']['SummaryCardSentenceRead']

/** ふりかえりまとめ・共有カードの集計取得（AI呼び出しなし、データ構造編6.API設計）。 */
export function getSummaryCard(
  goalId: number,
  dateFrom: string,
  dateTo: string,
): Promise<SummaryCardRead> {
  return apiClient.get<SummaryCardRead>(
    `/goals/${goalId}/summary-card?date_from=${dateFrom}&date_to=${dateTo}`,
  )
}

/** AIが選んだ一文の生成（利用者の明示操作時のみ呼ぶ。自動生成しない、§0 U4）。 */
export function generateSummaryCardSentence(
  goalId: number,
  dateFrom: string,
  dateTo: string,
): Promise<SummaryCardSentenceRead> {
  return apiClient.post<SummaryCardSentenceRead>(
    `/goals/${goalId}/summary-card/sentence?date_from=${dateFrom}&date_to=${dateTo}`,
  )
}
