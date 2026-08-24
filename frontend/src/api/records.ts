import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type DailyMessageRead = components['schemas']['DailyMessageRead']
export type TodayRead = components['schemas']['TodayRead']
export type DailyRecordRead = components['schemas']['DailyRecordRead']
export type StudyLogInput = components['schemas']['StudyLogInput']
export type ProgressRegisterRequest = components['schemas']['ProgressRegisterRequest']
export type FinalizeRequest = components['schemas']['FinalizeRequest']
export type ChatRequest = components['schemas']['ChatRequest']
export type ChatResponse = components['schemas']['ChatResponse']
export type QuotaItemRead = components['schemas']['QuotaItemRead']
export type CommentRead = components['schemas']['CommentRead']

/** 今日の一言を取得する（生成に時間がかかる場合があるため非同期・遅延表示とする）。 */
export function getDailyMessage(): Promise<DailyMessageRead> {
  return apiClient.get<DailyMessageRead>('/daily-message')
}

/** 論理的な本日を取得する（CLAUDE.md「クライアント側での論理日の判断」禁止のため、
 * 日付の前後比較が必要な画面はこれをサーバから取得して使う）。 */
export function getToday(): Promise<TodayRead> {
  return apiClient.get<TodayRead>('/records/today')
}

/** 指定日の日次記録を取得する（未入力の日も record_state=null の空構造で返る）。 */
export function getRecord(targetDate: string): Promise<DailyRecordRead> {
  return apiClient.get<DailyRecordRead>(`/records/${targetDate}`)
}

/** 指定日の教材別日次ノルマを取得する（SC-06/SC-07の実績入力行、仕様書6.5）。 */
export function getQuota(targetDate: string): Promise<QuotaItemRead[]> {
  return apiClient.get<QuotaItemRead[]>(`/records/${targetDate}/quota`)
}

/** 進捗のみ登録する（SC-07）。 */
export function registerProgress(
  targetDate: string,
  payload: ProgressRegisterRequest,
): Promise<DailyRecordRead> {
  return apiClient.post<DailyRecordRead>(`/records/${targetDate}/progress`, payload)
}

/** 報告を確定する（SC-06）。 */
export function finalizeRecord(
  targetDate: string,
  payload: FinalizeRequest,
): Promise<DailyRecordRead> {
  return apiClient.post<DailyRecordRead>(`/records/${targetDate}/finalize`, payload)
}

/** AI対話を1往復実行する（SC-06下段）。 */
export function sendChat(targetDate: string, payload: ChatRequest): Promise<ChatResponse> {
  return apiClient.post<ChatResponse>(`/records/${targetDate}/chat`, payload)
}

export function createComment(targetDate: string, body: string): Promise<CommentRead> {
  return apiClient.post<CommentRead>(`/records/${targetDate}/comments`, { body })
}

export function updateComment(commentId: number, body: string): Promise<CommentRead> {
  return apiClient.patch<CommentRead>(`/comments/${commentId}`, { body })
}

export function deleteComment(commentId: number): Promise<void> {
  return apiClient.delete<void>(`/comments/${commentId}`)
}
