import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type SystemInfoRead = components['schemas']['SystemInfoRead']

export function getSystemInfo(): Promise<SystemInfoRead> {
  return apiClient.get<SystemInfoRead>('/system-info')
}
