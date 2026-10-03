/**
 * フロントで捕捉した未処理エラーをバックエンドの診断ログへ記録する（Phase40 診断ログ
 * 出力・トレース強化、`backend/app/api/client_logs.py` `POST /client-logs`）。
 *
 * `ErrorBoundary.tsx`（描画中の例外）と`registerGlobalErrorHandlers.ts`（イベント
 * ハンドラ・非同期処理内の例外。ErrorBoundaryは構造的に捕捉できない）の両方から呼ぶ
 * 共有処理（CLAUDE.md DRYの原則）。`apiClient`を使わないのは、送信失敗を例外として
 * 扱う必要が無く（二次障害を防ぐため常に握りつぶす）、JSONの自動パースも不要なため。
 */
const CLIENT_LOGS_URL = '/api/v1/client-logs'

export function reportClientError(input: {
  message: string
  stack?: string
  /** Reactの`ErrorInfo.componentStack`は`string | null`（分岐を増やさないよう、
   * 呼び出し側で`undefined`へ変換せずそのまま受ける。`null`はバックエンドのスキーマ
   * （`component_stack: str | None`）とそのまま対応する）。 */
  componentStack?: string | null
}): void {
  fetch(CLIENT_LOGS_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      level: 'error',
      message: input.message,
      stack: input.stack,
      component_stack: input.componentStack,
      path: window.location.pathname,
    }),
  }).catch(() => {
    // 送信自体の失敗（バックエンド未起動等）をここで例外にすると、エラー報告のはずが
    // 新たな未処理エラーを生む。診断の最後の砦であるため常に握りつぶす。
  })
}
