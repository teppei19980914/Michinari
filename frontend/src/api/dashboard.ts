import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type DashboardRead = components['schemas']['DashboardRead']

export function getDashboard(): Promise<DashboardRead> {
  return apiClient.get<DashboardRead>('/dashboard')
}
