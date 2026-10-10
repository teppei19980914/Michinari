/** ThemeProvider（UIリッチ化）。設定取得後に<html>のdata属性へ反映すること、
 * theme="system"の間だけOSの明暗切替を追従することを固定する。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { AppSettingsRead } from '../api/settings'
import { DISPLAY_PREFERENCE_STORAGE_KEY } from '../hooks/useDisplayPreferenceStorage'
import { ThemeProvider } from './ThemeProvider'

const getSettings = vi.hoisted(() => vi.fn())
vi.mock('../api/settings', () => ({ getSettings }))

function makeSettings(overrides: Partial<AppSettingsRead['display']> = {}): AppSettingsRead {
  return {
    display: {
      locale: 'ja',
      theme: 'light',
      default_granularity: 'WEEK',
      accent_color: 'blue',
      font_scale: 'standard',
      ...overrides,
    },
  } as AppSettingsRead
}

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
      media: '(prefers-color-scheme: dark)',
      addEventListener: (_event: string, listener: () => void) => {
        mediaListeners.push(listener)
      },
      removeEventListener: (_event: string, listener: () => void) => {
        mediaListeners = mediaListeners.filter((l) => l !== listener)
      },
    })),
  )
}

function renderProvider(settings: AppSettingsRead) {
  getSettings.mockResolvedValue(settings)
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <div>content</div>
      </ThemeProvider>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  window.localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
  document.documentElement.removeAttribute('data-accent')
  document.documentElement.removeAttribute('data-font-scale')
  mockMatchMedia()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('ThemeProvider', () => {
  it('applies the fetched display settings to <html>', async () => {
    renderProvider(makeSettings({ theme: 'dark', accent_color: 'purple', font_scale: 'large' }))

    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('dark'))
    expect(document.documentElement.dataset.accent).toBe('purple')
    expect(document.documentElement.dataset.fontScale).toBe('large')
  })

  it('caches the applied preference to localStorage', async () => {
    renderProvider(makeSettings({ theme: 'light', accent_color: 'green', font_scale: 'small' }))

    await waitFor(() =>
      expect(window.localStorage.getItem(DISPLAY_PREFERENCE_STORAGE_KEY)).toBe(
        JSON.stringify({ themePreference: 'light', accentColor: 'green', fontScale: 'small' }),
      ),
    )
  })

  it('resolves theme="system" using the current OS preference', async () => {
    mediaMatches = true
    renderProvider(makeSettings({ theme: 'system' }))

    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('dark'))
  })

  it('follows OS preference changes live while theme="system"', async () => {
    mediaMatches = false
    renderProvider(makeSettings({ theme: 'system' }))

    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('light'))

    mediaMatches = true
    mediaListeners.forEach((listener) => listener())
    expect(document.documentElement.dataset.theme).toBe('dark')

    mediaMatches = false
    mediaListeners.forEach((listener) => listener())
    expect(document.documentElement.dataset.theme).toBe('light')
  })

  it('does not subscribe to OS preference changes for a fixed theme', async () => {
    renderProvider(makeSettings({ theme: 'dark' }))

    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('dark'))
    expect(mediaListeners).toHaveLength(0)
  })

  it('renders children immediately without waiting for settings to load', () => {
    const { getByText } = renderProvider(makeSettings())
    expect(getByText('content')).toBeTruthy()
  })
})
