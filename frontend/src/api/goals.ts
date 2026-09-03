import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type GoalRead = components['schemas']['GoalRead']
export type GoalDetailRead = components['schemas']['GoalDetailRead']
export type GoalCreate = components['schemas']['GoalCreate']
export type GoalUpdate = components['schemas']['GoalUpdate']
export type GoalCloseRequest = components['schemas']['GoalCloseRequest']
export type GoalDeleteArchivedRequest = components['schemas']['GoalDeleteArchivedRequest']
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
export type GoalCategory = components['schemas']['GoalCategory']
export type BookRead = components['schemas']['BookRead']
export type BookCreate = components['schemas']['BookCreate']
export type BookUpdate = components['schemas']['BookUpdate']

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

export function archiveGoal(goalId: number): Promise<GoalRead> {
  return apiClient.patch<GoalRead>(`/goals/${goalId}/archive`)
}

export function unarchiveGoal(goalId: number): Promise<GoalRead> {
  return apiClient.patch<GoalRead>(`/goals/${goalId}/unarchive`)
}

export function deleteArchivedGoal(
  goalId: number,
  payload: GoalDeleteArchivedRequest,
): Promise<void> {
  return apiClient.delete<void>(`/goals/${goalId}/archived`, payload)
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

export function createBook(goalId: number, payload: BookCreate): Promise<BookRead> {
  return apiClient.post<BookRead>(`/goals/${goalId}/book`, payload)
}

export function updateBook(bookId: number, payload: BookUpdate): Promise<BookRead> {
  return apiClient.patch<BookRead>(`/books/${bookId}`, payload)
}

/** 読了として記録する（仕様書6.2「読了操作」）。目標をCLOSED_WITH_RESULTへ遷移させる。 */
export function completeBook(bookId: number): Promise<GoalRead> {
  return apiClient.post<GoalRead>(`/books/${bookId}/complete`)
}

/**
 * 進行中の読書目標とその書籍を一覧する（日次報告画面・ダッシュボード補助表示で使用）。
 * バックエンドに一括取得用のエンドポイントが無いため、目標一覧からREADING×ACTIVEを
 * 絞り込み、書籍情報（GoalDetailRead.book）を目標ごとに取得して合成する。進行中の読書目標は
 * 少数（1目標1冊、通常は1〜数件）であることを前提とした構成であり、件数が多い場合はN+1になる
 * （CLAUDE.md パフォーマンスチェックの原則上は望ましくないが、専用集約エンドポイントを
 * 新設するほどの規模ではないと判断した。Phase17実装時の判断）。
 */
export async function listActiveReadingBooks(): Promise<{ goal: GoalRead; book: BookRead }[]> {
  const goals = await listGoals()
  const activeReadingGoals = goals.filter((g) => g.category === 'READING' && g.status === 'ACTIVE')
  const details = await Promise.all(activeReadingGoals.map((g) => getGoal(g.id)))
  return details
    .filter((detail): detail is GoalDetailRead & { book: BookRead } => detail.book !== null)
    .map((detail) => ({ goal: detail, book: detail.book }))
}
