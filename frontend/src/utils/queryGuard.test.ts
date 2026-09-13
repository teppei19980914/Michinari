import { describe, expect, it } from 'vitest'
import { findFailedQuery, isAnyLoading, type QueryLike } from './queryGuard'

function buildQuery<T>(data: T | undefined, overrides: Partial<QueryLike<T>> = {}): QueryLike<T> {
  return { isLoading: false, isError: false, error: null, data, ...overrides }
}

const SETTLED = buildQuery('ok')
const LOADING = buildQuery(undefined, { isLoading: true })

describe('isAnyLoading', () => {
  it('is false when every query has settled', () => {
    expect(isAnyLoading([SETTLED, SETTLED])).toBe(false)
  })

  it('is false when there is no query to wait for', () => {
    expect(isAnyLoading([])).toBe(false)
  })

  it.each([0, 1])('is true while the query at index %i is loading', (loadingIndex) => {
    const queries: QueryLike<unknown>[] = [SETTLED, SETTLED]
    queries[loadingIndex] = LOADING
    expect(isAnyLoading(queries)).toBe(true)
  })
})

describe('findFailedQuery', () => {
  it('returns undefined when every query succeeded', () => {
    expect(findFailedQuery([SETTLED, SETTLED])).toBeUndefined()
  })

  it('returns undefined when there is no query at all', () => {
    expect(findFailedQuery([])).toBeUndefined()
  })

  it('returns the failed query so the caller can read its error', () => {
    const failed = buildQuery(undefined, { isError: true, error: new Error('boom') })
    expect(findFailedQuery([SETTLED, failed])).toBe(failed)
  })

  // 渡した順がエラー表示の優先順になる。後ろの失敗で上書きされないことを固定する。
  it('returns the first failure in the given order', () => {
    const first = buildQuery(undefined, { isError: true, error: new Error('first') })
    const second = buildQuery(undefined, { isError: true, error: new Error('second') })
    expect(findFailedQuery([first, second])).toBe(first)
  })
})
