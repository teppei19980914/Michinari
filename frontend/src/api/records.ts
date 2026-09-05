import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type DailyMessageRead = components['schemas']['DailyMessageRead']
export type TodayRead = components['schemas']['TodayRead']
export type DailyRecordRead = components['schemas']['DailyRecordRead']
export type StudyLogInput = components['schemas']['StudyLogInput']
export type ProgressRegisterRequest = components['schemas']['ProgressRegisterRequest']
export type FinalizeRequest = components['schemas']['FinalizeRequest']
export type ReadingFinalizeRequest = components['schemas']['ReadingFinalizeRequest']
export type WorkFinalizeRequest = components['schemas']['WorkFinalizeRequest']
export type ChatRequest = components['schemas']['ChatRequest']
export type ChatResponse = components['schemas']['ChatResponse']
export type ReadingChatRequest = components['schemas']['ReadingChatRequest']
export type QuotaItemRead = components['schemas']['QuotaItemRead']
export type CommentRead = components['schemas']['CommentRead']
export type ReadingLogInput = components['schemas']['ReadingLogInput']
export type ReadingLogRead = components['schemas']['ReadingLogRead']
export type WorkChatRequest = components['schemas']['WorkChatRequest']
export type WorkLogInput = components['schemas']['WorkLogInput']
export type WorkLogRead = components['schemas']['WorkLogRead']
export type ChatMessageRead = components['schemas']['ChatMessageRead']
export type DiaryEntryInput = components['schemas']['DiaryEntryInput']
export type DiaryEntryRead = components['schemas']['DiaryEntryRead']

/** 今日の一言を目標ごとに取得する（生成に時間がかかる場合があるため非同期・遅延表示
 * とする）。ACTIVEな目標が無い日はgoal_id=NULLの1件が返る（未決事項L-04）。 */
export function getDailyMessage(): Promise<DailyMessageRead[]> {
  return apiClient.get<DailyMessageRead[]>('/daily-message')
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

/** 資格勉強（EXAM）の報告を確定する（SC-06）。読書・仕事の確定状態には影響しない
 * （仕様変更2026-09-05: カテゴリごとに独立して確定できるようにするため）。 */
export function finalizeRecord(
  targetDate: string,
  payload: FinalizeRequest,
): Promise<DailyRecordRead> {
  return apiClient.post<DailyRecordRead>(`/records/${targetDate}/finalize`, payload)
}

/** 読書の報告を確定する（SC-06）。資格勉強・仕事の確定状態には影響しない
 * （既存の/chat・/reading-chat・/work-chatと同じカテゴリ別命名規則）。 */
export function finalizeReadingRecord(
  targetDate: string,
  payload: ReadingFinalizeRequest,
): Promise<DailyRecordRead> {
  return apiClient.post<DailyRecordRead>(`/records/${targetDate}/reading-finalize`, payload)
}

/** 仕事の報告を確定する（SC-06）。資格勉強・読書の確定状態には影響しない。 */
export function finalizeWorkRecord(
  targetDate: string,
  payload: WorkFinalizeRequest,
): Promise<DailyRecordRead> {
  return apiClient.post<DailyRecordRead>(`/records/${targetDate}/work-finalize`, payload)
}

/** AI対話を1往復実行する（SC-06下段、資格試験）。 */
export function sendChat(targetDate: string, payload: ChatRequest): Promise<ChatResponse> {
  return apiClient.post<ChatResponse>(`/records/${targetDate}/chat`, payload)
}

/** 読書のAI対話を1往復実行する（SC-06下段、読書。資格試験の/chatとは別の会話・
 * プロンプトとして分離する、データ構造編6.2「AI対話エンドポイントの分離について」）。 */
export function sendReadingChat(
  targetDate: string,
  payload: ReadingChatRequest,
): Promise<ChatResponse> {
  return apiClient.post<ChatResponse>(`/records/${targetDate}/reading-chat`, payload)
}

/** 仕事のAI対話を1往復実行する（SC-06下段、仕事。資格試験の/chat・読書の/reading-chatとは
 * 別の会話・プロンプトとして分離する、データ構造編6.2）。 */
export function sendWorkChat(targetDate: string, payload: WorkChatRequest): Promise<ChatResponse> {
  return apiClient.post<ChatResponse>(`/records/${targetDate}/work-chat`, payload)
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
