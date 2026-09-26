import { describe, expect, it } from 'vitest'
import { resolveBookSpineVariant, resolveSpineHueClass } from './bookStatusVariant'

describe('resolveBookSpineVariant', () => {
  it('maps CLOSED_WITH_RESULT to completed', () => {
    expect(resolveBookSpineVariant('CLOSED_WITH_RESULT')).toBe('completed')
  })

  it('maps CLOSED_WITHOUT_RESULT to interrupted', () => {
    expect(resolveBookSpineVariant('CLOSED_WITHOUT_RESULT')).toBe('interrupted')
  })
})

describe('resolveSpineHueClass', () => {
  it('picks the same color for the same goal id every time (deterministic)', () => {
    expect(resolveSpineHueClass(3)).toBe(resolveSpineHueClass(3))
  })

  it('wraps around once ids exceed the palette size', () => {
    const paletteSize = 8
    expect(resolveSpineHueClass(1)).toBe(resolveSpineHueClass(1 + paletteSize))
  })

  it('picks different colors for different ids within the palette', () => {
    expect(resolveSpineHueClass(0)).not.toBe(resolveSpineHueClass(1))
  })
})
