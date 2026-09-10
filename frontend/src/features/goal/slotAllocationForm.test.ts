import { describe, expect, it } from 'vitest'
import {
  buildSlotAllocationPayload,
  exceedsFreeMinutes,
  freeMinutes,
  initSlotAllocationValues,
  parseMinutes,
  totalMinutes,
} from './slotAllocationForm'
import type { SlotAllocationRead } from '../../api/goals'

const ROW: SlotAllocationRead = {
  slot_id: 10,
  slot_name: '夜',
  environment: 'PC',
  weekdays: [0, 1, 2, 3, 4],
  duration_minutes: 120,
  minutes: 30,
  others_minutes: 40,
  is_over_capacity: false,
}

const UNALLOCATED: SlotAllocationRead = { ...ROW, slot_id: 11, slot_name: '通勤', minutes: 0 }

describe('initSlotAllocationValues', () => {
  it('shows an empty field for a slot with no allocation', () => {
    expect(initSlotAllocationValues([ROW, UNALLOCATED])).toEqual({ 10: '30', 11: '' })
  })
})

describe('parseMinutes', () => {
  it('treats blank, non-numeric and non-positive input as 0', () => {
    expect(parseMinutes('')).toBe(0)
    expect(parseMinutes(undefined)).toBe(0)
    expect(parseMinutes('abc')).toBe(0)
    expect(parseMinutes('-5')).toBe(0)
  })

  it('floors a fractional entry (配分は分の整数で扱う)', () => {
    expect(parseMinutes('30.9')).toBe(30)
  })
})

describe('freeMinutes', () => {
  it('is the slot duration minus the other goals allocation', () => {
    expect(freeMinutes(ROW)).toBe(80)
  })
})

describe('exceedsFreeMinutes', () => {
  it('is false while the entry fits in the free time', () => {
    expect(exceedsFreeMinutes(ROW, '80')).toBe(false)
  })

  it('is true once the entry passes the free time (仕様書NT-04の保存拒否を事前に示す)', () => {
    expect(exceedsFreeMinutes(ROW, '81')).toBe(true)
  })
})

describe('totalMinutes', () => {
  it('sums every entered slot', () => {
    expect(totalMinutes({ 10: '30', 11: '45', 12: '' })).toBe(75)
  })
})

describe('buildSlotAllocationPayload', () => {
  it('sends 0 for cleared slots so that the server deletes those rows', () => {
    expect(buildSlotAllocationPayload([ROW, UNALLOCATED], { 10: '60', 11: '' })).toEqual({
      allocations: [
        { slot_id: 10, minutes: 60 },
        { slot_id: 11, minutes: 0 },
      ],
    })
  })
})
