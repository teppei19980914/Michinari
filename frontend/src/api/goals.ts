import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type GoalRead = components['schemas']['GoalRead']
export type GoalDetailRead = components['schemas']['GoalDetailRead']
export type GoalCreate = components['schemas']['GoalCreate']
export type GoalUpdate = components['schemas']['GoalUpdate']
export type GoalCloseRequest = components['schemas']['GoalCloseRequest']
export type PlanBaselineRead = components['schemas']['PlanBaselineRead']
export type SubjectRead = components['schemas']['SubjectRead']
export type SubjectCreate = components['schemas']['SubjectCreate']
export type SubjectUpdate = components['schemas']['SubjectUpdate']
export type MaterialRead = components['schemas']['MaterialRead']
export type MaterialCreate = components['schemas']['MaterialCreate']
export type MaterialUpdate = components['schemas']['MaterialUpdate']
export type MaterialCycleProgressRead = components['schemas']['MaterialCycleProgressRead']
export type LoadProfileRead = components['schemas']['LoadProfileRead']
export type LoadProfileCreate = components['schemas']['LoadProfileCreate']
export type LoadProfileUpdate = components['schemas']['LoadProfileUpdate']

export function listGoals(): Promise<GoalRead[]> {
  return apiClient.get<GoalRead[]>('/goals')
}

export function createGoal(payload: GoalCreate): Promise<GoalRead> {
  return apiClient.post<GoalRead>('/goals', payload)
}

export function getGoal(goalId: number): Promise<GoalDetailRead> {
  return apiClient.get<GoalDetailRead>(`/goals/${goalId}`)
}

export function updateGoal(goalId: number, payload: GoalUpdate): Promise<GoalRead> {
  return apiClient.patch<GoalRead>(`/goals/${goalId}`, payload)
}

export function deleteGoal(goalId: number): Promise<void> {
  return apiClient.delete<void>(`/goals/${goalId}`)
}

export function activateGoal(goalId: number): Promise<GoalRead> {
  return apiClient.post<GoalRead>(`/goals/${goalId}/activate`)
}

export function pauseGoal(goalId: number): Promise<GoalRead> {
  return apiClient.post<GoalRead>(`/goals/${goalId}/pause`)
}

export function resumeGoal(goalId: number): Promise<GoalRead> {
  return apiClient.post<GoalRead>(`/goals/${goalId}/resume`)
}

export function closeGoal(goalId: number, payload: GoalCloseRequest): Promise<GoalRead> {
  return apiClient.post<GoalRead>(`/goals/${goalId}/close`, payload)
}

export function getBaselines(goalId: number): Promise<PlanBaselineRead[]> {
  return apiClient.get<PlanBaselineRead[]>(`/goals/${goalId}/baselines`)
}

export function createSubject(goalId: number, payload: SubjectCreate): Promise<SubjectRead> {
  return apiClient.post<SubjectRead>(`/goals/${goalId}/subjects`, payload)
}

export function updateSubject(subjectId: number, payload: SubjectUpdate): Promise<SubjectRead> {
  return apiClient.patch<SubjectRead>(`/subjects/${subjectId}`, payload)
}

export function deleteSubject(subjectId: number): Promise<void> {
  return apiClient.delete<void>(`/subjects/${subjectId}`)
}

export function fixSubjectDate(subjectId: number, examDateFixed: string): Promise<SubjectRead> {
  return apiClient.post<SubjectRead>(`/subjects/${subjectId}/fix-date`, {
    exam_date_fixed: examDateFixed,
  })
}

export function createMaterial(goalId: number, payload: MaterialCreate): Promise<MaterialRead> {
  return apiClient.post<MaterialRead>(`/goals/${goalId}/materials`, payload)
}

export function updateMaterial(
  materialId: number,
  payload: MaterialUpdate,
): Promise<MaterialRead> {
  return apiClient.patch<MaterialRead>(`/materials/${materialId}`, payload)
}

export function deleteMaterial(materialId: number): Promise<void> {
  return apiClient.delete<void>(`/materials/${materialId}`)
}

export function deactivateMaterial(materialId: number): Promise<MaterialRead> {
  return apiClient.post<MaterialRead>(`/materials/${materialId}/deactivate`)
}

export function getMaterialCycleProgress(
  materialId: number,
): Promise<MaterialCycleProgressRead[]> {
  return apiClient.get<MaterialCycleProgressRead[]>(`/materials/${materialId}/cycles`)
}

export function listLoadProfiles(goalId: number): Promise<LoadProfileRead[]> {
  return apiClient.get<LoadProfileRead[]>(`/goals/${goalId}/load-profiles`)
}

export function createLoadProfile(
  goalId: number,
  payload: LoadProfileCreate,
): Promise<LoadProfileRead> {
  return apiClient.post<LoadProfileRead>(`/goals/${goalId}/load-profiles`, payload)
}

export function updateLoadProfile(
  loadProfileId: number,
  payload: LoadProfileUpdate,
): Promise<LoadProfileRead> {
  return apiClient.patch<LoadProfileRead>(`/load-profiles/${loadProfileId}`, payload)
}

export function deleteLoadProfile(loadProfileId: number): Promise<void> {
  return apiClient.delete<void>(`/load-profiles/${loadProfileId}`)
}
