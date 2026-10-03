import { describe, expect, it } from 'vitest'
import {
  buildSlotMinutesPayload,
  buildSlotRows,
  initSlotMinutes,
  sumSlotMinutes,
} from './slotMinutesForm'

const DEFAULTS = [
  { slot_id: 10, slot_name: '通勤', minutes: 20 },
  { slot_id: 11, slot_name: '夜', minutes: 40 },
]

describe('initSlotMinutes', () => {
  it('uses the allocation defaults when there is no existing log', () => {
    expect(initSlotMinutes(DEFAULTS, undefined)).toEqual({ 10: '20', 11: '40' })
  })

  it('prefers the existing breakdown over the defaults (その日の実績を優先する)', () => {
    const existing = [{ slot_id: 11, slot_name: '夜', minutes: 55 }]
    expect(initSlotMinutes(DEFAULTS, existing)).toEqual({ 11: '55' })
  })

  it('skips breakdown rows whose time slot was deleted (slot_id=null)', () => {
    const existing = [
      { slot_id: null, slot_name: null, minutes: 10 },
      { slot_id: 11, slot_name: '夜', minutes: 55 },
    ]
    expect(initSlotMinutes(DEFAULTS, existing)).toEqual({ 11: '55' })
  })
})

describe('buildSlotRows', () => {
  it('lists the allocated slots in slot id order', () => {
    expect(buildSlotRows(DEFAULTS, undefined, [], new Map())).toEqual([
      { slotId: 10, slotName: '通勤' },
      { slotId: 11, slotName: '夜' },
    ])
  })

  it('includes a slot the user added even when it is not allocated', () => {
    const slotNames = new Map([[12, '早朝']])
    expect(buildSlotRows(DEFAULTS, undefined, [12], slotNames)).toEqual([
      { slotId: 10, slotName: '通勤' },
      { slotId: 11, slotName: '夜' },
      { slotId: 12, slotName: '早朝' },
    ])
  })

  it('includes a slot that only the existing log refers to (配分を外した後の再編集)', () => {
    const existing = [{ slot_id: 13, slot_name: '昼休み', minutes: 15 }]
    expect(buildSlotRows([], existing, [], new Map())).toEqual([
      { slotId: 13, slotName: '昼休み' },
    ])
  })

  it('skips an existing entry that has no slot id (枠に紐づかない実績)', () => {
    const existing = [{ slot_id: null, slot_name: null, minutes: 30 }]
    expect(buildSlotRows(DEFAULTS, existing, [], new Map())).toEqual([
      { slotId: 10, slotName: '通勤' },
      { slotId: 11, slotName: '夜' },
    ])
  })

  it('does not duplicate a slot that both the defaults and the existing log refer to', () => {
    const existing = [{ slot_id: 10, slot_name: '通勤（旧名）', minutes: 20 }]
    // 配分側の名称を優先し、行は増やさない。
    expect(buildSlotRows(DEFAULTS, existing, [10], new Map())).toEqual([
      { slotId: 10, slotName: '通勤' },
      { slotId: 11, slotName: '夜' },
    ])
  })

  it('falls back to the slot name map, then to an empty name', () => {
    // slot_name が無い既存実績は、時間枠の一覧から名称を引く。それも無ければ空文字。
    const named = buildSlotRows([], [{ slot_id: 13, slot_name: null, minutes: 15 }], [], new Map([[13, '昼休み']]))
    expect(named).toEqual([{ slotId: 13, slotName: '昼休み' }])

    const unnamed = buildSlotRows([], [{ slot_id: 14, slot_name: null, minutes: 15 }], [], new Map())
    expect(unnamed).toEqual([{ slotId: 14, slotName: '' }])

    const addedUnknown = buildSlotRows([], undefined, [15], new Map())
    expect(addedUnknown).toEqual([{ slotId: 15, slotName: '' }])
  })
})

describe('sumSlotMinutes', () => {
  it('sums the entered minutes and ignores blank or invalid values', () => {
    expect(sumSlotMinutes({ 10: '20', 11: '', 12: 'abc', 13: '-5' })).toBe(20)
  })

  it('is zero when nothing was entered', () => {
    expect(sumSlotMinutes(undefined)).toBe(0)
  })
})

describe('buildSlotMinutesPayload', () => {
  it('omits blank and non-positive entries so that no breakdown row is created', () => {
    expect(buildSlotMinutesPayload({ 10: '20', 11: '', 12: '0' })).toEqual([
      { slot_id: 10, minutes: 20 },
    ])
  })

  it('is empty when every slot is blank (投下時間の未入力を表す)', () => {
    expect(buildSlotMinutesPayload({ 10: '', 11: '' })).toEqual([])
  })

  it('drops a non-numeric entry instead of sending NaN', () => {
    expect(buildSlotMinutesPayload({ 10: 'abc', 11: '30' })).toEqual([{ slot_id: 11, minutes: 30 }])
  })

  it('truncates fractional minutes', () => {
    expect(buildSlotMinutesPayload({ 10: '20.7' })).toEqual([{ slot_id: 10, minutes: 20 }])
  })

  it('returns an empty list when the whole value is undefined', () => {
    expect(buildSlotMinutesPayload(undefined)).toEqual([])
  })
})
