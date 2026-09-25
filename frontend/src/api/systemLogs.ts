import { ApiError } from './client'
import { t } from '../locales/t'

const BASE_URL = '/api/v1'

/**
 * 期間指定で診断ログをダウンロードする（仕様書6.14 SC-15、Phase40 診断ログ出力）。
 * レスポンスが`text/plain`のためJSONを自動パースする`apiClient`ではなく個別にfetchし、
 * Blobのまま扱う（`api/data.ts`の`downloadExportFile`と同じパターン）。
 */
export async function downloadLogExport(dateFrom: string, dateTo: string): Promise<Blob> {
  let response: Response
  try {
    response = await fetch(
      `${BASE_URL}/system-info/logs/export?date_from=${dateFrom}&date_to=${dateTo}`,
    )
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
  return response.blob()
}
