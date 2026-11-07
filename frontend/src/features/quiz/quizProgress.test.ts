import { describe, expect, it } from 'vitest'
import { isLastQuestion, nextIndex } from './quizProgress'

describe('isLastQuestion', () => {
  it('returns false when there are more questions after the current one', () => {
    expect(isLastQuestion(0, 3)).toBe(false)
  })

  it('returns true for the final index', () => {
    expect(isLastQuestion(2, 3)).toBe(true)
  })

  it('returns true for a single-question list', () => {
    expect(isLastQuestion(0, 1)).toBe(true)
  })
})

describe('nextIndex', () => {
  it('advances by one', () => {
    expect(nextIndex(0)).toBe(1)
  })
})
