import { describe, expect, it } from 'vitest'
import { buildSessionSummary, isLastQuestion, nextIndex } from './vocabQuizProgress'

describe('isLastQuestion', () => {
  it('returns false when there are more questions after the current one', () => {
    expect(isLastQuestion(0, 3)).toBe(false)
  })

  it('returns true for the final index', () => {
    expect(isLastQuestion(2, 3)).toBe(true)
  })
})

describe('nextIndex', () => {
  it('advances by one', () => {
    expect(nextIndex(0)).toBe(1)
  })
})

describe('buildSessionSummary', () => {
  it('counts correct and incorrect answers and lists wrong cards', () => {
    const summary = buildSessionSummary([
      { cardId: 1, term: 'A', isCorrect: true },
      { cardId: 2, term: 'B', isCorrect: false },
      { cardId: 3, term: 'C', isCorrect: false },
    ])

    expect(summary.correctCount).toBe(1)
    expect(summary.totalCount).toBe(3)
    expect(summary.accuracyPercent).toBeCloseTo((1 / 3) * 100)
    expect(summary.wrongCards).toEqual([
      { cardId: 2, term: 'B' },
      { cardId: 3, term: 'C' },
    ])
  })

  it('returns null accuracy for an empty session', () => {
    const summary = buildSessionSummary([])

    expect(summary.accuracyPercent).toBeNull()
    expect(summary.wrongCards).toEqual([])
  })

  it('returns no wrong cards when everything was correct', () => {
    const summary = buildSessionSummary([{ cardId: 1, term: 'A', isCorrect: true }])

    expect(summary.wrongCards).toEqual([])
    expect(summary.accuracyPercent).toBe(100)
  })
})
