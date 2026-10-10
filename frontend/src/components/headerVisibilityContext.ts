import { createContext, useContext } from 'react'

/** ヘッダー（GlobalNav）の開閉状態を画面から読むための文脈（UIリッチ化）。
 * 部品（HeaderVisibilityProvider.tsx）と分けてあるのは、React Fast Refreshが
 * 「コンポーネントだけをexportするファイル」を要求するため（toastContext.tsと同じ理由）。 */
export const HeaderVisibilityContext = createContext(true)

/** `true`ならヘッダー（`GlobalNav`）を表示する。`HeaderVisibilityProvider`の外では常に`true`。 */
export function useHeaderVisibility(): boolean {
  return useContext(HeaderVisibilityContext)
}
