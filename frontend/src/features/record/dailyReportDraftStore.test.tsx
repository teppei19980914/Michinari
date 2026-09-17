import { describe, expect, it, vi } from 'vitest'
import { render } from '@testing-library/react'
import { applySetStateAction, useDraftStore } from './dailyReportDraftStore'

function Trigger() {
  useDraftStore()
  return null
}

describe('useDraftStore', () => {
  it('fails loudly when used outside the provider', () => {
    // Providerの入れ忘れは、下書きが黙って保持されないより即座に気付けるほうがよい
    // （components/Toast.tsxのuseToastと同じ方針）。
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    try {
      expect(() => render(<Trigger />)).toThrow(
        'useDraftStore must be used within a DailyReportDraftProvider',
      )
    } finally {
      consoleError.mockRestore()
    }
  })
})

describe('applySetStateAction', () => {
  it('applies an updater function to the current value', () => {
    expect(applySetStateAction((current: number) => current + 1, 3)).toBe(4)
  })

  it('uses a direct value as-is', () => {
    // 現時点の呼び出し元は更新関数のみを使うが、setChatMessages等はReactのuseStateと
    // 同じSetStateAction型を公開しているため、直接値を渡す経路もあわせて固定する。
    expect(applySetStateAction(5, 3)).toBe(5)
  })
})
