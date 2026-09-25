import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { App } from './App.tsx'
import { registerGlobalErrorHandlers } from './errorReporting/registerGlobalErrorHandlers'

// ErrorBoundaryは描画中の例外しか捕捉できないため、イベントハンドラ・非同期処理内の
// 未処理例外も診断ログへ残す（Phase40）。レンダリング開始前に登録すること。
registerGlobalErrorHandlers()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
