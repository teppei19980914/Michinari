import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { reportClientError } from './reportClientError'

const CLIENT_LOGS_URL = '/api/v1/client-logs'

beforeEach(() => {
  vi.restoreAllMocks()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('reportClientError', () => {
  it('posts the error details along with the current path', () => {
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true }) as unknown as Promise<Response>)
    vi.stubGlobal('fetch', fetchMock)

    reportClientError({ message: 'boom', stack: 'at App.tsx:1', componentStack: 'in App' })

    expect(fetchMock).toHaveBeenCalledWith(CLIENT_LOGS_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        level: 'error',
        message: 'boom',
        stack: 'at App.tsx:1',
        component_stack: 'in App',
        path: window.location.pathname,
      }),
    })
  })

  it('omits stack and componentStack when not given', () => {
    const fetchMock = vi.fn((_url: string, _init?: RequestInit) =>
      Promise.resolve({ ok: true }) as unknown as Promise<Response>,
    )
    vi.stubGlobal('fetch', fetchMock)

    reportClientError({ message: 'boom' })

    const [, init] = fetchMock.mock.calls[0]
    const body = JSON.parse(init?.body as string)
    expect(body.stack).toBeUndefined()
    expect(body.component_stack).toBeUndefined()
  })

  it('does not throw when the request itself fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )

    expect(() => reportClientError({ message: 'boom' })).not.toThrow()
    // fetchの拒否が未処理のPromise拒否として漏れないこと。
    await new Promise((resolve) => setTimeout(resolve, 0))
  })
})
