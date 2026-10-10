/** 表示設定のlocalStorageキャッシュ（UIリッチ化）。壊れた保存値・保存失敗時にも
 * 例外を投げず、サーバ値による表示を妨げないことを固定する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  DISPLAY_PREFERENCE_STORAGE_KEY,
  readDisplayPreference,
  resolveTheme,
  writeDisplayPreference,
} from './useDisplayPreferenceStorage'

function mockMatchMedia(matches: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockReturnValue({
      matches,
      media: '(prefers-color-scheme: dark)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  )
}

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('readDisplayPreference / writeDisplayPreference', () => {
  it('returns null when nothing is stored', () => {
    expect(readDisplayPreference()).toBe(null)
  })

  it('round-trips a written preference', () => {
    writeDisplayPreference({ themePreference: 'dark', accentColor: 'green', fontScale: 'large' })

    expect(readDisplayPreference()).toEqual({
      themePreference: 'dark',
      accentColor: 'green',
      fontScale: 'large',
    })
  })

  it('returns null for malformed JSON', () => {
    window.localStorage.setItem(DISPLAY_PREFERENCE_STORAGE_KEY, '{not json')

    expect(readDisplayPreference()).toBe(null)
  })

  it('returns null when the stored shape is missing a field', () => {
    window.localStorage.setItem(
      DISPLAY_PREFERENCE_STORAGE_KEY,
      JSON.stringify({ themePreference: 'dark', accentColor: 'green' }),
    )

    expect(readDisplayPreference()).toBe(null)
  })

  it('ignores a read failure instead of throwing', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })

    expect(readDisplayPreference()).toBe(null)
  })

  it('ignores a write failure instead of throwing', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })

    expect(() =>
      writeDisplayPreference({ themePreference: 'system', accentColor: 'blue', fontScale: 'standard' }),
    ).not.toThrow()
  })
})

describe('resolveTheme', () => {
  it('returns light/dark as-is', () => {
    expect(resolveTheme('light')).toBe('light')
    expect(resolveTheme('dark')).toBe('dark')
  })

  it('resolves system to dark when the OS prefers dark', () => {
    mockMatchMedia(true)
    expect(resolveTheme('system')).toBe('dark')
  })

  it('resolves system to light when the OS prefers light', () => {
    mockMatchMedia(false)
    expect(resolveTheme('system')).toBe('light')
  })
})
