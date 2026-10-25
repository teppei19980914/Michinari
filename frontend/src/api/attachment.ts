import { apiClient, ApiError } from './client'
import { t } from '../locales/t'
import type { components } from '../types/api.d.ts'

export type AttachmentRead = components['schemas']['AttachmentRead']
export type AttachmentLimits = components['schemas']['AttachmentLimitsRead']

const BASE_URL = '/api/v1'

/**
 * PDFをアップロードし、テキスト抽出して登録する（開発Todo_添付ファイル機能_v1.0 A2・A3・
 * A4）。multipart/form-dataで送るため、JSON専用のapiClientではなく個別にfetchする
 * （`api/data.ts`のimportDataFileと同じ方式）。
 */
export async function uploadAttachment(file: File): Promise<AttachmentRead> {
  const formData = new FormData()
  formData.append('file', file)

  let response: Response
  try {
    response = await fetch(`${BASE_URL}/attachments`, { method: 'POST', body: formData })
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
  return response.json() as Promise<AttachmentRead>
}

/** 登録順（id昇順）で一覧を取得する。 */
export function listAttachments(): Promise<AttachmentRead[]> {
  return apiClient.get<AttachmentRead[]>('/attachments')
}

/** 添付ファイルを削除する（常に削除を許可する、A1・P3）。 */
export function deleteAttachment(attachmentId: number): Promise<void> {
  return apiClient.delete<void>(`/attachments/${attachmentId}`)
}

/** 画面が表示・事前チェックに使う上限を取得する（A7・A10・P1）。 */
export function getAttachmentLimits(): Promise<AttachmentLimits> {
  return apiClient.get<AttachmentLimits>('/attachments/limits')
}
