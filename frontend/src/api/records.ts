import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type DailyMessageRead = components['schemas']['DailyMessageRead']

/** 今日の一言を取得する（生成に時間がかかる場合があるため非同期・遅延表示とする）。 */
export function getDailyMessage(): Promise<DailyMessageRead> {
  return apiClient.get<DailyMessageRead>('/daily-message')
}
