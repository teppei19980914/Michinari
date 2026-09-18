import { describe, expect, it } from 'vitest'
import { resolveWeekdaySlotTimes, resolveWeekendSlotTimes } from './simpleTimeSlots'

describe('resolveWeekdaySlotTimes', () => {
  it('matches the example in the specification (2 hours -> 20:00-22:00)', () => {
    expect(resolveWeekdaySlotTimes(2)).toEqual({
      startTime: '20:00',
      endTime: '22:00',
      clamped: false,
    })
  })

  it('clamps to 23:59 when the input would cross midnight', () => {
    expect(resolveWeekdaySlotTimes(5)).toEqual({
      startTime: '20:00',
      endTime: '23:59',
      clamped: true,
    })
  })
})

describe('resolveWeekendSlotTimes', () => {
  it('starts at 09:00', () => {
    expect(resolveWeekendSlotTimes(3)).toEqual({
      startTime: '09:00',
      endTime: '12:00',
      clamped: false,
    })
  })

  it('clamps to 23:59 when the input would cross midnight', () => {
    expect(resolveWeekendSlotTimes(16)).toEqual({
      startTime: '09:00',
      endTime: '23:59',
      clamped: true,
    })
  })
})
