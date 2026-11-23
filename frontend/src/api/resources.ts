import { apiClient, postMultipart } from './client'
import type { components } from '../types/api.d.ts'

export type ResourceSlotRead = components['schemas']['ResourceSlotRead']
export type ResourceSlotCreate = components['schemas']['ResourceSlotCreate']
export type ResourceSlotUpdate = components['schemas']['ResourceSlotUpdate']
export type AllocationStatusRead = components['schemas']['AllocationStatusRead']
export type DayType = components['schemas']['DayType']
export type DayBoundaryHourRead = components['schemas']['DayBoundaryHourRead']
export type HolidayTreatAsBufferRead = components['schemas']['HolidayTreatAsBufferRead']
export type HolidayListRead = components['schemas']['HolidayListRead']
export type HolidayImportResultRead = components['schemas']['HolidayImportResultRead']

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

/**
 * 祝日を取得する（D-46「収録済みの年の範囲」表示、D-45スケジュールタブのガント）。
 * `dateFrom`・`dateTo`を省略した場合は`holidays`は空配列、`year_from`/`year_to`
 * （収録範囲）のみを返す（リソース設定画面の表示はこの用法、`GET /holidays`は単位1で
 * 期間を省略可能として実装済み）。
 */
export function getHolidayCoverage(dateFrom?: string, dateTo?: string): Promise<HolidayListRead> {
  const query =
    dateFrom && dateTo ? `?date_from=${dateFrom}&date_to=${dateTo}` : ''
  return apiClient.get<HolidayListRead>(`/holidays${query}`)
}

/**
 * 内閣府CSVを手動で取り込む（既存の`POST /calendar/holidays/import`、D-46）。
 * multipart/form-dataで送るため、JSON専用のapiClientではなく`postMultipart`を使う。
 */
export function importHolidaysFile(file: File): Promise<HolidayImportResultRead> {
  const formData = new FormData()
  formData.append('file', file)
  return postMultipart<HolidayImportResultRead>('/calendar/holidays/import', formData)
}
