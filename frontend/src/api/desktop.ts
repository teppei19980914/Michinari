import { apiClient } from './client'
import type { components } from '../types/api.d.ts'

export type DesktopAutostartSyncResult = components['schemas']['DesktopAutostartSyncResult']

/**
 * 保存済みの`desktop.launch_at_login`を今すぐWindowsレジストリへ反映する
 * （開発Todo リマインド導線 D6）。設定の保存自体は`updateSettings`で行い、
 * このAPIは反映のみを行う。
 */
export function syncAutostart(): Promise<DesktopAutostartSyncResult> {
  return apiClient.post<DesktopAutostartSyncResult>('/desktop/autostart/sync')
}
