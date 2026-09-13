import { describe, expect, it, vi } from 'vitest'
import type { QueryClient } from '@tanstack/react-query'
import { invalidateDailyRecordCaches } from './invalidateDailyRecordCaches'

const TARGET_DATE = '2026-09-13'

describe('invalidateDailyRecordCaches', () => {
  function invalidate() {
    const invalidateQueries = vi.fn()
    invalidateDailyRecordCaches({ invalidateQueries } as unknown as QueryClient, TARGET_DATE)
    return invalidateQueries.mock.calls.map(([arg]) => arg.queryKey)
  }

  it('refreshes the record of the updated date', () => {
    expect(invalidate()).toContainEqual(['record', TARGET_DATE])
  })

  it('refreshes every screen that summarises the record', () => {
    // 1つでも落ちると「更新したのに古い値が残る画面」ができるため、対象を明示的に固定する。
    const keys = invalidate()
    expect(keys).toContainEqual(['today'])
    expect(keys).toContainEqual(['dashboard'])
    expect(keys).toContainEqual(['calendar'])
  })

  it('does not invalidate anything else', () => {
    expect(invalidate()).toHaveLength(4)
  })
})
