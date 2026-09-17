import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
  type SetStateAction,
} from 'react'
import type { ChatMessageRead } from '../../api/records'
import type { StudyLogFormValue } from './studyLogForm'
import type { ReadingLogFormValue } from './readingLogForm'
import type { WorkLogFormValue } from './workLogForm'
import type { DiaryFormValue } from './diaryForm'

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

type DraftStoreContextValue = {
  getDraft: (key: string) => CategoryDraftState
  setDraft: (key: string, updater: (current: CategoryDraftState) => CategoryDraftState) => void
}

const DraftStoreContext = createContext<DraftStoreContextValue | null>(null)

/**
 * SC-06 日次報告／SC-07 進捗のみ登録の下書きを、ページコンポーネントのマウント状態に
 * 関わらずアプリ内で保持する（記録画面改善タスク2026-09-17）。
 *
 * 従来は各ページ内の`useState`だったため、別画面へ移動するとアンマウントで下書きが消えて
 * いた（確定前に画面を離脱すると入力内容が失われる、という課題）。ルータより上位
 * （App.tsxのLayout）へ本Providerを置き、キー（画面種別+日付、useDailyReportDraftの
 * storeKey）ごとに下書きを保持することで、ブラウザを閉じない限り同一セッション内で
 * 画面を戻っても復元できるようにする。
 *
 * ブラウザを閉じる・再読み込みすると下書きは失われてよい（サーバへの下書き保存はしない。
 * 日次記録の不変性の設計を守るため、CLAUDE.md）。そのためあえてlocalStorage等の永続化は
 * 行わず、Reactの状態としてのみ保持する。
 */
export function DailyReportDraftProvider({ children }: { children: ReactNode }) {
  const [drafts, setDrafts] = useState<Record<string, CategoryDraftState>>({})

  const getDraft = useCallback(
    (key: string): CategoryDraftState => drafts[key] ?? EMPTY_DRAFT_STATE,
    [drafts],
  )
  const setDraft = useCallback(
    (key: string, updater: (current: CategoryDraftState) => CategoryDraftState) => {
      setDrafts((current) => ({
        ...current,
        [key]: updater(current[key] ?? EMPTY_DRAFT_STATE),
      }))
    },
    [],
  )

  return (
    <DraftStoreContext.Provider value={{ getDraft, setDraft }}>
      {children}
    </DraftStoreContext.Provider>
  )
}

export function useDraftStore(): DraftStoreContextValue {
  const context = useContext(DraftStoreContext)
  if (!context) {
    throw new Error('useDraftStore must be used within a DailyReportDraftProvider')
  }
  return context
}
