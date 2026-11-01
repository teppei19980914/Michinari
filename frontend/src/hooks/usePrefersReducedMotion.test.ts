import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { usePrefersReducedMotion } from './usePrefersReducedMotion'

let mediaListeners: Array<() => void>
let mediaMatches: boolean

function mockMatchMedia() {
  mediaListeners = []
  mediaMatches = false
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation(() => ({
      get matches() {
        return mediaMatches
      },
      media: '(prefers-reduced-motion: reduce)',
      addEventListener: (_event: string, listener: () => void) => {
        mediaListeners.push(listener)
      },
      removeEventListener: (_event: string, listener: () => void) => {
        mediaListeners = mediaListeners.filter((l) => l !== listener)
      },
    })),
  )
}

beforeEach(() => {
  mockMatchMedia()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('usePrefersReducedMotion', () => {
  it('returns false when the OS has no reduced-motion preference', () => {
    mediaMatches = false
    const { result } = renderHook(() => usePrefersReducedMotion())
    expect(result.current).toBe(false)
  })

  it('returns true when the OS prefers reduced motion', () => {
    mediaMatches = true
    const { result } = renderHook(() => usePrefersReducedMotion())
    expect(result.current).toBe(true)
  })

  it('follows live changes to the OS preference', () => {
    mediaMatches = false
    const { result } = renderHook(() => usePrefersReducedMotion())
    expect(result.current).toBe(false)

    mediaMatches = true
    act(() => mediaListeners.forEach((listener) => listener()))
    expect(result.current).toBe(true)
  })

  it('境界値: window.matchMediaが無い環境では常にfalseを返す', () => {
    vi.stubGlobal('matchMedia', undefined)
    const { result } = renderHook(() => usePrefersReducedMotion())
    expect(result.current).toBe(false)
  })
})
