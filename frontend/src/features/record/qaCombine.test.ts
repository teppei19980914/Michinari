import { describe, expect, it } from 'vitest'
import { combineQaAnswers, hasAnyQaInput } from './qaCombine'

describe('combineQaAnswers', () => {
  it('returns an empty string when nothing is filled in', () => {
    expect(combineQaAnswers(['Q1', 'Q2'], ['', ''], '')).toBe('')
  })

  it('returns the free text as-is when no question is answered', () => {
    expect(combineQaAnswers(['Q1', 'Q2'], ['', ''], '自由記述')).toBe('自由記述')
  })

  it('labels a single answered question and omits unanswered ones', () => {
    expect(combineQaAnswers(['Q1', 'Q2'], ['A1', ''], '')).toBe('【Q1】\nA1')
  })

  it('labels every answered question and joins them with a blank line', () => {
    expect(combineQaAnswers(['Q1', 'Q2'], ['A1', 'A2'], '')).toBe('【Q1】\nA1\n\n【Q2】\nA2')
  })

  it('appends the free text after the labeled answers', () => {
    expect(combineQaAnswers(['Q1', 'Q2'], ['A1', ''], '自由記述')).toBe('【Q1】\nA1\n\n自由記述')
  })

  it('treats whitespace-only answers as unanswered', () => {
    expect(combineQaAnswers(['Q1'], ['   '], '')).toBe('')
  })

  it('treats a missing answer index as unanswered', () => {
    expect(combineQaAnswers(['Q1', 'Q2'], ['A1'], '')).toBe('【Q1】\nA1')
  })
})

describe('hasAnyQaInput', () => {
  it('is false when every answer and the free text are empty', () => {
    expect(hasAnyQaInput(['', ''], '')).toBe(false)
  })

  it('is true when an answer has text', () => {
    expect(hasAnyQaInput(['A1', ''], '')).toBe(true)
  })

  it('is true when the free text has content', () => {
    expect(hasAnyQaInput(['', ''], '自由記述')).toBe(true)
  })

  it('is false when an answer is whitespace only', () => {
    expect(hasAnyQaInput(['   '], '')).toBe(false)
  })
})
