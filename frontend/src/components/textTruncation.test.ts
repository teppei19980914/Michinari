import { describe, expect, it } from 'vitest'
import { isTextTruncatable } from './textTruncation'

describe('isTextTruncatable', () => {
  it('returns false for short single-line text', () => {
    expect(isTextTruncatable('短い文')).toBe(false)
  })

  it('returns true when the line count exceeds 3', () => {
    expect(isTextTruncatable('1行目\n2行目\n3行目\n4行目')).toBe(true)
  })

  it('returns false when the line count is exactly 3', () => {
    expect(isTextTruncatable('1行目\n2行目\n3行目')).toBe(false)
  })

  it('returns true when the character count is long even without newlines', () => {
    expect(isTextTruncatable('あ'.repeat(200))).toBe(true)
  })
})
