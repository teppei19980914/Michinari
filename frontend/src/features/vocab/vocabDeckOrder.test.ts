import { describe, expect, it } from 'vitest'
import { swapByOffset } from './vocabDeckOrder'

describe('swapByOffset', () => {
  it('returns the list unchanged when the target index is out of bounds', () => {
    expect(swapByOffset([1, 2, 3], 0, -1)).toEqual([1, 2, 3])
    expect(swapByOffset([1, 2, 3], 2, 1)).toEqual([1, 2, 3])
  })

  it('swaps the two indices when within bounds', () => {
    expect(swapByOffset([1, 2, 3], 0, 1)).toEqual([2, 1, 3])
  })
})
