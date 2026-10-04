import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'
import { apiErrorDetail, apiErrorMessage } from '../api/client'
import { t } from '../locales/t'

type ToastVariant = 'info' | 'error'

type ToastEntry = {
  id: number
  /** 何をしようとして失敗したかの見出し（例: 「月次報告を生成できませんでした」）。 */
  title?: string
  message: string
  variant: ToastVariant
  /** 技術的な詳細（サポートへ報告する際に使う）。折りたたみで表示し、展開すると
   * 自動消滅を止める（開いた直後に消えると読めないため）。 */
  detail?: string
}

type ToastContextValue = {
  showToast: (message: string, variant?: ToastVariant, detail?: string) => void
  /** APIエラーをロケール文言でトースト表示する（画面ごとに同じ三項式を書かない、CLAUDE.md DRYの原則）。 */
  /** APIエラーをロケール文言でトースト表示する（画面ごとに同じ三項式を書かない、CLAUDE.md DRYの原則）。 */
  showApiError: (error: unknown) => void
  /** 「何をしようとして失敗したか」の見出し付きでAPIエラーを表示する。ミューテーションの
   * onErrorへ直接渡すと第2引数（変数）が見出しとして解釈されるため、onErrorには使わず
   * 明示的な無名関数の中から呼ぶ。 */
  showApiErrorWithTitle: (title: string, error: unknown) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const VARIANT_CLASSES: Record<ToastVariant, string> = {
  info: 'bg-gray-800',
  error: 'bg-red-600',
}

/** 全てのトーストは一定時間で自動的に消える（通知が積み重なって画面を塞がないため）。
 * エラーは二文（何が起きたか・何をすればよいか）を読む時間を取り、情報より長く表示する。 */
const AUTO_DISMISS_MS: Record<ToastVariant, number> = {
  info: 4000,
  error: 8000,
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastEntry[]>([])
  const timeoutsRef = useRef(new Map<number, ReturnType<typeof setTimeout>>())

  const dismiss = useCallback((id: number) => {
    // 全てのトーストは登録時に自動消去のタイマーを持つため、ここでは必ず存在する。
    clearTimeout(timeoutsRef.current.get(id))
    timeoutsRef.current.delete(id)
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const pushToast = useCallback(
    (entry: Omit<ToastEntry, 'id'>) => {
      const id = Date.now()
      setToasts((current) => [...current, { ...entry, id }])
      const timeoutId = setTimeout(() => dismiss(id), AUTO_DISMISS_MS[entry.variant])
      timeoutsRef.current.set(id, timeoutId)
    },
    [dismiss],
  )

  const showToast = useCallback(
    (message: string, variant: ToastVariant = 'info', detail?: string) => {
      pushToast({ message, variant, detail })
    },
    [pushToast],
  )

  const showApiErrorWithTitle = useCallback(
    (title: string, error: unknown) => {
      pushToast({
        title,
        message: apiErrorMessage(error),
        variant: 'error',
        detail: apiErrorDetail(error),
      })
    },
    [pushToast],
  )

  const showApiError = useCallback(
    (error: unknown) => {
      pushToast({ message: apiErrorMessage(error), variant: 'error', detail: apiErrorDetail(error) })
    },
    [pushToast],
  )

  return (
    <ToastContext.Provider value={{ showToast, showApiError, showApiErrorWithTitle }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`rounded-md px-4 py-2 text-sm text-white shadow-lg ${VARIANT_CLASSES[toast.variant]}`}
          >
            <div className="flex items-start gap-2">
              <div className="flex-1">
                {toast.title && <p className="font-semibold">{toast.title}</p>}
                <p>{toast.message}</p>
              </div>
              <button
                type="button"
                aria-label={t('common.action.close')}
                className="text-white/70 hover:text-white"
                onClick={() => dismiss(toast.id)}
              >
                ×
              </button>
            </div>
            {toast.detail && (
              <details className="mt-1 text-xs text-white/70">
                <summary className="cursor-pointer select-none">
                  {t('common.errorDetailsSummary')}
                </summary>
                <pre className="mt-1 whitespace-pre-wrap">{toast.detail}</pre>
              </details>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider')
  }
  return context
}
