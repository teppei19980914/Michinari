import { t } from '../locales/t'

/**
 * APIクライアント共通処理（技術選定書7.3「エラーコードのみを返し、文言はロケールファイルで
 * 管理する」）。バックエンドのエラー応答形式は backend/app/api/errors.py の
 * `{"error": {"code", "message", "details"}}` に準拠する。
 */

const BASE_URL = '/api/v1'

/** `details`から`{"reason": "..."}`形式のreasonを1件取り出す（削除不可エラー3種のみが持つ、
 * app/api/errors.py handle_domain_error・app/services/exceptions.pyのreasonクラス属性）。
 * detailsは他の形（バリデーションエラーの`{"loc", "msg"}`等）も許容する汎用構造のため、
 * reasonを持たない要素は無視する。 */
function findReason(details: unknown[]): string | null {
  for (const detail of details) {
    if (typeof detail === 'object' && detail !== null && 'reason' in detail) {
      const reason = (detail as { reason: unknown }).reason
      if (typeof reason === 'string') {
        return reason
      }
    }
  }
  return null
}

export class ApiError extends Error {
  readonly code: string
  readonly details: unknown[]

  constructor(code: string, message: string, details: unknown[] = []) {
    super(message)
    this.code = code
    this.details = details
  }

  /** エラーコードに対応するロケール文言（未登録コードは既定文言）。
   *
   * `details`にreasonがあり、かつそのreasonに対応する文言（`errors.reasons.*`）が
   * 登録されている場合は、コード自体の汎用文言（例: VALIDATION_ERROR＝「入力内容に
   * 誤りがあります」）より優先する。削除不可エラー3種のように、コードは増やさず
   * detailsで原因を伝える設計（2026-09-19、非エンジニア向けエラー表示改善）のため、
   * reasonが無い・対応する文言も無い場合は従来どおりコードの文言へフォールバックする。 */
  get localizedMessage(): string {
    const reason = findReason(this.details)
    if (reason !== null) {
      const reasonKey = `errors.reasons.${reason}`
      const reasonMessage = t(reasonKey)
      if (reasonMessage !== reasonKey) {
        return reasonMessage
      }
    }
    const key = `errors.${this.code}`
    const localized = t(key)
    return localized === key ? t('errors.default') : localized
  }
}

/** 例外からユーザー表示用の文言を求める（ApiError以外は既定文言。画面ごとに同じ三項式を
 * 書かないための共通処理、CLAUDE.md DRYの原則。全画面のエラー表示・Toast.tsxのshowApiErrorが使う）。 */
export function apiErrorMessage(error: unknown): string {
  return error instanceof ApiError ? error.localizedMessage : t('errors.default')
}

/** 技術的な詳細（エラーコード＋開発者向けメッセージ）。非エンジニア向けの平易な文言
 * （apiErrorMessage）とは別に、サポートへ報告する際に伝えられる情報として折りたたみで
 * 残す（Toast.tsx、2026-09-19 非エンジニア向けエラー表示改善）。 */
export function apiErrorDetail(error: unknown): string | undefined {
  if (error instanceof ApiError) {
    return `${error.code}: ${error.message}`
  }
  if (error instanceof Error) {
    return error.message
  }
  return undefined
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
  delete: <T>(path: string, body?: unknown): Promise<T> =>
    _requestWithBody<T>('DELETE', path, body),
}
