import { t } from '../../locales/t'
import { combineQaAnswers, hasAnyQaInput } from './qaCombine'
import {
  buildSlotMinutesPayload,
  initSlotMinutes,
  type SlotMinutesFormValue,
} from './slotMinutesForm'
import type { BookRead } from '../../api/goals'
import type { ReadingLogInput } from '../../api/records'
import type { components } from '../../types/api.d.ts'

type ReadingLogRead = components['schemas']['ReadingLogRead']

/**
 * 想起入力欄の1書籍分の入力状態（文字列で保持し、送信直前に数値へ変換する。
 * studyLogForm.tsのStudyLogFormValueと同じ方針）。
 *
 * 想起本文は質問への回答形式へ再構成した（仕様書6.5改、記録画面改善タスク2026-09-17）。
 * questionAnswersが質問ごとの回答、freeTextが「自由に書く」欄（旧・想起欄）に対応する。
 * 送信する想起本文（recall_body）はこの2つをcombineRecallBodyで都度結合して求め、
 * 保存形式・APIは変更しない。
 */
export type ReadingLogFormValue = {
  questionAnswers: string[]
  freeText: string
  /** 時間枠ごとの読書時間。読書もリソース配分の対象（要件定義書R-64）。 */
  slotMinutes: SlotMinutesFormValue
  /** 現在ページ（任意）。ページの入力欄はこれ1つだけとし、「読んだページ数」は
   * 持たない（仕様変更2026-09-11）。画面上の進捗率表示のためだけの値であり、
   * AIフィードバックの評価対象にはしない（要件定義書R-66・R-71）。 */
  currentPage: string
}

/** 読書の想起質問（仕様書6.5改）。固定2問。 */
export function getReadingLogQuestions(): string[] {
  return [t('dailyReport.readingLog.question1'), t('dailyReport.readingLog.question2')]
}

const EMPTY_VALUE: ReadingLogFormValue = {
  questionAnswers: ['', ''],
  freeText: '',
  slotMinutes: {},
  currentPage: '',
}

/** 質問への回答と「自由に書く」欄を結合し、送信する想起本文（recall_body）を求める。 */
export function combineRecallBody(value: ReadingLogFormValue): string {
  return combineQaAnswers(getReadingLogQuestions(), value.questionAnswers, value.freeText)
}

/**
 * 想起入力欄の初期値を組み立てる。既存の想起記録（進捗のみ登録済からの継続・昇格）が
 * あれば、その値で上書きする（studyLogForm.initStudyLogFormValuesと同じ方針）。
 *
 * 既存の想起本文は「自由に書く」欄（freeText）へそのまま引き継ぐ（diaryForm.
 * initDiaryFormValuesと同じ理由。質問への回答への逆変換はしない）。
 */
export function initReadingLogFormValues(
  books: BookRead[],
  existingLogs: ReadingLogRead[],
): Record<number, ReadingLogFormValue> {
  const existingByBook = new Map(existingLogs.map((log) => [log.book_id, log]))
  const result: Record<number, ReadingLogFormValue> = {}

  for (const book of books) {
    const existing = existingByBook.get(book.id)
    if (!existing) {
      result[book.id] = { ...EMPTY_VALUE, questionAnswers: [...EMPTY_VALUE.questionAnswers] }
      continue
    }
    result[book.id] = {
      questionAnswers: ['', ''],
      freeText: existing.recall_body,
      slotMinutes: initSlotMinutes([], existing.slot_minutes),
      currentPage: existing.current_page === null ? '' : String(existing.current_page),
    }
  }
  return result
}

/** 想起欄（質問への回答・自由記述）に1件でも入力されているか（要件定義書R-65）。
 * R-65の「想起本文は必須」は、いずれかの回答欄に1件以上の入力があることを指す
 * （仕様変更2026-09-17。全ての回答欄は任意とし、1つだけ書いても確定できる）。 */
export function hasAnyReadingLogInput(values: Record<number, ReadingLogFormValue>): boolean {
  return Object.values(values).some((v) => hasAnyQaInput(v.questionAnswers, v.freeText))
}

/** 送信用ペイロードを組み立てる。想起本文が未入力の書籍（今日その本に触れていない）は
 * 送信対象から除外する（ReadingLogInput.recall_bodyは必須のため）。 */
export function buildReadingLogPayload(
  values: Record<number, ReadingLogFormValue>,
): ReadingLogInput[] {
  return Object.entries(values)
    .map(([bookId, value]) => ({
      book_id: Number(bookId),
      recall_body: combineRecallBody(value),
      slot_minutes: buildSlotMinutesPayload(value.slotMinutes),
      current_page: value.currentPage.trim() === '' ? null : Number(value.currentPage),
    }))
    .filter((entry) => entry.recall_body !== '')
}
