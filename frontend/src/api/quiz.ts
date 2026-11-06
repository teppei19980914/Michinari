import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type QuizQuestion = components['schemas']['QuizQuestionRead']
export type QuizAnswerResult = components['schemas']['QuizAnswerResultRead']
export type QuizGenerateResult = components['schemas']['QuizGenerateResultRead']

/** 今日出題すべき復習クイズ（間隔が来たもの、1日の上限まで）。 */
export function getTodayQuiz(): Promise<QuizQuestion[]> {
  return apiClient.get<QuizQuestion[]>('/quiz/today')
}

export function answerQuiz(questionId: number, choiceIndex: number): Promise<QuizAnswerResult> {
  return apiClient.post<QuizAnswerResult>(`/quiz/${questionId}/answer`, {
    choice_index: choiceIndex,
  })
}

/** テーマのクイズを作る・作り直す（未出題分のみ削除してから生成するため、既存の解答済み分は残る）。 */
export function generateThemeQuiz(themeId: number): Promise<QuizGenerateResult> {
  return apiClient.post<QuizGenerateResult>(`/themes/${themeId}/quiz/generate`)
}
