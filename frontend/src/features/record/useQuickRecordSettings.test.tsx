import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import type { AppSettingsRead } from '../../api/settings'
import { useQuickRecordSettings } from './useQuickRecordSettings'

const getSettings = vi.hoisted(() => vi.fn())
vi.mock('../../api/settings', () => ({ getSettings }))

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient()
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
})

describe('useQuickRecordSettings', () => {
  it('returns the default note length and undefined last modes before settings load', () => {
    getSettings.mockReturnValue(new Promise(() => undefined))
    const { result } = renderHook(() => useQuickRecordSettings(), { wrapper })

    expect(result.current.quickNoteMaxChars).toBe(100)
    expect(result.current.lastModes).toBeUndefined()
  })

  it('reflects the stored quick_record settings once loaded', async () => {
    getSettings.mockResolvedValue({
      quick_record: {
        note_max_chars: 80,
        last_mode_exam: 'QUICK',
        last_mode_reading: 'NORMAL',
        last_mode_work: 'NORMAL',
        voice_hint_dismissed: false,
      },
    } as AppSettingsRead)
    const { result } = renderHook(() => useQuickRecordSettings(), { wrapper })

    await waitFor(() => expect(result.current.lastModes).toEqual({
      exam: 'QUICK',
      reading: 'NORMAL',
      work: 'NORMAL',
    }))
    expect(result.current.quickNoteMaxChars).toBe(80)
  })

  it('keeps the same lastModes reference across re-renders with unchanged data', async () => {
    getSettings.mockResolvedValue({
      quick_record: {
        note_max_chars: 100,
        last_mode_exam: 'NORMAL',
        last_mode_reading: 'NORMAL',
        last_mode_work: 'NORMAL',
        voice_hint_dismissed: false,
      },
    } as AppSettingsRead)
    const { result, rerender } = renderHook(() => useQuickRecordSettings(), { wrapper })

    await waitFor(() => expect(result.current.lastModes).toBeDefined())
    const first = result.current.lastModes
    rerender()
    expect(result.current.lastModes).toBe(first)
  })
})
