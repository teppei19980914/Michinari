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
export type ScheduleRevisionTrigger = components['schemas']['ScheduleRevisionTrigger']
export type ScheduleRevisionGenerateRequest = components['schemas']['ScheduleRevisionGenerateRequest']
export type ScheduleRevisionGenerateResult = components['schemas']['ScheduleRevisionGenerateResult']
export type ScheduleRevisionProposalRead = components['schemas']['ScheduleRevisionProposalRead']
export type ScheduleRevisionProposalItemRead =
  components['schemas']['ScheduleRevisionProposalItemRead']
export type ScheduleRevisionItemKind = components['schemas']['ScheduleRevisionItemKind']
export type ScheduleRevisionDecision = components['schemas']['ScheduleRevisionDecision']
export type ScheduleRevisionDecisionInput = components['schemas']['ScheduleRevisionDecisionInput']
export type ScheduleRevisionDecisionsRequest =
  components['schemas']['ScheduleRevisionDecisionsRequest']
export type ScheduleRevisionDecisionsResponse =
  components['schemas']['ScheduleRevisionDecisionsResponse']

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

/** AIによるスケジュール修正案の生成（開発Todo_スケジュール・ガントチャート_v1.1 13.7、単位5）。 */
export function generateScheduleRevisionProposal(
  goalId: number,
  payload: ScheduleRevisionGenerateRequest,
): Promise<ScheduleRevisionGenerateResult> {
  return apiClient.post<ScheduleRevisionGenerateResult>(
    `/goals/${goalId}/schedule/revision-proposals`,
    payload,
  )
}

/** 修正案の行ごとの判断（承認・却下・確認済み、13.7）。 */
export function decideScheduleRevisionProposal(
  goalId: number,
  proposalId: number,
  payload: ScheduleRevisionDecisionsRequest,
): Promise<ScheduleRevisionDecisionsResponse> {
  return apiClient.post<ScheduleRevisionDecisionsResponse>(
    `/goals/${goalId}/schedule/revision-proposals/${proposalId}/decisions`,
    payload,
  )
}
