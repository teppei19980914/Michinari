import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type AiStatusRead = components['schemas']['AiStatusRead']
export type AiAssistantRead = components['schemas']['AiAssistantRead']
export type AiLoginRequest = components['schemas']['AiLoginRequest']
export type AiLoginResult = components['schemas']['AiLoginResult']

export function getAiStatus(): Promise<AiStatusRead> {
  return apiClient.get<AiStatusRead>('/ai/status')
}

export function loginAi(payload: AiLoginRequest): Promise<AiLoginResult> {
  return apiClient.post<AiLoginResult>('/ai/login', payload)
}

export function logoutAi(): Promise<void> {
  return apiClient.post<void>('/ai/logout')
}

export function listAssistants(): Promise<AiAssistantRead[]> {
  return apiClient.get<AiAssistantRead[]>('/ai/assistants')
}
