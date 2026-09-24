import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { registerGlobalErrorHandlers } from './registerGlobalErrorHandlers'

const CLIENT_LOGS_URL = '/api/v1/client-logs'

function lastRequestBody(fetchMock: ReturnType<typeof vi.fn>): Record<string, unknown> {
  const [, init] = fetchMock.mock.calls.at(-1) as [string, RequestInit]
  return JSON.parse(init.body as string)
}

// windowへのイベントリスナー登録はプロセス内で一度きりの副作用のため、テストごとに
// 登録し直すとリスナーが積み上がり1イベントで複数回fetchされてしまう。ファイル内で
// 一度だけ登録する。
registerGlobalErrorHandlers()

beforeEach(() => {
  vi.restoreAllMocks()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('registerGlobalErrorHandlers', () => {
  it('reports an uncaught error raised outside of rendering (e.g. an event handler)', () => {
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true }) as unknown as Promise<Response>)
    vi.stubGlobal('fetch', fetchMock)

    window.dispatchEvent(
      new ErrorEvent('error', { message: 'boom', error: new Error('boom') }),
    )

    expect(fetchMock).toHaveBeenCalledWith(CLIENT_LOGS_URL, expect.objectContaining({ method: 'POST' }))
    expect(lastRequestBody(fetchMock).message).toBe('boom')
  })

  it('omits the stack when the thrown value is not an Error (e.g. `throw "text"`)', () => {
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true }) as unknown as Promise<Response>)
    vi.stubGlobal('fetch', fetchMock)

    window.dispatchEvent(new ErrorEvent('error', { message: 'boom', error: 'not an Error' }))

    expect(lastRequestBody(fetchMock).stack).toBeUndefined()
  })

  it('reports an unhandled promise rejection', () => {
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true }) as unknown as Promise<Response>)
    vi.stubGlobal('fetch', fetchMock)

    const event = new Event('unhandledrejection') as Event & { reason: unknown }
    Object.assign(event, { reason: new Error('rejected') })
    window.dispatchEvent(event)

    expect(lastRequestBody(fetchMock).message).toBe('rejected')
  })

  it('stringifies a non-Error rejection reason', () => {
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true }) as unknown as Promise<Response>)
    vi.stubGlobal('fetch', fetchMock)

    const event = new Event('unhandledrejection') as Event & { reason: unknown }
    Object.assign(event, { reason: 'plain string rejection' })
    window.dispatchEvent(event)

    expect(lastRequestBody(fetchMock).message).toBe('plain string rejection')
  })
})
