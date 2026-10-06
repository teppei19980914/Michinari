import { createContext, useContext } from 'react'

/** トーストの表示を画面から呼ぶための文脈（ToastProvider が提供する）。
 * 部品（Toast.tsx）と分けてあるのは、React Fast Refresh が「コンポーネントだけを export する
 * ファイル」を要求するため（フックや文脈をコンポーネントと同じファイルに置くと警告になる）。 */
export type ToastVariant = 'info' | 'error'

export type ToastContextValue = {
  showToast: (message: string, variant?: ToastVariant, detail?: string) => void
  /** APIエラーをロケール文言でトースト表示する（画面ごとに同じ三項式を書かない、CLAUDE.md DRYの原則）。 */
  showApiError: (error: unknown) => void
  /** 「何をしようとして失敗したか」の見出し付きでAPIエラーを表示する。ミューテーションの
   * onErrorへ直接渡すと第2引数（変数）が見出しとして解釈されるため、onErrorには使わず
   * 明示的な無名関数の中から呼ぶ。 */
  showApiErrorWithTitle: (title: string, error: unknown) => void
}

export const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider')
  }
  return context
}
