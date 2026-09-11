import { describe, expect, it } from 'vitest'
import {
  buildPassingScorePayload,
  formatPassingScoreDisplay,
  initPassingScoreFormState,
} from './passingScore'

describe('initPassingScoreFormState', () => {
  it('defaults to PERCENTAGE with empty inputs when no subject is given', () => {
    expect(initPassingScoreFormState()).toEqual({
      type: 'PERCENTAGE',
      percentValue: '',
      rawScoreValue: '',
      rawMaxValue: '',
    })
  })

  it('restores percent input from a PERCENTAGE subject', () => {
    expect(
      initPassingScoreFormState({
        passing_score: 60,
        passing_score_type: 'PERCENTAGE',
        passing_score_max: null,
      }),
    ).toEqual({ type: 'PERCENTAGE', percentValue: '60', rawScoreValue: '', rawMaxValue: '' })
  })

  it('restores raw score and max from a RAW_SCORE subject', () => {
    expect(
      initPassingScoreFormState({
        passing_score: 700,
        passing_score_type: 'RAW_SCORE',
        passing_score_max: 1000,
      }),
    ).toEqual({ type: 'RAW_SCORE', percentValue: '', rawScoreValue: '700', rawMaxValue: '1000' })
  })

  it('treats a null passing_score as unset regardless of type', () => {
    expect(
      initPassingScoreFormState({
        passing_score: null,
        passing_score_type: 'RAW_SCORE',
        passing_score_max: null,
      }),
    ).toEqual({ type: 'RAW_SCORE', percentValue: '', rawScoreValue: '', rawMaxValue: '' })
  })
})

describe('buildPassingScorePayload', () => {
  it('builds a percentage payload and clears passing_score_max', () => {
    expect(
      buildPassingScorePayload({
        type: 'PERCENTAGE',
        percentValue: '60',
        rawScoreValue: '700',
        rawMaxValue: '1000',
      }),
    ).toEqual({ passing_score: 60, passing_score_type: 'PERCENTAGE', passing_score_max: null })
  })

  it('builds a raw score payload with both score and max', () => {
    expect(
      buildPassingScorePayload({
        type: 'RAW_SCORE',
        percentValue: '60',
        rawScoreValue: '700',
        rawMaxValue: '1000',
      }),
    ).toEqual({ passing_score: 700, passing_score_type: 'RAW_SCORE', passing_score_max: 1000 })
  })

  it('maps an empty string input to null', () => {
    expect(
      buildPassingScorePayload({
        type: 'PERCENTAGE',
        percentValue: '',
        rawScoreValue: '',
        rawMaxValue: '',
      }),
    ).toEqual({ passing_score: null, passing_score_type: 'PERCENTAGE', passing_score_max: null })
  })
})

describe('formatPassingScoreDisplay', () => {
  it('returns null when passing_score is not set', () => {
    expect(
      formatPassingScoreDisplay({
        passing_score: null,
        passing_score_type: 'PERCENTAGE',
        passing_score_max: null,
      }),
    ).toBeNull()
  })

  it('formats a PERCENTAGE subject as a percent value', () => {
    expect(
      formatPassingScoreDisplay({
        passing_score: 60,
        passing_score_type: 'PERCENTAGE',
        passing_score_max: null,
      }),
    ).toBe('60%')
  })

  it('formats a RAW_SCORE subject as score/max', () => {
    expect(
      formatPassingScoreDisplay({
        passing_score: 700,
        passing_score_type: 'RAW_SCORE',
        passing_score_max: 1000,
      }),
    ).toBe('700/1000点')
  })

  it('sends nulls when the raw-score fields are left blank', () => {
    // 未入力（空文字）を0ではなくnullとして送る経路の検証。
    expect(
      buildPassingScorePayload({
        type: 'RAW_SCORE',
        percentValue: '',
        rawScoreValue: '',
        rawMaxValue: '',
      }),
    ).toEqual({ passing_score: null, passing_score_type: 'RAW_SCORE', passing_score_max: null })
  })
})
