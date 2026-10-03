import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type ResourceSlotRead = components['schemas']['ResourceSlotRead']
export type ResourceSlotCreate = components['schemas']['ResourceSlotCreate']
export type ResourceSlotUpdate = components['schemas']['ResourceSlotUpdate']
export type AllocationStatusRead = components['schemas']['AllocationStatusRead']
export type DayType = components['schemas']['DayType']
export type DayBoundaryHourRead = components['schemas']['DayBoundaryHourRead']
export type HolidayTreatAsBufferRead = components['schemas']['HolidayTreatAsBufferRead']

export function listSlots(): Promise<ResourceSlotRead[]> {
  return apiClient.get<ResourceSlotRead[]>('/resources/slots')
}

export function createSlot(payload: ResourceSlotCreate): Promise<ResourceSlotRead> {
  return apiClient.post<ResourceSlotRead>('/resources/slots', payload)
}

export function updateSlot(
  slotId: number,
  payload: ResourceSlotUpdate,
): Promise<ResourceSlotRead> {
  return apiClient.patch<ResourceSlotRead>(`/resources/slots/${slotId}`, payload)
}

export function deleteSlot(slotId: number): Promise<void> {
  return apiClient.delete<void>(`/resources/slots/${slotId}`)
}

export function getAllocation(): Promise<AllocationStatusRead> {
  return apiClient.get<AllocationStatusRead>('/resources/allocation')
}

export function getDayTypeDefaults(): Promise<Record<number, DayType>> {
  return apiClient.get<Record<number, DayType>>('/resources/day-type-defaults')
}

export function updateDayTypeDefaults(
  values: Record<number, DayType>,
): Promise<Record<number, DayType>> {
  return apiClient.put<Record<number, DayType>>('/resources/day-type-defaults', values)
}

export function getDayBoundaryHour(): Promise<DayBoundaryHourRead> {
  return apiClient.get<DayBoundaryHourRead>('/resources/day-boundary-hour')
}

export function updateDayBoundaryHour(hour: number): Promise<DayBoundaryHourRead> {
  return apiClient.put<DayBoundaryHourRead>('/resources/day-boundary-hour', {
    day_boundary_hour: hour,
  })
}

export function getHolidayTreatAsBuffer(): Promise<HolidayTreatAsBufferRead> {
  return apiClient.get<HolidayTreatAsBufferRead>('/resources/holiday-treat-as-buffer')
}

export function updateHolidayTreatAsBuffer(
  treatAsBuffer: boolean,
): Promise<HolidayTreatAsBufferRead> {
  return apiClient.put<HolidayTreatAsBufferRead>('/resources/holiday-treat-as-buffer', {
    treat_as_buffer: treatAsBuffer,
  })
}
