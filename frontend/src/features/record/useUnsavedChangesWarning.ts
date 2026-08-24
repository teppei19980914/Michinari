import { useEffect } from 'react'

/**
 * 確定前に画面を離脱しようとした場合に警告する（仕様書6.5「確定前に画面を離脱した場合、
 * 入力内容は保存されない旨を警告する」）。タブを閉じる・再読み込み・別URLへの直接遷移を
 * ブラウザ標準の確認ダイアログで警告する。文言はブラウザ既定のものが使われる仕様上の制約
 * （beforeunloadのreturnValueにカスタム文言を設定してもブラウザは無視する）のため、
 * ロケールファイルには持たない。
 */
export function useUnsavedChangesWarning(shouldWarn: boolean): void {
  useEffect(() => {
    if (!shouldWarn) {
      return
    }
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [shouldWarn])
}
