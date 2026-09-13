/** APIクライアント共通処理の分岐を固定する。
 *
 * `src/api/` は長らく「分岐を持たない薄いラッパ」としてカバレッジ対象外にしていたが、
 * 本ファイルだけは例外で、通信失敗の `NETWORK_ERROR` への変換・204の扱い・エラーコードの
 * 既定値・未登録コードのフォールバックという分岐を持つ（2026-09-13のカバレッジ監査で
 * 実測34.6%と判明。Phase 33）。全画面のエラー表示がここを通るため、対象へ戻して固定する。
 * エンドポイント単位のラッパ（`goals.ts` 等）は実通信なしでは意味のある検証にならないため
 * 除外を維持している（OPERATIONS.md「フロントエンドのテストとカバレッジ」）。
 *
 * 期待する文言は `t()` から取得する。ロケールを直書きすると文言変更のたびにテストが
 * 落ちるうえ、ゼロハードコーディング（CODING_RULES.md ②）にも反するため。 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiClient, apiErrorMessage } from './client'
import { t } from '../locales/t'

/** バックエンドが実際に返すエラーコードのひとつ（`backend/app/api/errors.py`）。 */
const REGISTERED_CODE = 'VALIDATION_ERROR'
/** ロケールに登録のないコード。既定文言へフォールバックする経路の確認に使う。 */
const UNREGISTERED_CODE = 'SOMETHING_UNKNOWN'
const PATH = '/goals'
const EXPECTED_URL = '/api/v1/goals'

/** `fetch` の戻り値を組み立てる。各テストで同じオブジェクトリテラルを書かないための共通処理。 */
function mockResponse(options: {
  ok: boolean
  status?: number
  json?: () => Promise<unknown>
}): Response {
  return {
    ok: options.ok,
    status: options.status ?? (options.ok ? 200 : 400),
    json: options.json ?? (() => Promise.resolve({})),
  } as unknown as Response
}

/** バックエンドのエラー応答形式（`{"error": {...}}`）を返す `fetch` を仕込む。 */
function stubErrorResponse(body: unknown): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve(mockResponse({ ok: false, json: () => Promise.resolve(body) }))),
  )
}

beforeEach(() => {
  vi.restoreAllMocks()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ApiError', () => {
  it('keeps the code and defaults details to an empty array', () => {
    const error = new ApiError(REGISTERED_CODE, 'message')

    expect(error.code).toBe(REGISTERED_CODE)
    expect(error.message).toBe('message')
    expect(error.details).toEqual([])
  })

  it('keeps the details when they are given', () => {
    const details = [{ field: 'name' }]

    expect(new ApiError(REGISTERED_CODE, 'message', details).details).toBe(details)
  })

  it('localizes a registered code', () => {
    const error = new ApiError(REGISTERED_CODE, 'サーバ側の文言')

    expect(error.localizedMessage).toBe(t(`errors.${REGISTERED_CODE}`))
  })

  it('falls back to the default message for an unregistered code', () => {
    const error = new ApiError(UNREGISTERED_CODE, 'サーバ側の文言')

    expect(error.localizedMessage).toBe(t('errors.default'))
  })
})

describe('apiErrorMessage', () => {
  it('localizes an ApiError', () => {
    expect(apiErrorMessage(new ApiError(REGISTERED_CODE, 'message'))).toBe(
      t(`errors.${REGISTERED_CODE}`),
    )
  })

  it('falls back to the default message for anything else', () => {
    expect(apiErrorMessage(new Error('boom'))).toBe(t('errors.default'))
    expect(apiErrorMessage(undefined)).toBe(t('errors.default'))
  })
})

describe('apiClient request handling', () => {
  it('prefixes the base path and returns the parsed body', async () => {
    const payload = { id: 1 }
    const fetchMock = vi.fn(() =>
      Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve(payload) })),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiClient.get(PATH)).resolves.toEqual(payload)
    expect(fetchMock).toHaveBeenCalledWith(EXPECTED_URL, {
      headers: { 'Content-Type': 'application/json' },
    })
  })

  it('returns undefined for 204 without parsing a body', async () => {
    const json = vi.fn(() => Promise.resolve({}))
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(mockResponse({ ok: true, status: 204, json }))),
    )

    await expect(apiClient.get(PATH)).resolves.toBeUndefined()
    expect(json).not.toHaveBeenCalled()
  })

  it('converts a network failure into NETWORK_ERROR', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )

    await expect(apiClient.get(PATH)).rejects.toMatchObject({
      code: 'NETWORK_ERROR',
      message: t('errors.NETWORK_ERROR'),
    })
  })

  it('surfaces the code, message and details returned by the server', async () => {
    const details = [{ loc: ['name'] }]
    stubErrorResponse({ error: { code: REGISTERED_CODE, message: 'サーバ側の文言', details } })

    await expect(apiClient.get(PATH)).rejects.toMatchObject({
      code: REGISTERED_CODE,
      message: 'サーバ側の文言',
      details,
    })
  })

  it('falls back to INTERNAL_ERROR when the error body cannot be parsed', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          mockResponse({ ok: false, json: () => Promise.reject(new Error('not json')) }),
        ),
      ),
    )

    await expect(apiClient.get(PATH)).rejects.toMatchObject({
      code: 'INTERNAL_ERROR',
      message: t('errors.default'),
      details: [],
    })
  })

  it('falls back to INTERNAL_ERROR when the body has no error object', async () => {
    stubErrorResponse({})

    await expect(apiClient.get(PATH)).rejects.toMatchObject({
      code: 'INTERNAL_ERROR',
      message: t('errors.default'),
      details: [],
    })
  })

  it('falls back field by field when the error object is partially filled', async () => {
    stubErrorResponse({ error: { code: REGISTERED_CODE } })

    await expect(apiClient.get(PATH)).rejects.toMatchObject({
      code: REGISTERED_CODE,
      message: t('errors.default'),
      details: [],
    })
  })
})

describe('apiClient methods', () => {
  /** 本文を伴うメソッドは同じ内部処理を共有するため、表で回して差分（メソッド名）だけを見る。 */
  const methodsWithBody = [
    { name: 'post', call: (body?: unknown) => apiClient.post(PATH, body), expected: 'POST' },
    { name: 'patch', call: (body?: unknown) => apiClient.patch(PATH, body), expected: 'PATCH' },
    { name: 'put', call: (body?: unknown) => apiClient.put(PATH, body), expected: 'PUT' },
    { name: 'delete', call: (body?: unknown) => apiClient.delete(PATH, body), expected: 'DELETE' },
  ] as const

  it.each(methodsWithBody)('sends the serialized body for $name', async ({ call, expected }) => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve({}) })),
    )
    vi.stubGlobal('fetch', fetchMock)
    const body = { name: '目標A' }

    await call(body)

    expect(fetchMock).toHaveBeenCalledWith(EXPECTED_URL, {
      headers: { 'Content-Type': 'application/json' },
      method: expected,
      body: JSON.stringify(body),
    })
  })

  it('omits the body when it is not given', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(mockResponse({ ok: true, status: 204, json: () => Promise.resolve({}) })),
    )
    vi.stubGlobal('fetch', fetchMock)

    await apiClient.post(PATH)

    expect(fetchMock).toHaveBeenCalledWith(EXPECTED_URL, {
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
      body: undefined,
    })
  })
})
