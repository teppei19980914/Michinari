import { describe, expect, it } from 'vitest'
import { CHARACTER_ICONS } from '../../constants/characterIcons'
import { resolveScheduleStatus, resolveScheduleStatusIcon } from './scheduleStatus'

describe('resolveScheduleStatus', () => {
  it('returns null when the deviation is unavailable', () => {
    expect(resolveScheduleStatus(null)).toBeNull()
  })

  it('returns delayed when the forecast is behind schedule (positive days)', () => {
    expect(resolveScheduleStatus(3)).toBe('delayed')
  })

  it('returns ahead when the forecast is ahead of schedule (negative days)', () => {
    expect(resolveScheduleStatus(-2)).toBe('ahead')
  })

  it('returns onTrack when the forecast exactly matches the due date (zero)', () => {
    expect(resolveScheduleStatus(0)).toBe('onTrack')
  })
})

describe('resolveScheduleStatusIcon', () => {
  it('returns null when the deviation is unavailable', () => {
    expect(resolveScheduleStatusIcon(null)).toBeNull()
  })

  it.each([
    [3, CHARACTER_ICONS.scheduleDelayed],
    [-2, CHARACTER_ICONS.scheduleAhead],
    [0, CHARACTER_ICONS.scheduleOnTrack],
  ])('maps %s days to its UI-02/03/04 icon', (days, expected) => {
    expect(resolveScheduleStatusIcon(days)).toBe(expected)
  })
})
