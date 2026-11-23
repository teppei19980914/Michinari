import { apiClient } from './client'
import type { QuizGenerateResult } from './quiz'
import type { components } from '../types/api.d.ts'

export type VocabDeck = components['schemas']['VocabDeckRead']
export type VocabCard = components['schemas']['VocabCardRead']
export type VocabCardType = components['schemas']['VocabCardType']
export type VocabImportPreview = components['schemas']['VocabImportPreviewRead']
export type VocabImportRowRead = components['schemas']['VocabImportRowRead']
export type VocabImportConfirmRow = components['schemas']['VocabImportConfirmRow']
export type VocabImportConfirmResult = components['schemas']['VocabImportConfirmRead']
export type VocabExport = components['schemas']['VocabExportRead']
export type VocabQuizSession = components['schemas']['VocabQuizSessionRead']
export type VocabQuizQuestion = components['schemas']['VocabQuizQuestionRead']
export type VocabAnswerResult = components['schemas']['VocabAnswerResultRead']
export type VocabQuizMode = components['schemas']['VocabAnswerRequest']['mode']
export type VocabTermSuggestion = components['schemas']['VocabTermSuggestionRead']
export type VocabTermSuggestionList = components['schemas']['VocabTermSuggestionListRead']
//: 出題開始時の「カードの種類」絞り込み（開発Todo_単語帳_v1.0 要件F F-U3）。
export type VocabCardTypeFilter = 'ALL' | 'TERM' | 'SITUATION'

/** 目標に紐づく単語帳の一覧（表示順）。 */
export function getVocabDecks(goalId: number): Promise<VocabDeck[]> {
  return apiClient.get<VocabDeck[]>(`/goals/${goalId}/vocab-decks`)
}

/** 単語帳を作成する（対象の目標が資格試験以外だと400が返る）。 */
export function createVocabDeck(
  goalId: number,
  payload: { name: string; description?: string | null },
): Promise<VocabDeck> {
  return apiClient.post<VocabDeck>(`/goals/${goalId}/vocab-decks`, payload)
}

export function reorderVocabDecks(goalId: number, orderedDeckIds: number[]): Promise<void> {
  return apiClient.put(`/goals/${goalId}/vocab-decks/order`, { ordered_deck_ids: orderedDeckIds })
}

export function getVocabDeck(deckId: number): Promise<VocabDeck> {
  return apiClient.get<VocabDeck>(`/vocab-decks/${deckId}`)
}

export function updateVocabDeck(
  deckId: number,
  payload: { name?: string; description?: string | null; use_in_ai?: boolean },
): Promise<VocabDeck> {
  return apiClient.patch<VocabDeck>(`/vocab-decks/${deckId}`, payload)
}

export function deleteVocabDeck(deckId: number): Promise<void> {
  return apiClient.delete(`/vocab-decks/${deckId}`)
}

/** カード一覧。`filter`・`sort`は画面の絞り込み・並び替えキー（省略時はALL・REGISTERED）。
 * `cardType`は種類の絞り込み（省略時はALL、開発Todo_単語帳_v1.0 要件F）。 */
export function getVocabCards(
  deckId: number,
  filter?: string,
  sort?: string,
  cardType?: VocabCardTypeFilter,
): Promise<VocabCard[]> {
  const params = new URLSearchParams()
  if (filter) params.set('filter', filter)
  if (sort) params.set('sort', sort)
  if (cardType) params.set('card_type', cardType)
  const query = params.toString() ? `?${params.toString()}` : ''
  return apiClient.get<VocabCard[]>(`/vocab-decks/${deckId}/cards${query}`)
}

export function createVocabCard(
  deckId: number,
  payload: {
    card_type?: VocabCardType
    term: string
    meaning: string
    aliases?: string | null
    note?: string | null
    situation_text?: string | null
    question_text?: string | null
  },
): Promise<VocabCard> {
  return apiClient.post<VocabCard>(`/vocab-decks/${deckId}/cards`, payload)
}

/** カードを更新する。`card_type`は更新できない（開発Todo_単語帳_v1.0 要件F F-D2、作成後
 * 不変）ため、このpayload型自体に項目を持たせない。 */
export function updateVocabCard(
  cardId: number,
  payload: {
    term?: string
    meaning?: string
    aliases?: string | null
    note?: string | null
    situation_text?: string | null
    question_text?: string | null
  },
): Promise<VocabCard> {
  return apiClient.patch<VocabCard>(`/vocab-cards/${cardId}`, payload)
}

export function checkVocabCard(cardId: number, isChecked: boolean): Promise<VocabCard> {
  return apiClient.patch<VocabCard>(`/vocab-cards/${cardId}/check`, { is_checked: isChecked })
}

export function deleteVocabCard(cardId: number): Promise<void> {
  return apiClient.delete(`/vocab-cards/${cardId}`)
}

/** 一括登録のプレビュー（確定前）。取り込む件数・エラー行・重複件数を返す。`cardType`省略時は
 * TERM（開発Todo_単語帳_v1.0 要件F F-U8）。 */
export function previewVocabImport(
  deckId: number,
  text: string,
  cardType: VocabCardType = 'TERM',
): Promise<VocabImportPreview> {
  return apiClient.post<VocabImportPreview>(`/vocab-decks/${deckId}/cards/import-preview`, {
    text,
    card_type: cardType,
  })
}

/** プレビューで確定した行をカードとして一括登録する。 */
export function confirmVocabImport(
  deckId: number,
  rows: VocabImportConfirmRow[],
  cardType: VocabCardType = 'TERM',
): Promise<VocabImportConfirmResult> {
  return apiClient.post<VocabImportConfirmResult>(`/vocab-decks/${deckId}/cards/import`, {
    rows,
    card_type: cardType,
  })
}

/** 単語帳を種類ごとにタブ区切りテキストへ書き出す（`cardType`省略時はTERM、F-U8）。 */
export function exportVocabDeck(
  deckId: number,
  cardType: VocabCardType = 'TERM',
): Promise<VocabExport> {
  return apiClient.get<VocabExport>(
    `/vocab-decks/${deckId}/export?${new URLSearchParams({ card_type: cardType }).toString()}`,
  )
}

/** 出題セッションを開始する（サーバーにセッション自体は保存されない）。`card_type`省略時は
 * ALL（開発Todo_単語帳_v1.0 要件F F-U3）。 */
export function startVocabQuizSession(
  deckId: number,
  payload: {
    mode: VocabQuizMode
    filter?: string
    order?: string
    question_count: number
    card_type?: VocabCardTypeFilter
  },
): Promise<VocabQuizSession> {
  return apiClient.post<VocabQuizSession>(`/vocab-decks/${deckId}/quiz-sessions`, payload)
}

/** 出題セッションを終えた直後に呼ぶ（開発Todo_単語帳_v1.0 要件E E-U3）。未お祝いの節目の
 * 取得は別途`listPendingCelebrations`（`api/milestones.ts`）で行う（GETに副作用を持たせない
 * 方針のため、本APIのレスポンスには節目を含めない）。 */
export function completeVocabQuizSession(deckId: number): Promise<void> {
  return apiClient.post(`/vocab-decks/${deckId}/quiz-sessions/complete`)
}

/** 解答を記録する。モードに応じて`self_judged_correct`／`answer_text`／`selected_card_id`のいずれかを渡す。 */
export function answerVocabCard(
  cardId: number,
  payload: {
    mode: VocabQuizMode
    self_judged_correct?: boolean | null
    answer_text?: string | null
    selected_card_id?: number | null
  },
): Promise<VocabAnswerResult> {
  return apiClient.post<VocabAnswerResult>(`/vocab-cards/${cardId}/answer`, payload)
}

/** 単語帳詳細の「今日の復習の問題を作る」ボタン（開発Todo_単語帳_v1.0 要件B）。
 * まだ問題を持たないカードの分だけを作る（既存の未出題分の削除は行わない）。 */
export function generateVocabDeckQuiz(deckId: number): Promise<QuizGenerateResult> {
  return apiClient.post<QuizGenerateResult>(`/vocab-decks/${deckId}/quiz/generate`)
}

/** 日次報告の確定成功後に呼ぶ（開発Todo_単語帳_v1.0 要件D D-U4）。AI未設定・単語帳が
 * 1つも無いときは呼ばないこと（呼び出し側の責務）。 */
export function generateVocabTermSuggestions(
  goalId: number,
  recordDate: string,
): Promise<VocabTermSuggestionList> {
  return apiClient.post<VocabTermSuggestionList>(`/goals/${goalId}/vocab-suggestions`, {
    record_date: recordDate,
  })
}

/** その日のPENDINGの提案一覧（record_dateは必須）。 */
export function getVocabTermSuggestions(
  goalId: number,
  recordDate: string,
): Promise<VocabTermSuggestionList> {
  const params = new URLSearchParams({ record_date: recordDate })
  return apiClient.get<VocabTermSuggestionList>(
    `/goals/${goalId}/vocab-suggestions?${params.toString()}`,
  )
}

/** 提案を採用し、単語帳へカードを追加する。 */
export function acceptVocabTermSuggestion(
  goalId: number,
  suggestionId: number,
  payload: { deck_id: number; term: string; meaning: string; aliases?: string | null },
): Promise<VocabCard> {
  return apiClient.post<VocabCard>(
    `/goals/${goalId}/vocab-suggestions/${suggestionId}/accept`,
    payload,
  )
}

/** 提案を見送る。 */
export function dismissVocabTermSuggestion(goalId: number, suggestionId: number): Promise<void> {
  return apiClient.post(`/goals/${goalId}/vocab-suggestions/${suggestionId}/dismiss`)
}
