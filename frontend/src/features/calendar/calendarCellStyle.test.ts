import { describe, expect, it } from 'vitest'
import { resolveCalendarCellBackgroundClass, resolveCalendarCellMarkerKey } from './calendarCellStyle'

describe('resolveCalendarCellBackgroundClass', () => {
  it('maps each day type to a distinct background class', () => {
    const plan = resolveCalendarCellBackgroundClass('PLAN')
    const buffer = resolveCalendarCellBackgroundClass('BUFFER')
    const off = resolveCalendarCellBackgroundClass('OFF')

    expect(new Set([plan, buffer, off]).size).toBe(3)
  })
})

describe('resolveCalendarCellMarkerKey', () => {
  it('maps an unreported day (null) to the unreported marker', () => {
    expect(resolveCalendarCellMarkerKey(null)).toBe('calendar.marker.unreported')
  })

  it('maps PROGRESS_ONLY to the progress-only marker', () => {
    expect(resolveCalendarCellMarkerKey('PROGRESS_ONLY')).toBe('calendar.marker.progressOnly')
  })

  it('maps REPORTED to the reported marker', () => {
    expect(resolveCalendarCellMarkerKey('REPORTED')).toBe('calendar.marker.reported')
  })
})
