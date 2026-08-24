import { t } from '../locales/t'

/**
 * APIクライアント共通処理（技術選定書7.3「エラーコードのみを返し、文言はロケールファイルで
 * 管理する」）。バックエンドのエラー応答形式は backend/app/api/errors.py の
 * `{"error": {"code", "message", "details"}}` に準拠する。
 */

const BASE_URL = '/api/v1'

export class ApiError extends Error {
  readonly code: string
  readonly details: unknown[]

  constructor(code: string, message: string, details: unknown[] = []) {
    super(message)
    this.code = code
    this.details = details
  }

  /** エラーコードに対応するロケール文言（未登録コードは既定文言）。 */
  get localizedMessage(): string {
    const key = `errors.${this.code}`
    const localized = t(key)
    return localized === key ? t('errors.default') : localized
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    })
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

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

function _requestWithBody<T>(method: string, path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export const apiClient = {
  get: <T>(path: string): Promise<T> => request<T>(path),
  post: <T>(path: string, body?: unknown): Promise<T> => _requestWithBody<T>('POST', path, body),
  patch: <T>(path: string, body?: unknown): Promise<T> => _requestWithBody<T>('PATCH', path, body),
  put: <T>(path: string, body?: unknown): Promise<T> => _requestWithBody<T>('PUT', path, body),
  delete: <T>(path: string): Promise<T> => request<T>(path, { method: 'DELETE' }),
}
