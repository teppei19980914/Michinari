import { describe, expect, it } from 'vitest'
import {
  buildQuickRecordSettingsPayload,
  resolveQuickRecordSettingsGuard,
} from './quickRecordSettings'

describe('resolveQuickRecordSettingsGuard', () => {
  it('allows submission for a positive integer', () => {
    expect(resolveQuickRecordSettingsGuard({ noteMaxChars: 100 })).toEqual({
      canSubmit: true,
      errorKey: null,
    })
  })

  it('blocks submission for zero', () => {
    expect(resolveQuickRecordSettingsGuard({ noteMaxChars: 0 }).canSubmit).toBe(false)
  })

  it('blocks submission for a non-integer', () => {
    expect(resolveQuickRecordSettingsGuard({ noteMaxChars: 1.5 }).canSubmit).toBe(false)
  })
})

describe('buildQuickRecordSettingsPayload', () => {
  it('maps the draft to the request shape', () => {
    expect(buildQuickRecordSettingsPayload({ noteMaxChars: 80 })).toEqual({ note_max_chars: 80 })
  })
})
