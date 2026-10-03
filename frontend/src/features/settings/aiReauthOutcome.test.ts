import { describe, expect, it } from 'vitest'
import { resolveReauthOutcome } from './aiReauthOutcome'

describe('resolveReauthOutcome', () => {
  it('returns succeeded when PAT authentication is confirmed', () => {
    expect(resolveReauthOutcome({ status: 'AUTHENTICATED', authenticated: true })).toBe(
      'succeeded',
    )
  })

  it('returns failed when PAT authentication could not be confirmed', () => {
    expect(resolveReauthOutcome({ status: 'PENDING', authenticated: false })).toBe('failed')
  })
})
