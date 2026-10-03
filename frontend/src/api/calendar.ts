import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type CalendarDayRead = components['schemas']['CalendarDayRead']
export type DayType = components['schemas']['DayType']
export type DayTypeOverrideRequest = components['schemas']['DayTypeOverrideRequest']

/** 指定期間のカレンダー表示情報（日種別・記録状態）を取得する（仕様書6.4 SC-05）。 */
export function getCalendar(dateFrom: string, dateTo: string): Promise<CalendarDayRead[]> {
  return apiClient.get<CalendarDayRead[]>(
    `/calendar?date_from=${dateFrom}&date_to=${dateTo}`,
  )
}

export function setDayType(
  targetDate: string,
  payload: DayTypeOverrideRequest,
): Promise<CalendarDayRead> {
  return apiClient.put<CalendarDayRead>(`/calendar/${targetDate}/day-type`, payload)
}

export function clearDayType(targetDate: string): Promise<void> {
  return apiClient.delete<void>(`/calendar/${targetDate}/day-type`)
}
