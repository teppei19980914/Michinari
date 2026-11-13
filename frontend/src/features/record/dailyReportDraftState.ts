import { createContext, useContext, type SetStateAction } from 'react'
import type { ChatMessageRead } from '../../api/records'
import type { StudyLogFormValue } from './studyLogForm'
import type { ReadingLogFormValue } from './readingLogForm'
import type { WorkLogFormValue } from './workLogForm'
import type { DiaryFormValue } from './diaryForm'
import type { MoodValue } from './moodStamps'
import type { RecordInputMode } from './recordInputMode'

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
  /** カテゴリ別の入力方式（下記examMode等）を`quick_record.last_mode_*`から初期化
   * 済みか（useDailyReportDraft.useHydrateModeOnce）。recordDataのhydrateとは
   * 別のタイミング（設定取得）で届くため独立したフラグとする。カテゴリごとに独立させる
   * のは、利用者が1カテゴリだけ先に手動切替した場合、他カテゴリの設定からの初期化を
   * 妨げないようにするため（2026-11、useHydrateModeOnceとの競合を回避）。 */
  examModeHydrated: boolean
  readingModeHydrated: boolean
  workModeHydrated: boolean
  /** ひとこと記録モード（開発Todo「ひとこと記録」v1.0）の気分スタンプ。カテゴリ単位
   * （`daily_record_mood`がgoal非依存のため）で、通常モードではnullのまま。 */
  examMood: MoodValue | null
  readingMood: MoodValue | null
  workMood: MoodValue | null
  /** カテゴリ別の入力方式（通常／ひとこと記録、決定事項Q3）。 */
  examMode: RecordInputMode
  readingMode: RecordInputMode
  workMode: RecordInputMode
}

export const EMPTY_DRAFT_STATE: CategoryDraftState = {
  studyLogValues: {},
  readingLogValues: {},
  workLogValues: {},
  diaryValues: {},
  chatMessages: [],
  hydrated: false,
  examModeHydrated: false,
  readingModeHydrated: false,
  workModeHydrated: false,
  examMood: null,
  readingMood: null,
  workMood: null,
  examMode: 'NORMAL',
  readingMode: 'NORMAL',
  workMode: 'NORMAL',
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
