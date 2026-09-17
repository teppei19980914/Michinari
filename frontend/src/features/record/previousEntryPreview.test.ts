import { describe, expect, it } from 'vitest'
import { buildPreviousEntryPreview } from './previousEntryPreview'

describe('buildPreviousEntryPreview', () => {
  it('returns the full text untruncated when within the preview length', () => {
    expect(buildPreviousEntryPreview('短い本文')).toEqual({
      preview: '短い本文',
      isTruncated: false,
    })
  })

  it('returns the full text untruncated at exactly the boundary length', () => {
    const body = 'a'.repeat(100)
    expect(buildPreviousEntryPreview(body)).toEqual({ preview: body, isTruncated: false })
  })

  it('truncates text longer than the preview length', () => {
    const body = 'a'.repeat(150)
    const result = buildPreviousEntryPreview(body)
    expect(result.preview).toBe('a'.repeat(100))
    expect(result.isTruncated).toBe(true)
  })
})
