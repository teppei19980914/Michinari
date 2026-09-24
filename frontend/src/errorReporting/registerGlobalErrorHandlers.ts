/**
 * イベントハンドラ・非同期処理内の未処理例外を診断ログへ記録する（Phase40）。
 *
 * Reactの`ErrorBoundary`は描画中の例外しか捕捉できず、`onClick`等のイベントハンドラや
 * `async`関数内で投げられた例外・未処理のPromise rejectionは構造的に取りこぼす。それらは
 * `window`の`error`/`unhandledrejection`イベントとしてしか観測できないため、ここで拾って
 * `reportClientError`へ渡す。`main.tsx`から一度だけ呼ぶ関数として切り出すのは、副作用を
 * テストしやすくするため（直書きするとテストの都度アプリ全体を起動する必要が生じる）。
 */
import { reportClientError } from './reportClientError'

export function registerGlobalErrorHandlers(): void {
  window.addEventListener('error', (event) => {
    reportClientError({
      message: event.message,
      stack: event.error instanceof Error ? event.error.stack : undefined,
    })
  })

  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason
    reportClientError({
      message: reason instanceof Error ? reason.message : String(reason),
      stack: reason instanceof Error ? reason.stack : undefined,
    })
  })
}
