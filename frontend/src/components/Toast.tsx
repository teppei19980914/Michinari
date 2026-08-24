import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { apiErrorMessage } from '../api/client'

type ToastVariant = 'info' | 'error'

type ToastEntry = {
  id: number
  message: string
  variant: ToastVariant
}

type ToastContextValue = {
  showToast: (message: string, variant?: ToastVariant) => void
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

  const showToast = useCallback((message: string, variant: ToastVariant = 'info') => {
    const id = Date.now()
    setToasts((current) => [...current, { id, message, variant }])
    setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id))
    }, AUTO_DISMISS_MS)
  }, [])

  const showApiError = useCallback(
    (error: unknown) => {
      showToast(apiErrorMessage(error), 'error')
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
            {toast.message}
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
