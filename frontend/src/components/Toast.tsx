import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'
import { apiErrorDetail, apiErrorMessage } from '../api/client'
import { t } from '../locales/t'

type ToastVariant = 'info' | 'error'

type ToastEntry = {
  id: number
  message: string
  variant: ToastVariant
  /** 技術的な詳細（サポートへ報告する際に使う）。折りたたみで表示し、展開すると
   * 自動消滅を止める（開いた直後に消えると読めないため）。 */
  detail?: string
}

type ToastContextValue = {
  showToast: (message: string, variant?: ToastVariant, detail?: string) => void
  /** APIエラーをロケール文言でトースト表示する（画面ごとに同じ三項式を書かない、CLAUDE.md DRYの原則）。 */
  showApiError: (error: unknown) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const VARIANT_CLASSES: Record<ToastVariant, string> = {
  info: 'bg-gray-800',
  error: 'bg-red-600',
}

const AUTO_DISMISS_MS = 4000

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastEntry[]>([])
  const timeoutsRef = useRef(new Map<number, ReturnType<typeof setTimeout>>())

  const dismiss = useCallback((id: number) => {
    const timeoutId = timeoutsRef.current.get(id)
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId)
      timeoutsRef.current.delete(id)
    }
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  /** 詳細を開いたら自動消滅を止める（読み終える・報告のためコピーする前に消えないように）。 */
  const cancelAutoDismiss = useCallback((id: number) => {
    const timeoutId = timeoutsRef.current.get(id)
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId)
      timeoutsRef.current.delete(id)
    }
  }, [])

  const showToast = useCallback(
    (message: string, variant: ToastVariant = 'info', detail?: string) => {
      const id = Date.now()
      setToasts((current) => [...current, { id, message, variant, detail }])
      const timeoutId = setTimeout(() => dismiss(id), AUTO_DISMISS_MS)
      timeoutsRef.current.set(id, timeoutId)
    },
    [dismiss],
  )

  const showApiError = useCallback(
    (error: unknown) => {
      showToast(apiErrorMessage(error), 'error', apiErrorDetail(error))
    },
    [showToast],
  )

  return (
    <ToastContext.Provider value={{ showToast, showApiError }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`rounded-md px-4 py-2 text-sm text-white shadow-lg ${VARIANT_CLASSES[toast.variant]}`}
          >
            <div className="flex items-start gap-2">
              <p className="flex-1">{toast.message}</p>
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
              <details
                className="mt-1 text-xs text-white/70"
                onToggle={(e) => {
                  if (e.currentTarget.open) {
                    cancelAutoDismiss(toast.id)
                  }
                }}
              >
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
