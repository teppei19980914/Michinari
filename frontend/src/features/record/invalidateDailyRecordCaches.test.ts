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

  it('refreshes the schedule item report widget (単位4)', () => {
    expect(invalidate()).toContainEqual(['scheduleItemsForReport', TARGET_DATE])
  })

  it('does not invalidate anything else', () => {
    // 開発Todo_スケジュール・ガントチャート_v1.1 D-32（単位4）でscheduleItemsForReportを
    // 追加し、4件から5件になった（意図した変更、15.1手順10）。
    expect(invalidate()).toHaveLength(5)
  })
})
