/** useUnsavedChangesWarning の回帰テスト。
 *
 * 呼び出し元(DailyReportPage.tsx)の描画テストは`shouldWarn`を渡していることまでしか
 * 検証しておらず、beforeunloadハンドラの中身（preventDefault・returnValue）や
 * addEventListener/removeEventListenerの対応が一度も直接検証されていなかった
 * （2026-09-19、テスト全般の抜け漏れ調査で発覚）。ブラウザの`beforeunload`確認ダイアログは
 * jsdom上で意味のある形では再現できないため、`window.addEventListener`/
 * `removeEventListener`をスパイしてハンドラの登録・内容・解除だけを直接検証する。 */
import { describe, expect, it, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useUnsavedChangesWarning } from './useUnsavedChangesWarning'

function findBeforeUnloadHandler(addSpy: ReturnType<typeof vi.spyOn>): EventListener | undefined {
  const call = addSpy.mock.calls.find((call: unknown[]) => call[0] === 'beforeunload')
  return call?.[1] as EventListener | undefined
}

function makeBeforeUnloadEvent() {
  return { preventDefault: vi.fn(), returnValue: undefined as unknown }
}

describe('useUnsavedChangesWarning', () => {
  it('registers no beforeunload listener when there is nothing unsaved', () => {
    const addSpy = vi.spyOn(window, 'addEventListener')

    renderHook(() => useUnsavedChangesWarning(false))

    expect(findBeforeUnloadHandler(addSpy)).toBeUndefined()
    addSpy.mockRestore()
  })

  it('prevents the default unload and sets returnValue when something is unsaved', () => {
    const addSpy = vi.spyOn(window, 'addEventListener')

    renderHook(() => useUnsavedChangesWarning(true))
    const handler = findBeforeUnloadHandler(addSpy)
    expect(handler).toBeDefined()

    const event = makeBeforeUnloadEvent()
    handler?.(event as unknown as Event)

    // returnValueへカスタム文言を設定してもブラウザは無視する仕様上の制約があるため、
    // 空文字を設定するだけでよい（useUnsavedChangesWarning.tsのコメント参照）。
    expect(event.preventDefault).toHaveBeenCalledOnce()
    expect(event.returnValue).toBe('')
    addSpy.mockRestore()
  })

  it('removes the listener once shouldWarn turns false', () => {
    const addSpy = vi.spyOn(window, 'addEventListener')
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    const { rerender } = renderHook(
      ({ shouldWarn }: { shouldWarn: boolean }) => useUnsavedChangesWarning(shouldWarn),
      { initialProps: { shouldWarn: true } },
    )
    const handler = findBeforeUnloadHandler(addSpy)

    rerender({ shouldWarn: false })

    expect(removeSpy).toHaveBeenCalledWith('beforeunload', handler)
    addSpy.mockRestore()
    removeSpy.mockRestore()
  })

  it('removes the listener on unmount', () => {
    const addSpy = vi.spyOn(window, 'addEventListener')
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    const { unmount } = renderHook(() => useUnsavedChangesWarning(true))
    const handler = findBeforeUnloadHandler(addSpy)

    unmount()

    expect(removeSpy).toHaveBeenCalledWith('beforeunload', handler)
    addSpy.mockRestore()
    removeSpy.mockRestore()
  })
})
