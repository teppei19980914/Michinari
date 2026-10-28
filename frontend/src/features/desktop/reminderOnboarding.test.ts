import { describe, expect, it } from 'vitest'
import { resolveAutostartSyncMessageKey } from './reminderOnboarding'

describe('resolveAutostartSyncMessageKey', () => {
  it('returns applied with no message when the registry was updated', () => {
    expect(resolveAutostartSyncMessageKey({ supported: true, applied: true })).toEqual({
      kind: 'applied',
      messageKey: null,
    })
  })

  it('returns an info message when running from source (unsupported)', () => {
    expect(resolveAutostartSyncMessageKey({ supported: false, applied: false })).toEqual({
      kind: 'info',
      messageKey: 'desktop.autostartSync.unsupported',
    })
  })

  it('returns an error message when supported but the registry write failed', () => {
    expect(resolveAutostartSyncMessageKey({ supported: true, applied: false })).toEqual({
      kind: 'error',
      messageKey: 'desktop.autostartSync.failed',
    })
  })
})
