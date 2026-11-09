import { describe, expect, it } from 'vitest'
import {
  buildOnThisDaySettingsPayload,
  isValidCandidateMonthsAgo,
  resolveOnThisDaySettingsGuard,
  type OnThisDaySettingsDraft,
} from './onThisDaySettings'

const VALID_DRAFT: OnThisDaySettingsDraft = {
  enabled: true,
  candidateMonthsAgo: '1,6,12',
  showProbability: 0.3,
  bodyPreviewChars: 100,
}

describe('isValidCandidateMonthsAgo', () => {
  it.each(['1', '1,6,12', ' 1 , 6 , 12 '])('accepts %s', (value) => {
    expect(isValidCandidateMonthsAgo(value)).toBe(true)
  })

  it.each(['', '1,,6', '1,abc', '-1'])('rejects %s', (value) => {
    expect(isValidCandidateMonthsAgo(value)).toBe(false)
  })
})

describe('resolveOnThisDaySettingsGuard', () => {
  it('allows saving a valid draft', () => {
    expect(resolveOnThisDaySettingsGuard(VALID_DRAFT)).toEqual({
      canSubmit: true,
      errorKey: null,
    })
  })

  it('blocks saving when candidateMonthsAgo is malformed', () => {
    expect(
      resolveOnThisDaySettingsGuard({ ...VALID_DRAFT, candidateMonthsAgo: '1,,6' }),
    ).toEqual({
      canSubmit: false,
      errorKey: 'settings.onThisDay.candidateMonthsAgoInvalid',
    })
  })

  it.each([-0.1, 1.1])('blocks saving when showProbability is out of range (%s)', (value) => {
    expect(resolveOnThisDaySettingsGuard({ ...VALID_DRAFT, showProbability: value })).toEqual({
      canSubmit: false,
      errorKey: 'settings.onThisDay.showProbabilityInvalid',
    })
  })

  it.each([0, 1])('allows showProbability at the boundary (%s)', (value) => {
    expect(
      resolveOnThisDaySettingsGuard({ ...VALID_DRAFT, showProbability: value }).canSubmit,
    ).toBe(true)
  })

  it.each([0, -1, 1.5])('blocks saving when bodyPreviewChars is invalid (%s)', (value) => {
    expect(resolveOnThisDaySettingsGuard({ ...VALID_DRAFT, bodyPreviewChars: value })).toEqual({
      canSubmit: false,
      errorKey: 'settings.onThisDay.bodyPreviewCharsInvalid',
    })
  })
})

describe('buildOnThisDaySettingsPayload', () => {
  it('maps every field to its snake_case API key', () => {
    expect(buildOnThisDaySettingsPayload(VALID_DRAFT)).toEqual({
      enabled: true,
      candidate_months_ago: '1,6,12',
      show_probability: 0.3,
      body_preview_chars: 100,
    })
  })
})
