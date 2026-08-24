import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type DailyMessageRead = components['schemas']['DailyMessageRead']
export type TodayRead = components['schemas']['TodayRead']

/** 今日の一言を取得する（生成に時間がかかる場合があるため非同期・遅延表示とする）。 */
export function getDailyMessage(): Promise<DailyMessageRead> {
  return apiClient.get<DailyMessageRead>('/daily-message')
}

/** 論理的な本日を取得する（CLAUDE.md「クライアント側での論理日の判断」禁止のため、
 * 日付の前後比較が必要な画面はこれをサーバから取得して使う）。 */
export function getToday(): Promise<TodayRead> {
  return apiClient.get<TodayRead>('/records/today')
}
