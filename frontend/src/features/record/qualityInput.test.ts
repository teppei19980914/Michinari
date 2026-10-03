import { describe, expect, it } from 'vitest'
import {
  isValidPercentValue,
  isValidSubjectiveValue,
  resolveQualityInputKind,
  resolveQualityLabelKey,
  subjectiveScaleFromNormalized,
} from './qualityInput'

describe('resolveQualityInputKind', () => {
  it('hides the input for NONE', () => {
    expect(resolveQualityInputKind('NONE')).toBe('HIDDEN')
  })

  it('shows a 0-100 percent input for OBJECTIVE', () => {
    expect(resolveQualityInputKind('OBJECTIVE')).toBe('PERCENT')
  })

  it('shows a 0-100 percent input for SELF_SCORED', () => {
    expect(resolveQualityInputKind('SELF_SCORED')).toBe('PERCENT')
  })

  it('shows a 5-level scale for SUBJECTIVE', () => {
    expect(resolveQualityInputKind('SUBJECTIVE')).toBe('SUBJECTIVE_SCALE')
  })
})

describe('resolveQualityLabelKey', () => {
  it('resolves to the correctness-rate label for OBJECTIVE', () => {
    expect(resolveQualityLabelKey('OBJECTIVE')).toBe(
      'dailyReport.studyLog.qualityShortLabel.PERCENT',
    )
  })

  it('resolves to the correctness-rate label for SELF_SCORED', () => {
    expect(resolveQualityLabelKey('SELF_SCORED')).toBe(
      'dailyReport.studyLog.qualityShortLabel.PERCENT',
    )
  })

  it('resolves to the impression label for SUBJECTIVE', () => {
    expect(resolveQualityLabelKey('SUBJECTIVE')).toBe(
      'dailyReport.studyLog.qualityShortLabel.SUBJECTIVE_SCALE',
    )
  })
})

describe('isValidSubjectiveValue', () => {
  it('accepts integers from 1 to 5', () => {
    expect(isValidSubjectiveValue(1)).toBe(true)
    expect(isValidSubjectiveValue(5)).toBe(true)
  })

  it('rejects out-of-range or non-integer values', () => {
    expect(isValidSubjectiveValue(0)).toBe(false)
    expect(isValidSubjectiveValue(6)).toBe(false)
    expect(isValidSubjectiveValue(2.5)).toBe(false)
  })
})

describe('isValidPercentValue', () => {
  it('accepts 0 to 100', () => {
    expect(isValidPercentValue(0)).toBe(true)
    expect(isValidPercentValue(100)).toBe(true)
  })

  it('rejects values outside 0-100', () => {
    expect(isValidPercentValue(-1)).toBe(false)
    expect(isValidPercentValue(101)).toBe(false)
  })
})

describe('subjectiveScaleFromNormalized', () => {
  it('inverts the 1-5 to 20-100 conversion table exactly', () => {
    expect(subjectiveScaleFromNormalized(20)).toBe(1)
    expect(subjectiveScaleFromNormalized(40)).toBe(2)
    expect(subjectiveScaleFromNormalized(60)).toBe(3)
    expect(subjectiveScaleFromNormalized(80)).toBe(4)
    expect(subjectiveScaleFromNormalized(100)).toBe(5)
  })

  it('returns null for a value outside the known conversion table', () => {
    expect(subjectiveScaleFromNormalized(50)).toBeNull()
  })
})
