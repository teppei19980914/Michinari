import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type AppSettingsRead = components['schemas']['AppSettingsRead']
export type AppSettingsUpdate = components['schemas']['AppSettingsUpdate']
export type PromptTemplateRead = components['schemas']['PromptTemplateRead']
export type AiPurpose = components['schemas']['AiPurpose']

export function getSettings(): Promise<AppSettingsRead> {
  return apiClient.get<AppSettingsRead>('/settings')
}

export function updateSettings(payload: AppSettingsUpdate): Promise<AppSettingsRead> {
  return apiClient.patch<AppSettingsRead>('/settings', payload)
}

export function listPromptTemplates(): Promise<PromptTemplateRead[]> {
  return apiClient.get<PromptTemplateRead[]>('/prompt-templates')
}

export function updatePromptTemplate(
  purpose: AiPurpose,
  body: string,
): Promise<PromptTemplateRead> {
  return apiClient.patch<PromptTemplateRead>(`/prompt-templates/${purpose}`, { body })
}

export function resetPromptTemplate(purpose: AiPurpose): Promise<PromptTemplateRead> {
  return apiClient.post<PromptTemplateRead>(`/prompt-templates/${purpose}/reset`)
}
