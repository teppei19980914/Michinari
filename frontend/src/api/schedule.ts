import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type ScheduleRead = components['schemas']['ScheduleRead']
export type ScheduleSaveRequest = components['schemas']['ScheduleSaveRequest']
export type ScheduleItemInput = components['schemas']['ScheduleItemInput']
export type ScheduleColumnInput = components['schemas']['ScheduleColumnInput']
export type ScheduleItemRead = components['schemas']['ScheduleItemRead']
export type ScheduleColumnRead = components['schemas']['ScheduleColumnRead']
export type ScheduleItemStatus = components['schemas']['ScheduleItemStatus']
export type ScheduleViewSettingUpdate = components['schemas']['ScheduleViewSettingUpdate']
export type ScheduleViewSettingRead = components['schemas']['ScheduleViewSettingRead']

export function getSchedule(goalId: number): Promise<ScheduleRead> {
  return apiClient.get<ScheduleRead>(`/goals/${goalId}/schedule`)
}

export function saveSchedule(
  goalId: number,
  payload: ScheduleSaveRequest,
): Promise<ScheduleRead> {
  return apiClient.put<ScheduleRead>(`/goals/${goalId}/schedule`, payload)
}

export function updateScheduleViewSetting(
  goalId: number,
  payload: ScheduleViewSettingUpdate,
): Promise<ScheduleViewSettingRead> {
  return apiClient.put<ScheduleViewSettingRead>(`/goals/${goalId}/schedule/view-setting`, payload)
}
