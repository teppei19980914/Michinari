import { describe, expect, it } from 'vitest'
import { resolveInitialRecordInputMode } from './recordInputMode'

describe('resolveInitialRecordInputMode', () => {
  it('returns QUICK when the stored mode is QUICK', () => {
    expect(resolveInitialRecordInputMode('QUICK')).toBe('QUICK')
  })

  it('returns NORMAL when the stored mode is NORMAL', () => {
    expect(resolveInitialRecordInputMode('NORMAL')).toBe('NORMAL')
  })

  it('falls back to NORMAL for an unexpected value', () => {
    expect(resolveInitialRecordInputMode('')).toBe('NORMAL')
  })
})
