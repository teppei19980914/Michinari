import { createContext, useContext, type SetStateAction } from 'react'
import type { ChatMessageRead } from '../../api/records'
import type { StudyLogFormValue } from './studyLogForm'
import type { ReadingLogFormValue } from './readingLogForm'
import type { WorkLogFormValue } from './workLogForm'
import type { DiaryFormValue } from './diaryForm'

/** 日次報告の下書きの状態・文脈・フック（dailyReportDraftStore.tsx の Provider から使う）。
 * コンポーネントと分けてあるのは、React Fast Refresh が「コンポーネントだけを export する
 * ファイル」を要求するため。 */
/** 1画面・1日分の下書き（実績入力・日記・AI対話履歴）。従来 useDailyReportDraft が
 * ローカル state として持っていたものと同じ形。 */
export type CategoryDraftState = {
  studyLogValues: Record<number, StudyLogFormValue>
  readingLogValues: Record<number, ReadingLogFormValue>
  workLogValues: Record<number, WorkLogFormValue>
  diaryValues: Record<number, DiaryFormValue>
  chatMessages: ChatMessageRead[]
  /** 取得完了後の初期化（hydrate）が済んだか。画面を再訪問した際に、残っている下書きへ
   * 初期値を上書きしないための判定に使う（旧hydratedRefのグローバル版）。 */
  hydrated: boolean
}

export const EMPTY_DRAFT_STATE: CategoryDraftState = {
  studyLogValues: {},
  readingLogValues: {},
  workLogValues: {},
  diaryValues: {},
  chatMessages: [],
  hydrated: false,
}

/** Reactの`useState`と同じ`値 or 更新関数`の両方を受け付ける（setChatMessagesは直接値、
 * patchFormValue経由の各setterは更新関数で呼ばれるため両対応が要る）。 */
export function applySetStateAction<T>(action: SetStateAction<T>, current: T): T {
  return typeof action === 'function' ? (action as (prev: T) => T)(current) : action
}

export type DraftStoreContextValue = {
  getDraft: (key: string) => CategoryDraftState
  setDraft: (key: string, updater: (current: CategoryDraftState) => CategoryDraftState) => void
}

export const DraftStoreContext = createContext<DraftStoreContextValue | null>(null)

export function useDraftStore(): DraftStoreContextValue {
  const context = useContext(DraftStoreContext)
  if (!context) {
    throw new Error('useDraftStore must be used within a DailyReportDraftProvider')
  }
  return context
}
