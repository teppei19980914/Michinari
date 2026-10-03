import { describe, expect, it } from 'vitest'
import { canArchiveGoal, isClosedGoalStatus, resolveGoalListTarget } from './goalStatus'

describe('isClosedGoalStatus', () => {
  it('returns false for DRAFT/ACTIVE/PAUSED', () => {
    expect(isClosedGoalStatus('DRAFT')).toBe(false)
    expect(isClosedGoalStatus('ACTIVE')).toBe(false)
    expect(isClosedGoalStatus('PAUSED')).toBe(false)
  })

  it('returns true for both closed statuses', () => {
    expect(isClosedGoalStatus('CLOSED_WITH_RESULT')).toBe(true)
    expect(isClosedGoalStatus('CLOSED_WITHOUT_RESULT')).toBe(true)
  })
})

describe('resolveGoalListTarget', () => {
  it('routes to the goal detail screen when not closed', () => {
    expect(resolveGoalListTarget(1, 'ACTIVE')).toBe('/goals/1')
  })

  it('routes to the export placeholder when closed', () => {
    expect(resolveGoalListTarget(1, 'CLOSED_WITH_RESULT')).toBe('/goals/1/export')
    expect(resolveGoalListTarget(1, 'CLOSED_WITHOUT_RESULT')).toBe('/goals/1/export')
  })
})

describe('canArchiveGoal', () => {
  it('returns false for ACTIVE (進行中はアーカイブ不可)', () => {
    expect(canArchiveGoal('ACTIVE', null)).toBe(false)
  })

  it('returns true for non-active statuses that are not yet archived', () => {
    expect(canArchiveGoal('DRAFT', null)).toBe(true)
    expect(canArchiveGoal('PAUSED', null)).toBe(true)
    expect(canArchiveGoal('CLOSED_WITH_RESULT', null)).toBe(true)
    expect(canArchiveGoal('CLOSED_WITHOUT_RESULT', null)).toBe(true)
  })

  it('returns false when already archived', () => {
    expect(canArchiveGoal('CLOSED_WITH_RESULT', '2026-08-30T00:00:00')).toBe(false)
    expect(canArchiveGoal('DRAFT', '2026-08-30T00:00:00')).toBe(false)
  })
})
