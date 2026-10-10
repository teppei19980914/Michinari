import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { App } from './App.tsx'
import { registerGlobalErrorHandlers } from './errorReporting/registerGlobalErrorHandlers'
import { getSettings } from './api/settings'
import { isLocale, setLocale } from './locales/t'

// ErrorBoundaryは描画中の例外しか捕捉できないため、イベントハンドラ・非同期処理内の
// 未処理例外も診断ログへ残す（Phase40）。レンダリング開始前に登録すること。
registerGlobalErrorHandlers()

/** 描画前に表示言語を確定させる（日英i18n対応）。
 *
 * `t()`は呼び出し箇所（本体コードで845箇所超）ごとにContext経由で言語を受け取る構成では
 * なく、モジュール内の現在ロケールを参照する単純な構成にしている。そのため言語は描画開始前に
 * 一度確定させ、設定画面での変更は保存後の全体リロードで反映する方針にした
 * （未決事項の設計検討、2026-10-09確定）。取得に失敗した場合は既定のjaで描画を続ける
 * （設定取得の失敗で起動自体を止めるべきではない）。 */
async function bootstrapLocale(): Promise<void> {
  try {
    const settings = await getSettings()
    const locale = settings.display.locale
    if (isLocale(locale)) {
      setLocale(locale)
      document.documentElement.lang = locale
    }
  } catch {
    // 既定のja・<html lang>の初期値のまま描画を続ける。
  }
}

bootstrapLocale().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
})
