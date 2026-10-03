import { describe, expect, it } from 'vitest'
import {
  resolveQuickBookDueDate,
  resolveQuickBookTotalPages,
  resolveQuickWorkExpectedContent,
} from './quickCreateGoalDefaults'

describe('resolveQuickBookTotalPages', () => {
  it('returns 1 when left blank', () => {
    expect(resolveQuickBookTotalPages('')).toBe(1)
  })

  it('returns the entered number otherwise', () => {
    expect(resolveQuickBookTotalPages('250')).toBe(250)
  })
})

describe('resolveQuickBookDueDate', () => {
  it('adds the default 90 days to the start date', () => {
    expect(resolveQuickBookDueDate('2026-01-01')).toBe('2026-04-01')
  })

  it('supports a custom number of days', () => {
    expect(resolveQuickBookDueDate('2026-01-01', 10)).toBe('2026-01-11')
  })
})

describe('resolveQuickWorkExpectedContent', () => {
  it('falls back to the goal name when left blank', () => {
    expect(resolveQuickWorkExpectedContent('', '新規案件')).toBe('新規案件')
  })

  it('keeps the entered summary otherwise', () => {
    expect(resolveQuickWorkExpectedContent('保守運用を担当', '新規案件')).toBe('保守運用を担当')
  })
})
