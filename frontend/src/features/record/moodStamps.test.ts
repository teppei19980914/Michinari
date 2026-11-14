import { describe, expect, it } from 'vitest'
import { MOOD_VALUES, isMoodValue } from './moodStamps'

describe('isMoodValue', () => {
  it('accepts every defined mood value', () => {
    for (const value of MOOD_VALUES) {
      expect(isMoodValue(value)).toBe(true)
    }
  })

  it('rejects values outside the 1〜5 range', () => {
    expect(isMoodValue(0)).toBe(false)
    expect(isMoodValue(6)).toBe(false)
  })
})
