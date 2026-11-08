import { describe, expect, it } from 'vitest'
import { formatAccuracyPercent } from './quizAccuracyFormat'

describe('formatAccuracyPercent', () => {
  it('returns a dash when there are no answers', () => {
    expect(formatAccuracyPercent(0, 0)).toBe('-')
  })

  it('rounds to the nearest percent', () => {
    expect(formatAccuracyPercent(1, 3)).toBe('33%')
  })

  it('returns 100% when all answers are correct', () => {
    expect(formatAccuracyPercent(2, 2)).toBe('100%')
  })

  it('returns 0% when none are correct', () => {
    expect(formatAccuracyPercent(0, 2)).toBe('0%')
  })
})
