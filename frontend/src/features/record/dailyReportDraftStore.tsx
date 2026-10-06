import { useCallback, useState, type ReactNode } from 'react'
import {
  DraftStoreContext,
  EMPTY_DRAFT_STATE,
  type CategoryDraftState,
} from './dailyReportDraftState'

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
