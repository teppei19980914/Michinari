import { Component, type ErrorInfo, type ReactNode } from 'react'
import { t } from '../locales/t'
import { reportClientError } from '../errorReporting/reportClientError'

type ErrorBoundaryState = { error: Error | null }

/**
 * 画面全体の予期しない描画エラーを拾う（非エンジニア向けエラー表示改善2026-09-19）。
 *
 * これが無いと、Reactの描画中の例外で画面が真っ白のまま止まり、非エンジニアには
 * 何が起きたのか・何をすればいいのかが全く分からない。技術的な詳細（スタック等）は
 * 折りたたみにして残し、非エンジニアには「再読み込みしてください」とだけ伝える。
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // 利用者へは出さず、開発者が原因調査できるようログにのみ残す。
    console.error('Unhandled render error', error, info)
    // ブラウザのコンソールは利用者自身が開かない限り誰にも届かない（Phase40）。
    // バックエンドの診断ログへも残し、ログエクスポート機能で共有できるようにする。
    reportClientError({
      message: error.message,
      stack: error.stack,
      componentStack: info.componentStack,
    })
  }

  render(): ReactNode {
    const { error } = this.state
    if (error) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-3 p-6 text-center">
          <p className="text-sm text-gray-700">{t('errorBoundary.message')}</p>
          <details className="text-xs text-gray-400">
            <summary className="cursor-pointer select-none">
              {t('errorBoundary.detailsSummary')}
            </summary>
            <pre className="mt-1 max-w-md whitespace-pre-wrap text-left">{error.message}</pre>
          </details>
        </div>
      )
    }
    return this.props.children
  }
}
