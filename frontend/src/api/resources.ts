import { apiClient, ApiError } from './client'
import { t } from '../locales/t'
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

const BASE_URL = '/api/v1'

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

/** 収録済みの祝日の年の範囲を取得する（D-46「収録済みの年の範囲」表示）。 */
export function getHolidayCoverage(): Promise<HolidayListRead> {
  return apiClient.get<HolidayListRead>('/holidays')
}

/**
 * 内閣府CSVを手動で取り込む（既存の`POST /calendar/holidays/import`、D-46）。
 * multipart/form-dataで送るため、JSON専用のapiClientではなく個別にfetchする
 * （`api/data.ts`のimportDataFileと同じ方式）。
 */
export async function importHolidaysFile(file: File): Promise<HolidayImportResultRead> {
  const formData = new FormData()
  formData.append('file', file)

  let response: Response
  try {
    response = await fetch(`${BASE_URL}/calendar/holidays/import`, {
      method: 'POST',
      body: formData,
    })
  } catch {
    throw new ApiError('NETWORK_ERROR', t('errors.NETWORK_ERROR'))
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      error?: { code?: string; message?: string; details?: unknown[] }
    } | null
    const error = body?.error
    throw new ApiError(
      error?.code ?? 'INTERNAL_ERROR',
      error?.message ?? t('errors.default'),
      error?.details ?? [],
    )
  }
  return response.json() as Promise<HolidayImportResultRead>
}
