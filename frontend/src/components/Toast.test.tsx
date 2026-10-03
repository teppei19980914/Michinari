import { describe, expect, it, vi, afterEach } from 'vitest'
import { act, render, screen, cleanup } from '@testing-library/react'
import { ApiError } from '../api/client'
import { t } from '../locales/t'
import { ToastProvider, useToast } from './Toast'

function Trigger({ onReady }: { onReady: (toast: ReturnType<typeof useToast>) => void }) {
  const toast = useToast()
  onReady(toast)
  return null
}

/** ToastProvider配下でフックを取り出す（描画後に showToast / showApiError を呼ぶため）。 */
function renderWithProvider() {
  let api: ReturnType<typeof useToast> | undefined
  render(
    <ToastProvider>
      <Trigger
        onReady={(toast) => {
          api = toast
        }}
      />
    </ToastProvider>,
  )
  if (!api) {
    throw new Error('ToastProviderの初期化に失敗しました')
  }
  return api
}

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

describe('ToastProvider', () => {
  it('shows the message passed to showToast', () => {
    const toast = renderWithProvider()

    act(() => toast.showToast('保存しました'))

    expect(screen.getByText('保存しました')).toBeTruthy()
  })

  it('dismisses the toast automatically', () => {
    vi.useFakeTimers()
    const toast = renderWithProvider()

    act(() => toast.showToast('保存しました'))
    expect(screen.getByText('保存しました')).toBeTruthy()

    // 自動消滅（AUTO_DISMISS_MS=4000）。時間を進めないと消えないため偽タイマーを使う。
    act(() => vi.advanceTimersByTime(4000))

    expect(screen.queryByText('保存しました')).toBeNull()
  })

  it('renders an api error with its localized message', () => {
    const toast = renderWithProvider()

    act(() => toast.showApiError(new ApiError('NOT_FOUND', '対象がありません')))

    expect(screen.getByText(t('errors.NOT_FOUND'))).toBeTruthy()
  })

  it('falls back to the default message for an unknown failure', () => {
    const toast = renderWithProvider()

    act(() => toast.showApiError(new Error('boom')))

    expect(screen.getByText(t('errors.default'))).toBeTruthy()
  })

  it('dismisses immediately when the close button is clicked', () => {
    const toast = renderWithProvider()
    act(() => toast.showToast('保存しました'))

    act(() => screen.getByRole('button', { name: t('common.action.close') }).click())

    expect(screen.queryByText('保存しました')).toBeNull()
  })

  it('shows a foldable technical detail for an API error, for reporting purposes', () => {
    const toast = renderWithProvider()

    act(() => toast.showApiError(new ApiError('NOT_FOUND', '対象(id=1)がありません')))

    expect(screen.getByText(t('common.errorDetailsSummary'))).toBeTruthy()
    expect(screen.getByText('NOT_FOUND: 対象(id=1)がありません')).toBeTruthy()
  })

  it('does not show a foldable detail for a plain showToast call', () => {
    const toast = renderWithProvider()

    act(() => toast.showToast('保存しました'))

    expect(screen.queryByText(t('common.errorDetailsSummary'))).toBeNull()
  })

  it('does nothing extra when the technical detail is toggled closed', () => {
    vi.useFakeTimers()
    const toast = renderWithProvider()
    act(() => toast.showApiError(new ApiError('NOT_FOUND', '対象がありません')))

    const details = screen.getByText(t('common.errorDetailsSummary')).closest('details')
    if (!details) {
      throw new Error('details要素が見つかりません')
    }
    // 開かずに（openのまま変化させず）toggleイベントだけ発生した場合は自動消滅を止めない。
    act(() => {
      details.open = false
      details.dispatchEvent(new Event('toggle'))
    })
    act(() => vi.advanceTimersByTime(4000))

    expect(screen.queryByText(t('errors.NOT_FOUND'))).toBeNull()
  })

  it('still dismisses via the close button after the auto-dismiss was already cancelled', () => {
    const toast = renderWithProvider()
    act(() => toast.showApiError(new ApiError('NOT_FOUND', '対象がありません')))

    const details = screen.getByText(t('common.errorDetailsSummary')).closest('details')
    if (!details) {
      throw new Error('details要素が見つかりません')
    }
    act(() => {
      details.open = true
      details.dispatchEvent(new Event('toggle'))
    })
    act(() => screen.getByRole('button', { name: t('common.action.close') }).click())

    expect(screen.queryByText(t('errors.NOT_FOUND'))).toBeNull()
  })

  it('stops the auto-dismiss once the technical detail is opened', () => {
    vi.useFakeTimers()
    const toast = renderWithProvider()
    act(() => toast.showApiError(new ApiError('NOT_FOUND', '対象がありません')))

    const details = screen.getByText(t('common.errorDetailsSummary')).closest('details')
    if (!details) {
      throw new Error('details要素が見つかりません')
    }
    act(() => {
      details.open = true
      details.dispatchEvent(new Event('toggle'))
    })

    act(() => vi.advanceTimersByTime(4000))

    expect(screen.getByText(t('errors.NOT_FOUND'))).toBeTruthy()
  })
})

describe('useToast', () => {
  it('fails loudly when used outside the provider', () => {
    // Providerの入れ忘れは、トーストが黙って出ないより即座に気付けるほうがよい。
    // Reactがエラー境界なしの例外をconsole.errorに出すため、テスト出力を汚さないよう抑止する。
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    try {
      expect(() => render(<Trigger onReady={() => {}} />)).toThrow(
        'useToast must be used within a ToastProvider',
      )
    } finally {
      consoleError.mockRestore()
    }
  })
})
