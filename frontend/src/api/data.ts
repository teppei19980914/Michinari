import { apiClient, ApiError } from './client'
import { t } from '../locales/t'
import type { components } from '../types/api.d.ts'

export type BackupRead = components['schemas']['BackupRead']

const BASE_URL = '/api/v1'

export function listBackups(): Promise<BackupRead[]> {
  return apiClient.get<BackupRead[]>('/data/backups')
}

export function createBackup(): Promise<BackupRead> {
  return apiClient.post<BackupRead>('/data/backup')
}

export function restoreBackup(backupId: string): Promise<void> {
  return apiClient.post<void>(`/data/backups/${backupId}/restore`)
}

/**
 * 全データのエクスポート（仕様書6.12）。レスポンスをファイルとしてダウンロードさせる
 * （ブラウザへの保存はDataManagementPage側のdownloadBlobが行う）ため、
 * JSONを自動パースするapiClientではなく個別にfetchしBlobのまま扱う。
 */
export async function downloadExportFile(): Promise<Blob> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}/data/export`)
  } catch {
    throw new ApiError('NETWORK_ERROR', t('errors.NETWORK_ERROR'))
  }
  if (!response.ok) {
    throw new ApiError('INTERNAL_ERROR', t('errors.default'))
  }
  return response.blob()
}

/**
 * データのインポート（仕様書6.12）。multipart/form-dataで送るため、
 * JSON専用のapiClientではなく個別にfetchする。
 */
export async function importDataFile(file: File): Promise<void> {
  const formData = new FormData()
  formData.append('file', file)

  let response: Response
  try {
    response = await fetch(`${BASE_URL}/data/import`, { method: 'POST', body: formData })
  } catch {
    throw new ApiError('NETWORK_ERROR', t('errors.NETWORK_ERROR'))
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      error?: { code?: string; message?: string; details?: unknown[] }
    } | null
    const error = body?.error
    throw new ApiError(
      error?.code ?? 'INTERNAL_ERROR',
      error?.message ?? t('errors.default'),
      error?.details ?? [],
    )
  }
}
