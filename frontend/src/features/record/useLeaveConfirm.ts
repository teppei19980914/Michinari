import { useRef } from 'react'
import { useBlocker, type Blocker } from 'react-router-dom'
import { useUnsavedChangesWarning } from './useUnsavedChangesWarning'

export type LeaveConfirm = {
  /** 離脱をブロック中かどうかを持つ。確認ダイアログの表示に使う（LeaveConfirmModal）。 */
  blocker: Blocker
  /** 次の遷移を警告なしで通す。確定成功による遷移の直前に呼ぶ。 */
  allowNextNavigation: () => void
}

/**
 * 確定前に画面を離脱しようとした場合の警告をまとめる（仕様書6.5「確定前に画面を離脱した場合、
 * 入力内容は保存されない旨を警告する」）。
 *
 * ブラウザレベルの離脱（タブを閉じる・再読み込み・アドレスバーへの直接入力）と、アプリ内遷移
 * （GlobalNavのリンククリック、ブラウザの戻る/進む等）の両方を対象にする。後者はブラウザ離脱に
 * 限定されない要件のため、data router化してuseBlockerを使う（App.tsx参照）。
 *
 * allowNextNavigationは、確定成功によるnavigate()まで誤ってブロックしないためのもの。
 * レンダー中にrefを読むとReactのルール違反になるため、判定関数の「呼び出し時」にのみ参照する
 * （この関数はナビゲーション試行のタイミングでルータから呼ばれるため、レンダー中の読み取りには
 * ならない）。呼び出し側もnavigate()の直前に同期的に呼ぶため、値が確実に反映される。
 *
 * @param hasUnsavedInput 保存されていない入力が残っているか
 */
export function useLeaveConfirm(hasUnsavedInput: boolean): LeaveConfirm {
  const allowedRef = useRef(false)
  useUnsavedChangesWarning(hasUnsavedInput)
  const blocker = useBlocker(() => hasUnsavedInput && !allowedRef.current)

  return {
    blocker,
    allowNextNavigation: () => {
      allowedRef.current = true
    },
  }
}
