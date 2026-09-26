import { describe, expect, it } from 'vitest'
import { resolveBookSpineVariant } from './bookStatusVariant'

describe('resolveBookSpineVariant', () => {
  it('maps CLOSED_WITH_RESULT to completed', () => {
    expect(resolveBookSpineVariant('CLOSED_WITH_RESULT')).toBe('completed')
  })

  it('maps CLOSED_WITHOUT_RESULT to interrupted', () => {
    expect(resolveBookSpineVariant('CLOSED_WITHOUT_RESULT')).toBe('interrupted')
  })
})
