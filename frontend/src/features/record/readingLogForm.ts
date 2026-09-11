import {
  buildSlotMinutesPayload,
  initSlotMinutes,
  type SlotMinutesFormValue,
} from './slotMinutesForm'
import type { BookRead } from '../../api/goals'
import type { ReadingLogInput } from '../../api/records'
import type { components } from '../../types/api.d.ts'

type ReadingLogRead = components['schemas']['ReadingLogRead']

/** 想起入力欄の1書籍分の入力状態（文字列で保持し、送信直前に数値へ変換する。
 * studyLogForm.tsのStudyLogFormValueと同じ方針）。 */
export type ReadingLogFormValue = {
  recallBody: string
  /** 時間枠ごとの読書時間。読書もリソース配分の対象（要件定義書R-64）。 */
  slotMinutes: SlotMinutesFormValue
  /** 現在ページ（任意）。ページの入力欄はこれ1つだけとし、「読んだページ数」は
   * 持たない（仕様変更2026-09-11）。画面上の進捗率表示のためだけの値であり、
   * AIフィードバックの評価対象にはしない（要件定義書R-66・R-71）。 */
  currentPage: string
}

const EMPTY_VALUE: ReadingLogFormValue = {
  recallBody: '',
  slotMinutes: {},
  currentPage: '',
}

/** 想起入力欄の初期値を組み立てる。既存の想起記録（進捗のみ登録済からの継続・昇格）が
 * あれば、その値で上書きする（studyLogForm.initStudyLogFormValuesと同じ方針）。 */
export function initReadingLogFormValues(
  books: BookRead[],
  existingLogs: ReadingLogRead[],
): Record<number, ReadingLogFormValue> {
  const existingByBook = new Map(existingLogs.map((log) => [log.book_id, log]))
  const result: Record<number, ReadingLogFormValue> = {}

  for (const book of books) {
    const existing = existingByBook.get(book.id)
    if (!existing) {
      result[book.id] = { ...EMPTY_VALUE }
      continue
    }
    result[book.id] = {
      recallBody: existing.recall_body,
      slotMinutes: initSlotMinutes([], existing.slot_minutes),
      currentPage: existing.current_page === null ? '' : String(existing.current_page),
    }
  }
  return result
}

/** 想起本文が1件でも入力されているか（要件定義書R-65「想起本文は必須」の入力側チェック）。 */
export function hasAnyReadingLogInput(values: Record<number, ReadingLogFormValue>): boolean {
  return Object.values(values).some((v) => v.recallBody.trim() !== '')
}

/** 送信用ペイロードを組み立てる。想起本文が未入力の書籍（今日その本に触れていない）は
 * 送信対象から除外する（ReadingLogInput.recall_bodyは必須のため）。 */
export function buildReadingLogPayload(
  values: Record<number, ReadingLogFormValue>,
): ReadingLogInput[] {
  return Object.entries(values)
    .filter(([, value]) => value.recallBody.trim() !== '')
    .map(([bookId, value]) => ({
      book_id: Number(bookId),
      recall_body: value.recallBody,
      slot_minutes: buildSlotMinutesPayload(value.slotMinutes),
      current_page: value.currentPage.trim() === '' ? null : Number(value.currentPage),
    }))
}
