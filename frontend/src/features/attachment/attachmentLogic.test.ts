import { describe, expect, it } from 'vitest'
import type { AttachmentRead } from '../../api/attachment'
import { isAtMaxCount, totalSelectedChars } from './attachmentLogic'

const ATTACHMENTS: AttachmentRead[] = [
  { id: 1, file_name: 'a.pdf', char_count: 100 },
  { id: 2, file_name: 'b.pdf', char_count: 200 },
  { id: 3, file_name: 'c.pdf', char_count: 300 },
]

describe('totalSelectedChars', () => {
  it('returns 0 when nothing is selected', () => {
    expect(totalSelectedChars(ATTACHMENTS, [])).toBe(0)
  })

  it('sums char_count for selected ids', () => {
    expect(totalSelectedChars(ATTACHMENTS, [1, 3])).toBe(400)
  })

  it('ignores ids that no longer exist', () => {
    expect(totalSelectedChars(ATTACHMENTS, [1, 999])).toBe(100)
  })
})

describe('isAtMaxCount', () => {
  it('returns false when below the limit', () => {
    expect(isAtMaxCount(2, 50)).toBe(false)
  })

  it('returns true when at the limit', () => {
    expect(isAtMaxCount(50, 50)).toBe(true)
  })

  it('returns true when above the limit', () => {
    expect(isAtMaxCount(51, 50)).toBe(true)
  })
})
